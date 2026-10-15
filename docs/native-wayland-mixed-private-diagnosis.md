# Private mixed-window diagnosis — 2026-10-15

The native → newly created XWayland GTK → native, same-production-transaction
acceptance test remains **failed** in the runs below. The initial diagnosis
changed no production source; the later pacing repair is recorded separately. This is a private headless GNOME/Mutter 50.1 compositor with owned GTK3
windows, not the user's desktop. A worker acknowledgement proves dispatch, not
text receipt. Exact per-window text assertions remain mandatory.

## Findings

- `private_xwayland_environment()` validates the Xwayland child PID, compositor
  ancestry, private runtime, display lock and Xauthority path, then updates the
  child environment. The lifecycle fixture copies that environment after the
  update. This was not a missing `DISPLAY` / `XAUTHORITY` forwarding error.
- GTK `is_active()` plus `has_focus()` is insufficient evidence of Mutter seat
  keyboard delivery. A read-only X diagnostic observed cases with a different
  actual X input focus; other runs confirmed the focus window was the owned
  toplevel or its owned descendant and still received no body keys.
- The original no-delay run acknowledged ten characters, but only the native
  window's first five were received. The XWayland field remained empty:
  `build/mixed-keymap-production-final.log`.
- A test-only 20 ms post-map delay with private Escape/click activation received
  only `Echo`, four of the required `kEcho` characters. This **did not pass** and
  does not justify adding a production sleep:
  `build/mixed-keymap-click-escape-settle.log`.
- A private Escape reached the X GTK widget in several diagnostic runs, but a
  subsequent F12 / second Escape did not. A temporary extra X event observer saw
  mapping notifications without the corresponding later core key presses.
  Because this added an observer and alternative activation steps, that is
  diagnostic evidence only, not a default-application compatibility result.
- The final ordinary-letter baseline removed the extra X connection, forced X
  focus, pointer operations and diagnostic function keys. After the new owned
  X GTK window reported active/widget focus, it waited 0.5 seconds and sent an
  ordinary existing `a` keysym from the private bootstrap session. It received
  **zero text and zero GTK key events**. This is a distinct session from the
  production worker; it demonstrates a broader private activation / seat-routing
  problem, not equivalence of every production device path:
  `build/mixed-keymap-plain-a-final.log`.
- That final baseline explicitly selected `GTK_IM_MODULE=simple` only for the
  owned X GTK child. The earlier launcher used `gtk-im-context-simple`.
  Neither the baseline nor the application commits text through an input-method
  API; no host input-source setting was changed.

## Current helper and reproduction

The retained helper adds read-only X focus ancestry, keymap and pointer-position
metadata. It does not force X focus or click a window. Its normal acceptance
path requires actual owned X focus as well as GTK active/widget-focus metadata,
exact native/X text and complete map/modifier restoration. The optional ordinary
letter baseline always exits as a diagnostic failure; disabling the extra X
observer is only permitted with that explicitly failing baseline.

```sh
PYTHONPATH=src .venv/bin/python \
  scripts/feasibility/mixed_keymap_workflow_probe.py --run-isolated

INKECHO_MIXED_NO_X_DIAGNOSTIC=1 INKECHO_MIXED_BASELINE=1 PYTHONPATH=src \
  .venv/bin/python scripts/feasibility/mixed_keymap_workflow_probe.py --run-isolated
```

The successful standalone production XWayland VTE check and successful host
native Chrome checks remain separate evidence. They do not turn this mixed GTK
failure into a pass. A real-desktop owned mixed-browser check can provide stronger
acceptance evidence for its actual tested application, but must retain the
private GTK result as a known failed test.


## Fresh server-map diagnosis and exact upstream source

