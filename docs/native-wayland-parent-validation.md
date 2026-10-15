# GNOME Wayland integration and alpha9 acceptance — 2026-10-15

This is the current acceptance overview. Historical failures below remain evidence;
passing unit tests or a private compositor test alone do not establish support for
an arbitrary user's desktop. The final measured runtime is **0.1.0a9**, Linux x86_64, with 50 ms production
pacing. The actual rebuilt package passed native → XWayland → native
contenteditable delivery in one transaction. Earlier 30 ms and diagnostic
artifacts remain separate checkpoints.
The host measurements use **Ubuntu 26.04.1, GNOME/Mutter 50.1 and Chrome
154.0.8037.97**. Acceptance used owned test fields. After acceptance, the final artifact was
deployed to the existing stable launch path; the three user JSON files and
Ctrl+F4 binding were preserved. Deployment evidence is recorded below.

## Passed checks

| Check | Actual result and boundary |
| --- | --- |
| Final working-tree checks | **509 passed, 2 skipped in 7.89 s**, `build/native-wayland-final-suite.log`; repository-wide Ruff lint and formatting passed for **169 Python files**. This is the final working-tree check, not the later clean-HEAD workflow receipt. |
| Acceptance-helper checks | The seven new probe/fixture/test files passed Ruff lint and formatting; the owned host guard passed **10 tests**. Relative Markdown links in README and both current reports resolve. Root also checked all **164 Python files** with repository-wide Ruff. These are working-tree checks, not the final clean-HEAD workflow receipt. |
| Parent/guard/desktop regressions | **32 passed**: 19 parent-adapter tests, 10 host-probe guard tests and 3 desktop-capability tests. These use fake processes/metadata; they do not send desktop keys. |
| Final 50 ms pacing regressions | **106 focused tests passed**, including eight new cancellation/expiry and held-key/Caps checks across the new waits. `build/wayland-pacing50-focused-tests.log`. These are synthetic boundary tests, separate from the desktop receipts. |
| Private production worker | Native Chrome contenteditable received the fixed **26-codepoint BMP** sample exactly; the original map was restored. Production cancellation and stdin EOF after character 5 stopped the remaining 21 characters, produced no delayed text and restored the map. See the [keymap report](native-wayland-keymap-validation.md) for commands and separate prototype versus production evidence. |
| Final 50 ms pacing interruption | Final source and package worker hashes match. Private native Chrome cancellation and requester EOF each stopped at exactly five characters, left 21 unsent, produced no delayed output and restored the original map; both exited 0. `build/nested-keymap-production-pacing50-cancel.log`, `build/nested-keymap-production-pacing50-eof.log`. |
| Private final worker, XWayland terminal | Owned VTE raw PTY received **26/26**, with Return observed as CR, no late output and original map bytes restored; `GdkX11Display` and owned active focus were confirmed. `build/nested-keymap-production-final-vte-xwayland.log`. This single-target check does not replace mixed-window acceptance. |
| Source default checkpoint before pacing | Owned native Chrome textarea: **26/26** exact, **26 press and 26 release attempts**, continuously owned focus, original map/group/modifier state restored; no experimental flag or inserted delay. `build/native-wayland-host-default.json`. |
| First alpha9 mounted runtime checkpoint | Owned host native Chrome contenteditable: **26/26**, balanced events and exact map/modifier restoration. All selected modules came from the actual AppImage's FUSE mount and matched source. `build/native-wayland-host-appimage.json`. This is the input path, not a new microphone/cloud-ASR end-to-end test. |
| 30 ms alpha9 default textarea mixed delivery | The actual FUSE-mounted 30 ms package passed a single 26-character insert: **5 native → 5 XWayland → 16 native**, both switches confirmed, exact per-field text, 26 balanced press/release attempts and exact map/group/modifier restoration. `diagnostic_only: false`, `default_acceptance_passed: true`; no test-only delays. `build/native-wayland-host-mixed-final.json`. This verifies both directions for the measured host textarea windows, not the later failing contenteditable case. |
| Final 50 ms default contenteditable mixed delivery | Actual FUSE-mounted final artifact: one insert, **5 native → 5 XWayland → 16 native**, exact fields, both switches, 26 balanced press/release attempts, zero guard rejections and exact original map/group/modifier restoration. `passed` and `default_acceptance_passed` true, `diagnostic_only` false. `build/native-wayland-host-pacing50-ownedfield-final.json`. This verifies the measured host contenteditable current-cursor requirement across both directions. |
| Final 50 ms alpha9 FUSE parent death | The mounted Python parent sent exactly `中` to an owned private GTK editor, then the supervisor killed that exact parent through a pidfd. The formal guardian restored the original map/group/modifiers, sent no tail, exited, and the FUSE mount disappeared. `build/native-wayland-alpha9-pacing50-fuse.log` (final 50 ms worker and artifact). |
| Actual alpha9 GUI startup | Exit 0 and nine pages captured under isolated configuration/data, native Wayland, with a visible application window. Root inspected the compatibility page for complete layout. `build/native-wayland-a9-final-ui.log`, `build/native-wayland-a9-final-ui/`; this used the final 3c18 artifact. |
| Artifact contents | **37 source/asset files** byte-identical, every symlink contained in AppDir, no retired accessibility adapter, `.DirIcon → inkecho.png`, pinned libei bundled. `build/native-wayland-alpha9-pacing50-inventory-check.json`; final 50 ms artifact SHA-256 verified. |

