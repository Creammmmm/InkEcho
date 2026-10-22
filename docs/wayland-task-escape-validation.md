# Native Wayland task Escape validation

2026-10-23, actual Ubuntu26.04 host, source adapter validation. This is not a
same-SHA AppImage acceptance or native Ubuntu24 Wayland support claim. The Xorg
adapter and its actual Ubuntu24 checks are recorded separately.

## Mechanism and cancellation ordering

After the normal application desktop entry is registered, asynchronous
`PortalTaskEscape` registers the legitimate `io.github.Creammmmm.InkEcho` identity
with the host Registry on the same D-Bus connection used for GlobalShortcuts.
A task owns its own session. Preferred trigger is Escape and the product label
is “取消当前语音任务”. Localized `trigger_description` is display information, never
parsed as a protocol key. Unknown saved action IDs are preserved instead of
replaced. Grant denial/unsupported backends leave local Qt and explicit cancel
controls available, with a non-popup status. First authorization may display the
system's configuration UI; no GNOME identity is impersonated or GSettings binding
written. Later authorization behavior remains desktop-dependent.

Arm is scheduled asynchronously after the recording state transition; it never
blocks the recorder's synchronous start. On Activated, the adapter synchronously
disconnects its owned peer, then TaskEscape invalidates its active revision and
calls cancellation in the same event-loop turn. It never waits for remote Close
before invalidating transcription/output. Terminal/disposal similarly aborts the
owned peer; graceful setup-error Close and disconnect cover partial sessions.
Pending connection completion retains a local bus reference and disconnects even
if abort already cleared the instance reference. Stale callbacks/grants cannot
cancel a replacement task. Shutdown drains owned initialization tasks.

## Actual desktop observations

An earlier identity-less CLI CreateSession returned NotAllowed. That was a probe
identity result, not evidence that native Wayland cannot provide global Escape.
Using the official own-app Registry succeeded: Registry1/GlobalShortcuts1,
CreateSession response0, explicit Close, normal exit0 and peer disconnected.
Existing own desktop entry was read, not forged or replaced by this probe.

A unique-description permission probe returned cancel-task and “按 Escape”, then
closed explicitly. Its initial UI grant completion was not observed by root or
automation; no automated Add action was invoked. The owned provider window and
public unique label were observed through AT-SPI only. Same-description rebind
then took115.313ms and closed successfully. A separate exact-provider top-level
watcher sampled89 times over4.736s at50ms, seeing no authorization window. This is
bounded sampling evidence, not a guarantee that no shorter flash is possible or
that every desktop will preserve authorization the same way.

The explicit-Close source probe passed active cancellation then idle Escape.
Production uses synchronous disconnect instead, so a separate real production
`TaskEscape`/`PortalTaskEscape` probe was required and completed:

- Original execution17064 naturally exited0. Owned native Qt target PID57987,
  start988576, DISPLAY absent; actual post-show state was visible, active and
  focused. Fresh guards checked process identity and state age before each press.
- Root reviewed the exact owned process and its prepared, **not yet visible**
  control preview. Only after exact PID authorization did it first show once;
  stable actual native focus was sampled for250ms. No user window was activated.
  This is fixture sequencing, not product focus behavior or a product focus fix.
- Two balanced synthetic evdev1 Escape press/release pairs used the production
  Mutter session methods without SetKeymap, text, clipboard or IME transport.
- First Activated called cancellation once in the same loop turn, with
  guard_active=false, revision2 and backend_closed=true. Target received no Escape
  key press. Disconnect caused the corresponding key **release** to reach the
  target; this is an observed boundary, not a claim that the entire pair was
  suppressed. No ordinary text was sent.
- After production disconnect, the second Escape reached the target: press1 /
  release2 total, one cancellation callback total. Thus idle Escape was not
  swallowed. All emission guards retained actual visible/native focus.
- Sender Stop/disconnect, guard shutdown, and owned child stdin-close/natural0
  completed. No forced signal. Original Qt text-input shutdown warnings are kept
  in the raw child stderr rather than hidden.

Four earlier production fixture runs remain failed, not rewritten as passes:
ready-before-review focus was gone when emission was authorized, so fresh guards
refused all keys (runs1–3); a single approved owned-window reactivation was denied
by Wayland (run4), again no keys. Moving Mutter Start earlier did not fix this,
so these failures must not be attributed to Mutter Start. Every failed run
retained normal sender/guard/child cleanup. The final first-show ordering avoids
the fixture's review-time focus race without relaxing the emission guard.

## Focused checks and reproducibility

Normal local IPC permissions: `pytest -q tests/test_portal_escape.py
 tests/test_task_escape.py tests/test_startup.py tests/test_ui.py` reports
**107 passed in8.00s**, normal exit0. The narrower19 portal/controller checks also
pass. They cover German localized trigger text, legitimate own registration,
foreign signal/session rejection, grant denial, saved-action preservation,
terminal during pending grant, late connection completion after abort, close
transport errors, async non-blocking arm, rapid task replacement and immediate
cancellation without a loop-turn/Close await. Ruff check/format pass. An earlier
sandbox run failed existing local IPC cases and was stopped130; that run is not
counted as a passing product check.

Local raw evidence is under `build/ubuntu24-input-pipeline/escape-portal/`:
`host-registry-lifecycle-r1.json`, `host-escape-bind-r1.json`,
`host-escape-bind-r2.json`, `host-escape-bind-r2-watch.json`,
`host-escape-active-r1.json`, `host-escape-active-r2.json`, and
`production-escape-r1.json` through `production-escape-r5.json`. The final source
origins and SHA256 hashes are in the production record; child state, prepared
preview and post-show image are adjacent under `production-escape-owned-r5/`.
Reviewed executable probes are under the sibling `tools/` directory. Real desktop
runs require a private owned target and an exact root-reviewed emit gate; never
run them against arbitrary user focus. Source CLI identity/API discovery cannot
replace the same-version, same-SHA Ubuntu24/26 package gates.

Official APIs:
[host Registry](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.host.portal.Registry.html),
[GlobalShortcuts](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html),
[shortcut identifiers](https://specifications.freedesktop.org/shortcuts/latest/).