The host reports XWayland package **2:24.1.10-1**. The matching upstream source
was downloaded, without installation, from the official
[Ubuntu source archive](https://archive.ubuntu.com/ubuntu/pool/main/x/xwayland/xwayland_24.1.10.orig.tar.xz).
In `hw/xwayland/xwayland-input.c`, `keyboard_handle_key()` queues physical key
numbers (lines 1136–1156), whereas `keyboard_handle_keymap()` directly applies a
new map to the slave and master (1163–1215). The latter contains no explicit input
queue drain. `xkb/xkbUtils.c`'s `XkbDeviceApplyKeymap()` copies the map and notifies
clients (2025–2050), also without an explicit drain. Modifier handling explicitly
drains queued events. This supports an event/mapping timing hypothesis; it does
not establish that one fixed delay guarantees consumption by every application.

A separately labelled test wrapper made a **fresh X connection and server
`XGetKeyboardMapping(132)` query before each press**. All ten mappings read the
correct Unicode symbols, including `k`, `E`, `c`, `h`, `o`, but the owned X GTK field
received only `k`. The map and modifiers were restored:
`build/mixed-keymap-fresh-server-map.log`. This rejects the hypothesis that the
server necessarily discards Unicode-style ASCII or always maps AE13 to yen.
The extra 4–6 ms queries alter timing, so this is diagnostic, not default-runtime
acceptance. Reproduction uses `INKECHO_MIXED_XMAP_DIAGNOSTIC=1`; the helper remains
restricted to the existing private runtime and never queries the host display.

The private release-only 30 ms experiment stopped at the new-window focus gate
before any X body character. Its failure is not evidence for or against that
pacing's transport correctness: `build/mixed-keymap-release30.log`.

A pure-library alternative appended a momentary `SetMods(Mod2, clearLocks=false)`
action to AE13. Both groups and initial locked masks 0/16 preserved locks, group
and the printable symbol while depressed changed 0 → 16 → 0:
`build/modifier-barrier-pure-library.json`. This sent **zero desktop keys** and did
not validate actual application handling. The modifier would be client-visible;
the experiment was stopped and **no modifier action was added to production**.
Its retained standalone research helper is
`scripts/feasibility/modifier_barrier_keymap_probe.py`.

## Formal pacing repair and regression checks

The separately owned real-desktop Chrome experiment received the exact 26-character
sample across native → XWayland → native only with both test-only waits set to
30 ms (`build/native-wayland-host-mixed-both30.json`). This motivated the minimal
production repair: wait 30 ms after a map change, then re-read modifiers before
pressing; after every owned release attempt, wait 30 ms before acknowledgment,
next mapping or restoration. No focus routing, clipboard, IME call or extra
modifier was added. Caller cancellation/expiry is checked after the new waits;
cleanup still releases and settles owned keys even after cancellation or an
ambiguous release failure.

Focused source checks: **106 passed in 1.46 s** across worker, EIS, map and parent
suites, `build/wayland-pacing-focused-tests.log`. Eight new cases cover cancellation
and deadline at each wait, release-failure cleanup ordering, and depressed/latched/
Caps state appearing during map settlement. Relevant code and experiment helpers
passed Ruff lint and formatting. These are automated checks; final rebuilt-package
host acceptance and FUSE lifecycle results belong to the main acceptance report.


## Final conservative timing — 50 ms per boundary

The first formal 30 ms / 30 ms build passed the owned host textarea mixed check,
but a separate contenteditable mixed run lost its first XWayland `k` and received
`Echo`; all ten press/release attempts were balanced and the map/modifiers were
restored. That retained failure is
`build/native-wayland-host-mixed-contenteditable-autofocus.json`. It invalidates a
broad compatibility claim based on the textarea result alone.

A test-only additional 20 ms at both boundaries, giving **50 ms after map change
and 50 ms after key release**, received the exact 26-character sample across both
window transitions and restored the original keyboard state:
`build/native-wayland-host-contenteditable-total50.json`. Its diagnostic/default
flags remain explicit; it is not the final default-package acceptance result.

The formal constants were therefore changed to **0.05 seconds** at both existing
boundaries, preserving the same cancellation, deadline, fresh-modifier and cleanup
ordering. This is a conservative rhythm measured on this host, **not an
end-to-end consumption acknowledgement from arbitrary clients**. No new focus
logic, modifier action or input-method path was introduced. The final default
package was then rebuilt and passed the host contenteditable mixed test below.

The 50 ms source revision passed the same **106 focused tests in 2.26 s**,
`build/wayland-pacing50-focused-tests.log`; Ruff lint and formatting checks passed.


## Final actual-package host result

The rebuilt default 50 ms AppImage, SHA-256
`3c18b8773ec95632fd864ffc21a63a08c465b4780c939237f5f27e2dddfc1d07`,
passed one contenteditable transaction across native → XWayland → native:
5/5/16 exact characters, both transitions, 26 balanced press/release attempts,
zero guard rejections and exact map/group/modifier restoration. Receipt:
`build/native-wayland-host-pacing50-ownedfield-final.json`, with
`diagnostic_only: false` and `default_acceptance_passed: true`. See the
[acceptance and deployment overview](native-wayland-parent-validation.md).

This host result covers the measured Chrome fields; it does not make the
private GTK test pass. The retained headless activation/seat ambiguity remains
inconclusive about that separate fixture and cannot establish arbitrary target
compatibility. Earlier 30 ms `Echo` remains a failed delivery result, while
no-body or owned-focus-loss runs remain rejected fixture attempts.