## Retained failures and remaining limits

The 30 ms + 30 ms default contenteditable mixed run received `Echo` instead of
`kEcho` in the newly opened owned XWayland field, despite owned focus remaining
true. It failed exact-text acceptance and restored the map/modifiers:
`build/native-wayland-host-mixed-contenteditable-autofocus.json`. This remains a failed historical product result; the final 50 ms package
subsequently passed the same contenteditable text requirement.

A further controlled contenteditable experiment added 20 ms at each boundary,
for total 50 ms after mapping and after release, and received all 26 characters
across both directions with exact restoration. It is still diagnostic-only:
`build/native-wayland-host-contenteditable-total50.json`. The production constants were then changed to 50 ms with the same
cancellation/expiry boundaries. The rebuilt package passed the default-path
contenteditable check without extra waits, as recorded above.

The final host fixture also corrected its own startup readiness: when its newly
created browser window gains focus, that page focuses its own editable field.
Readiness requires 250 ms of continuous owned window/field focus before body
output. It does not activate an OS window or periodically reclaim focus, and it
changes no product behavior. Earlier 50 ms fixture attempts with no body output
or a one-character prefix followed by owned-focus loss remain rejected fixture
runs, not evidence of a product transport failure. In contrast, the 30 ms `Echo`
case above retained owned focus and remains a genuine failed delivery result.

The earlier mixed native/XWayland default-path check **failed**. Real host tests
against the first mounted alpha9 runtime exposed a delivery-timing problem:
without the later pacing correction, the transaction reached ten acknowledged
characters but the owned XWayland Chrome prefix was wrong. An acknowledgement
proves dispatch, not text receipt. The 30 ms production correction passed the real-host textarea default-path
test above, but the subsequent contenteditable test exposed a remaining failure.

A controlled host experiment then **passed diagnostically**, using one production
`insert` transaction and the same 26-character sample: five characters reached
owned native Chrome, the next five reached owned XWayland Chrome, and the last
16 reached the native field after returning. Both direction changes were
confirmed; 26 presses and 26 releases were attempted; the exact original map,
group and modifiers were restored. This used two **test-only** waits: 30 ms after
mapping and 30 ms after key release. The receipt explicitly records
`diagnostic_only: true` and `default_acceptance_passed: false`:
`build/native-wayland-host-mixed-both30.json`. It is evidence for the timing
correction on this host, not acceptance of an unchanged default package.

The controls remain failures: 20 ms after mapping alone produced `EEcho` instead
of `kEcho` (`build/native-wayland-host-mixed-settle20-wait.json`); 30 ms after
release alone produced `cho`
(`build/native-wayland-host-mixed-keysettle30.json`). These outcomes do not
establish a general latency bound for other hardware or applications. The
product correction retains task validity checks across both new waits. Its final
default path subsequently passed without test-only pacing options.

The earlier private headless native → XWayland GTK → native gate still did
**not pass**. Its final plain-letter control also delivered no `a` key event or
text despite GTK active/widget-focus metadata. That exposes ambiguity in the
private activation/seat fixture, but does not prove the product free of bugs.
The stronger real-host browser diagnostic above does not turn the private GTK
failure into a pass. See the
[private mixed diagnosis](native-wayland-mixed-private-diagnosis.md), retained
`build/mixed-keymap-production-final.log` and
`build/mixed-keymap-plain-a-final.log`. No existing user document, clipboard,
input-source setting or Shell security bypass was used. The owned host targets
were temporary browser profiles displaying only local fixed-sample fields.

The first host production run received **19/26** despite 26 balanced press/release
attempts and preserved focus. Adding a test-only 20 ms delay did not fix it.
The host's existing libpinyin input context transformed ordinary Latin keysyms.
The final mapping uses Unicode keysyms for all printable characters; the runtime
verifies their decoding instead of silently using an incompatible layout. The
subsequent host experiment and final default both received **26/26**. This does
not mean the application changes the system input method: it calls no IME API,
changes no user input-source setting, and does not use an IME to commit text.
The existing desktop IME may still influence application handling on unmeasured
systems. Details and retained failures are in the
[keymap report](native-wayland-keymap-validation.md) and
[feasibility report](native-wayland-feasibility.md).

The first FUSE attempt stopped before parent death because the private GTK editor
lost focus during runtime/authorization startup; it received no text or text-key
event. The corrected test waits for mounted-parent authorization, then creates
and confirms a fresh owned GTK target before allowing output. Its one-character
prefix and strict restoration checks were not weakened. Earlier logs:
`build/native-wayland-alpha9-fuse.log` and
`build/native-wayland-alpha9-fuse-diagnostic.log`.

## Explicit limits and untested behavior

- Native GNOME delivery currently accepts BMP characters, including Chinese,
  accented Latin and Greek. Emoji/non-BMP, surrogates and unsupported controls
  reject the entire result before any text or mapping change. This is not an
  arbitrary-Unicode claim; Chromium's non-BMP behavior is documented separately.
- This round does not revalidate physical microphone → cloud ASR → polishing →
  input, physical Ctrl+F4, all applications, other compositors, Ubuntu 24.04's
  older Mutter APIs or Windows/macOS. Prior voice-workflow reports remain
  historical evidence with their original transport and scope.
- Mixed native/XWayland delivery must use the same backend throughout. The
  application does not inspect focus to choose protocols or pin an earlier target.
- Held keys, Caps Lock, missing compatible layout slots, external map changes,
  session closure and incomplete restoration are explicit errors. A guardian
  still restoring can outlive its parent. The UI says the layout has not yet been
  restored and input is paused; releasing keys is a first action, not a guarantee
  that every service failure is resolved by doing so.

## Parent, Session and UI behavior

`platform/wayland_keyboard.py` selects the native route by GNOME Wayland desktop
identity; the existing X11 backend remains separate. A bounded JSONL pipe permits
one character request at a time. The worker inherits the actual Python/runtime
environment in a separate process session. Session passes the absolute monotonic
task deadline, and the worker checks after asynchronous work and before each
press. Parent validity checks also run after each acknowledgement and `finish`.
Explicit cancellation, stale epochs and deadlines stop unsent text; focus changes
alone do not cancel production tasks. No ambiguous prefix is replayed.

Connection does not authorize. Explicit enable is cancellable, and idle
`session_closed` events invalidate readiness without reauthorizing. The UI
refreshes current backend readiness. Readers, pending requests and cleanup are
bound to their original worker generation: an old EOF or queued cancellation
cannot affect a replacement. An ACK followed by session closure cannot restore a
stale connected state. Cleanup is bounded for the caller but never forcibly kills
a guardian that still owns restoration work.

The focused regression history was 107 integration tests, then 17 and 18 adapter
tests; the current 32-test subset adds connection-ACK/session-close and exact
host-probe event-count requirements. GNOME and non-GNOME desktop capability tests
make distinct scope assertions, and neither promises readiness from environment
variables alone. See the [integration review](native-wayland-integration-review.md)
for the original design and ownership constraints.

## Reproduction and artifact

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q \
  tests/test_wayland_keyboard.py tests/test_native_wayland_probe.py \
  tests/test_platform_capabilities.py

PYTHONPATH=src .venv/bin/python scripts/feasibility/nested_keymap_probe.py \
  --run-isolated --production-worker --target vte-xwayland --single-slot-bmp

PYTHONPATH=src .venv/bin/python scripts/feasibility/nested_keymap_probe.py \
  --run-isolated --production-worker --target chrome-contenteditable \
  --single-slot-bmp --cancel-after 5
PYTHONPATH=src .venv/bin/python scripts/feasibility/nested_keymap_probe.py \
  --run-isolated --production-worker --target chrome-contenteditable \
  --single-slot-bmp --worker-eof-after 5

PYTHONPATH=src .venv/bin/python scripts/feasibility/mixed_keymap_workflow_probe.py \
  --run-isolated

PYTHONPATH=src .venv/bin/python scripts/feasibility/fuse_guardian_workflow_probe.py \
  --run-isolated --appimage dist/InkEcho-0.1.0a9-x86_64.AppImage \
  --sha256 3c18b8773ec95632fd864ffc21a63a08c465b4780c939237f5f27e2dddfc1d07
```

The FUSE test uses the standard `python -m` current-directory lookup for a
**test-only replacement main**, never shipped in the application. It validates a
private runtime path, explicit marker, argv, actual FUSE mount, Python and module
origins. The formal packaged parent/guardian remain unchanged. This tests actual
FUSE-runtime parent death, **not death of the GUI main loop**. The two-stage
fixture barrier avoids confusing startup focus with delivery. On failure the
owned private compositor is closed; any known guardian is tracked by pidfd,
never by a global process scan or an unrelated PID kill.

The host helper is opt-in and must be reviewed before use:

```sh
QT_QPA_PLATFORM=wayland PYTHONPATH=src .venv/bin/python \
  scripts/validation/native_wayland_keyboard_probe.py --run-host \
  --package-root "$PWD/src" --field textarea --output build/host-result.json
```

It permits only a unique temporary Chrome profile and local fixed sample. A
worker-side test guard requires owned PID/parent, native protocol evidence and
focus metadata no older than 250 ms before every press; releases remain
unconditional. The pass predicate requires exact text, exact restoration,
`press_attempts == release_attempts == 26`, and no failure/focus-loss/cleanup error.
No initial focus means zero presses and failure. Fixed-sample diagnostic codepoints
are emitted only for that owned field. `--ack-settle` is optional test-only
experimentation, default zero; the removed `--unicode-latin` experiment is no
longer accepted because the final default requires that representation.

The actual mounted-runtime host check uses two terminals. In the first, keep
this process alive and note the freshly printed mount path:

```sh
./dist/InkEcho-0.1.0a9-x86_64.AppImage --appimage-mount
```

In the second, replace `/tmp/.mount_PRINTED_PATH` with that current output;
never reuse a path from an older log. Run from the repository root:

```sh
inkecho_test_mount=/tmp/.mount_PRINTED_PATH
env APPDIR="$inkecho_test_mount" PYTHONHOME="$inkecho_test_mount/usr" \
  PYTHONPATH="$inkecho_test_mount/packages" PYTHONNOUSERSITE=1 \
  LD_LIBRARY_PATH="$inkecho_test_mount/usr/lib/inkecho" \
  "$inkecho_test_mount/usr/bin/python3" \
  scripts/validation/native_wayland_keyboard_probe.py \
  --package-root "$inkecho_test_mount/packages" --run-host \
  --field contenteditable --output build/native-wayland-host-appimage.json
```

The final mixed-window acceptance uses that same live mount environment, with
no `--map-settle` or `--key-settle` diagnostic options:

```sh
env APPDIR="$inkecho_test_mount" PYTHONHOME="$inkecho_test_mount/usr" \
  PYTHONPATH="$inkecho_test_mount/packages" PYTHONNOUSERSITE=1 \
  LD_LIBRARY_PATH="$inkecho_test_mount/usr/lib/inkecho" \
  "$inkecho_test_mount/usr/bin/python3" \
  scripts/validation/host_mixed_wayland_probe.py \
  --package-root "$inkecho_test_mount/packages" --run-host \
  --field contenteditable \
  --output build/native-wayland-host-pacing50-ownedfield-final.json
```

The test-only transition guard pauses presses until a newly created owned field
has fresh focus evidence; it never activates or types into an existing user
window. The production backend itself does not track focus or select another
protocol on a window change.

Stop the mount process with Ctrl+C only after the helper has finished and
restored the map. This check imports production modules from the live FUSE
mount; it is distinct from source and extracted-runtime validation. The helper's
owned-focus guard can reject a desktop that never activates its new test window.

The separate GUI startup check used isolated configuration and data:

```sh
./dist/InkEcho-0.1.0a9-x86_64.AppImage \
  --config-dir /tmp/inkecho-a9-host-ui-config \
  --data-dir /tmp/inkecho-a9-host-ui-data \
  --screenshot-dir "$PWD/build/native-wayland-a9-final-ui" --quit-after 5
```

It exited 0 and captured all nine pages from a visible native Wayland window.
This startup check does not exercise recording, a cloud provider or text delivery.

Final 50 ms artifact: `dist/InkEcho-0.1.0a9-x86_64.AppImage`,
**108,739,064 bytes**. SHA-256:
`3c18b8773ec95632fd864ffc21a63a08c465b4780c939237f5f27e2dddfc1d07`.
Its worker SHA-256 is
`d7dff54b2c8fbc436cc823ed576eb7a904d9faabe3ac9c3d6ee35803ae24733b`,
matching source and the final FUSE runtime check. The earlier same-version,
same-size checkpoints were `b946133c94173444b1ef275436ab8eb3b3c0d0eb6f43632badce2e3e348f91d6`
(30 ms pacing) and
`e2362843c5047676cadf6d554eab05be558bb806a7d7607af75abb2f9bbbabc9`
(before the mixed-window pacing correction). Historical hashes must not be used
for the final rebuilt package.
The builder used cached inputs, including verified libei 1.5.0-3; its Expat license
notice is included. The offline lock resolver lacked cached dbus-next metadata,
so only the existing local InkEcho lock entry was changed from a8 to a9; no
third-party dependency versions changed. The existing V0.1 GitHub release was
not changed. Local stable deployment is recorded below.


## Local deployment after acceptance

Root normally cancelled and quit the previous a8 application, then atomically
replaced `dist/InkEcho-0.1.0-alpha-x86_64.AppImage` with the accepted final a9.
The stable alias SHA-256 matched
`3c18b8773ec95632fd864ffc21a63a08c465b4780c939237f5f27e2dddfc1d07`.
The restarted main PID was **454225**, running from
`/tmp/.mount_InkEchjPBkIa`; its mounted application version was **0.1.0a9** and
its worker SHA-256 matched `d7dff54b2c8fbc436cc823ed576eb7a904d9faabe3ac9c3d6ee35803ae24733b`.
Worker PID **454262** was a child of that main process and was healthy at the
post-start check. These PIDs and mount paths are deployment observations, not
paths or PIDs to reuse in later tests.

The before/after SHA-256 lists for `config.json`, `providers/deepseek.json` and
`providers/qwen.json` compared identically:
`build/native-wayland-deploy-config-before.sha256` and
`build/native-wayland-deploy-config-after.sha256`. Read-only
`GnomeShortcuts.status` confirmed the registered **Ctrl+F4** binding still used
the same stable launch path with `--toggle`. Credentials remain in the system
secret service; no API Key was copied into source, ordinary JSON or these logs.

The existing GitHub **v0.1** release continues to provide a8 and was not replaced
by local deployment. At this report checkpoint, the final acceptance commit,
clean-HEAD workflow receipt and push are still separate root-agent steps; the
working-tree test results above do not claim that those later steps have passed.
