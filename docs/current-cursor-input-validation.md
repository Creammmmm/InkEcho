# Current cursor input validation — 2026-10-14

## Revised requirement and current status

The user explicitly replaced the previous captured-target policy on 2026-10-14.
Recording starts without inspecting or requiring a focused editable target.
Changes to windows, focus, caret or selection during recording, transcription and
polishing do not cancel the task. Text follows keyboard semantics at delivery
time; changing focus during output permits subsequent characters to reach the
new focus. Neither clipboard nor system input method may deliver the text.

Explicit cancellation, expired task IDs/epochs and replaced tasks still prevent
further text dispatch, including late provider replies. Already dispatched input
cannot be retracted; cleanup releases owned keys/resources without emitting
remaining text. Ambiguous partial delivery must not trigger automatic replay.

See [project requirements](PROJECT_SPEC.md), [agent rules](../AGENTS.md) and
[development conventions](DEVELOPMENT.md). **The tested native Wayland portal
keysym route failed the Unicode gate.** The production XSendEvent backend, source
Session and final alpha7 packaged Session workflows subsequently passed on owned
GTK XWayland windows. An owned Chrome diagnostic and production VTE keyboard
check also passed. The user's Codex application remains untested. These measurements
do not establish native Wayland GTK or universal application support. The final
versioned artifact is accepted and deployed to the stable path; the independent
deployment receipt is recorded below.

Earlier AT-SPI, owned GTK, GNOME Text Editor and cloud workflow reports retain
their historical results. They tested a different input policy and do not prove
this new behavior. No historical failure or success has been relabelled.

## Required evidence

| Check | Required observation | Actual result |
| --- | --- | --- |
| Start independently of focus | Recording begins without a focused editable control or target capture | Source and final packaged workflows passed recording on an owned noneditable GTK button |
| Move while recording | Switching owned windows/caret does not cancel or bind an old target | Pending |
| Move while awaiting ASR/polishing | Task continues; returned text reaches the delivery-time cursor | Source and final packaged workflows passed switching during local ASR; polishing disabled in this run |
| Move during output | Later characters follow the new focus, without replaying the prefix or cancelling solely for focus | Production backend native-host test passed between two owned XWayland windows; separate from Session workflow |
| Explicit cancellation | Cancellation during preparation, recording, provider waits or partial output prevents further text dispatch | Source and final packaged local-ASR late-reply cancellation passed; backend partial-output cancellation passed; other boundaries covered separately in Session tests |
| Expired/replaced task | Late callbacks and pending output cannot emit text for an inactive task ID/epoch | See source Core/Session regressions in current-focus-session-validation.md; not a native full-matrix claim |
| Unicode transport | Chinese, Latin, punctuation, newline and mixed Unicode arrive through the measured transport | Native Wayland portal failed (28 expected / 15 received); owned GTK production backend and source/packaged workflows passed 28/28; Chrome diagnostic passed 28/28 |
| Permission and transport failure | Missing/denied/revoked transport produces a bounded actionable failure, without clipboard/input-method fallback | Backend owned destroyed-window check returned a fixed error without crashing; other permissions remain separate |
| Output cleanup | Cancellation/failure releases owned held keys and resources; ambiguous partial output is not replayed | Backend cancellation produced one press/one release/no tail; source/packaged workflow normalized whole-map restoration passed |
| Feedback | Production status feedback does not take focus or redirect ordinary output unexpectedly | Source and final packaged MainWindow each sent seven accepted desktop notifications, no visible Qt window; exact owned output passed |
| Actual package | Final frozen artifact exercises the revised production Session and transport, not only source or a stand-alone diagnostic | Passed with exact alpha7 extracted runtime; final hash and command below |

## Reproduction and observations to record

For each actual run, record the source revision or artifact hash, OS/desktop and
session, transport and required permissions, target application versions, exact
reproduction command/actions, observed result and remaining limitations. Record
source tests, synthetic/private-display checks, native transport measurements,
real microphone capture, local fixture requests and live cloud requests as
separate evidence. A diagnostic key event or passing unit test is not a complete
application workflow.

Native validation must coordinate exclusive access to owned disposable test
windows. No user document, credential or ambient audio should be used merely to
prove text transport; fixed fixture text suffices. Any later audio/provider
acceptance must state whether it used real microphone input, a public sample,
local responses or an authenticated cloud service. Keep secrets, audio and user
text out of logs. The test must never insert into an unrelated user window.

No cloud request was made for this revision. The reviewed
`scripts/validation/current_cursor_workflow_probe.py`
requires `--package-root` and explicit `--fixture-backend x11|wayland`, keeping the
Wayland host session distinct from its target application's transport. Its
synchronous production `_send(window, keycode, pressed)` hook now checks the
owned fixture's fresh focus snapshot, the compositor-active X window's PID, and
the focused child window's ancestry before each press. Releases pass through for
cleanup. No asynchronous gap is introduced into this gate. The helper also
compares normalized keymaps before and after the two tasks. It currently accepts
only explicit `--fixture-backend x11`; native Wayland targets are not claimed.
These window/metadata guards are confined to the test harness, not a product
focus-lock policy. Script syntax and Ruff checks passed. The root-reviewed source
workflow was subsequently run once and passed, as recorded below; future native
runs must still coordinate exclusive owned-window use.

## Native Wayland portal keysym measurement: Unicode failed

On 2026-10-14, the backend agent tested the real GNOME Wayland desktop with portal
RemoteDesktop version 2 and `AvailableDeviceTypes=7`. The request selected only
keyboard devices (`types=1`, `persist_mode=0`); ordinary desktop consent succeeded.
An earlier attempt timed out awaiting consent after 60 seconds and sent no text.
No screen-sharing stream, clipboard operation or system input method was used.

The retained reproduction is:

```sh
PYTHONPATH=src .venv/bin/python scripts/feasibility/portal_unicode_probe.py
```

This command requires coordinated access to the native desktop and standard
keyboard consent; do not run it against unrelated user windows. The probe creates
an owned empty GTK editor and checks active/focused state and its D-Bus process
identity before each key pair. All input is fixed fixture text:

- Expected: `你好 InkEcho，世界！ café Ω 😀\n第二行。` — 28 code points.
- Received: ` InkEcho caf  \n` — 15 code points (`\n` denotes a newline).
- Two runs agreed. Chinese, accented Latin, Greek and emoji were not delivered,
  despite successful keyboard calls. The session and owned editor were cleaned
  up; no user document, microphone, credential or cloud service was involved.

The official Mutter 50.1 implementation searches the current keymap for a keyval;
if absent it skips emission while completing the internal task successfully.
The RemoteDesktop method completion therefore cannot prove text delivery. This
source behavior is consistent with the measured missing characters:
[Mutter native keyval implementation](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/native/meta-virtual-input-device-native.c)
(functions around lines 434–479 and 526–589), and
[RemoteDesktop keysym handler](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/meta-remote-desktop-session.c)
(lines 698–732). No production portal adapter is claimed to support arbitrary
Unicode from this result.

## Current Codex window uses XWayland

The root agent separately inspected X11 window identity without reading its
content. `xprop -root _NET_CLIENT_LIST` returned window `0x600004`; that window's
`_NET_WM_PID` was 6479 and `WM_CLASS` identified `Chatgpt`. Combined with the native
Wayland desktop session, this identifies the current Codex window as an
**XWayland client**, not a native Wayland client.

The earlier Codex AT-SPI report still describes its observed frames/null children;
that does not determine keyboard transport support. XWayland keyboard validation
must use an owned `GDK_BACKEND=x11` fixture in the existing Wayland host, and its
result must remain distinct from native Wayland GTK. No text was sent to the
user's Codex window in this read-only identity check. The owned GTK XWayland transport diagnostic below subsequently passed. Actual
Codex delivery remains pending; separate full Session acceptance follows below.

## Read-only exclusion: Mutter 50.1 SetKeymap

Source review only; no native session was created and no keymap operation was
called. This route is excluded from the current implementation:

- `SetKeymap` replaces the seat keymap. Its optional lock blocks ordinary layout
  changes. `CurrentKeymap` exposes a name/source, not the original full map.
  [Mutter 50.1 interface](https://raw.githubusercontent.com/GNOME/mutter/50.1/data/dbus-interfaces/org.gnome.Mutter.RemoteDesktop.xml).
- Session close/finalize releases its keymap references but does not reset the
  seat. The owner is a reference-counted identity, with no destruction callback
  restoring a previous map. The seat retains the description and owner; process
  exit therefore does not establish restoration, especially with a locked map.
  [Session lifecycle](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/meta-remote-desktop-session.c),
  [owner lifetime](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/meta-keymap-description.c),
  [seat replacement and owner checks](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/native/meta-seat-impl.c).
- Explicit reset requests the compositor's fallback policy, not a saved original
  snapshot; absent a fallback description it uses US. Even adding only empty
  slots rebuilds XKB state and resets depressed modifiers.
  [Reset implementation](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/meta-backend.c),
  [XKB state replacement](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/native/meta-seat-impl.c).
- The standard consent-based RemoteDesktop portal does not expose `SetKeymap`.
  Its GNOME backend creates the underlying Mutter session under the backend's
  D-Bus identity; applications cannot treat that as their own session for keyboard
  notification. Creating another direct Mutter session would be a separate path,
  not reuse of the portal grant. No permission bypass was attempted.
  [Portal interface](https://raw.githubusercontent.com/flatpak/xdg-desktop-portal/main/data/org.freedesktop.portal.RemoteDesktop.xml),
  [GNOME portal backend](https://raw.githubusercontent.com/GNOME/xdg-desktop-portal-gnome/main/src/remotedesktop.c).

These findings exclude the proposed reliable temporary-keymap approach; they do
not claim a native experiment or rule out a future compositor-supported API with
explicit authorization and transactional restoration.

## Owned GTK XWayland XSendEvent diagnostic

The root agent reviewed a later measurement on the actual GNOME Wayland host,
using an owned empty GTK window with `GDK_BACKEND=x11`. This is the host's
XWayland server, not a private Xvfb display and not a native Wayland GTK client.
The candidate XSendEvent route with `NoEventMask` (0) delivered the complete
28-code-point mixed Unicode sample exactly. It temporarily mapped an unused
keycode, 248, and verified restoration of its own slot. Comparing keymap rows
while ignoring trailing zero padding also matched the original map:
`normalized_map_restored=true`, `changed_keycodes=[]`. The original-map snapshot
for this run is `/tmp/inkecho-xsend-map-of5gou9d.json`.

Earlier diagnostic failures have narrower implications:

- The initial KeyPressMask/KeyReleaseMask route delivered 0 of 28 characters.
  Delivery with mask 0 then succeeded, so that observation must not be reported
  as proof that XWayland cannot receive Unicode.
- An ASCII baseline using the existing keycode 38, with no map change, passed.
  This checked event delivery independently of temporary Unicode mapping.
- An earlier whole-map byte comparison returned false. A subsequent read-only
  check found no remaining U+3002 mapping; the final run added normalized row
  comparison and verified every keycode unchanged. The earlier false result is
  retained as a less precise comparison, not silently relabelled as a pass.

The retained implementation is
`scripts/feasibility/xwayland_unicode_probe.py` with
`scripts/feasibility/xsend_transport.py`. The XWayland server version was 24.1.10;
the GTK fixture used the system GTK 3 installation. The executing agent supplied
the final command below; use `--fixture gtk` for GTK:

```sh
PYTHONPATH=src \
LD_LIBRARY_PATH="$PWD/build/listening-test-tools/root/usr/lib/x86_64-linux-gnu" \
.venv/bin/python scripts/feasibility/xwayland_unicode_probe.py \
  --fixture chrome --transport xsend --owner-mask \
  --xdotool "$PWD/build/listening-test-tools/root/usr/bin/xdotool"
```

This is an explicitly coordinated owned-window diagnostic: the xdotool path is
used for fixture activation and focus/PID checks, while XSendEvent sends the test
characters. It is not permission to send test text to the user's Codex window.

## Owned Chrome XWayland diagnostic

A subsequent owned Chrome XWayland fixture also received all 28 code points,
including Chinese, accented Latin, Greek, emoji and newline. Its temporary slot
and normalized whole map were restored, with `changed_keycodes=[]`; the original
map snapshot is `/tmp/inkecho-xsend-map-d6rn4mg1.json`. The measured versions were Google Chrome 154.0.8037.97,
`libgtk-3-0t64=3.24.52-0ubuntu1` and `xwayland=2:24.1.10-1`.

The first Chrome run received 27 of 28 code points: only newline was missing when
Return used the temporary mapping slot. The successful run used the existing
Return keycode instead. This distinction is part of the measured transport
requirements; a successful native call alone was not treated as proof of delivery.

These diagnostic measurements do not by themselves prove production KeyboardInput
or a microphone/provider/Session workflow. The separate production and source
workflow measurements follow. Native Wayland GTK, Codex and general application
support remain unproven; no production build or deployment follows from a fixture
result alone.

## Production keyboard backend on the native host

After source review, the backend agent exercised the actual `KeyboardInput` on
two owned GTK XWayland windows in the GNOME Wayland session:

```sh
PYTHONPATH=src \
LD_LIBRARY_PATH="$PWD/build/listening-test-tools/root/usr/lib/x86_64-linux-gnu" \
.venv/bin/python scripts/feasibility/keyboard_backend_probe.py \
  --xdotool "$PWD/build/listening-test-tools/root/usr/bin/xdotool"
```

Observed: all 28 mixed Unicode code points arrived exactly; switching between the
two owned windows during output sent later characters to the new window; partial
cancellation produced one press and its matching release without sending the
remaining text. Sending to a deliberately destroyed owned X window produced a
fixed error without crashing the process. The normalized whole keymap matched its
initial state after cleanup. These checks used the production emitter with
additional test-only ownership guards, not a replacement transport.

The complete backend report is
[keyboard transport validation](keyboard-transport-validation.md). The backend
focused suite separately reported 22 passing tests. Core/Session/UI
regressions are recorded in
[Session validation](current-focus-session-validation.md). Automated tests and
owned-window measurements do not establish arbitrary application compatibility.

## Source microphone and current-cursor workflow: passed

Once the backend agent released the desktop, the reviewed source helper ran once
and exited 0. The command was:

```sh
env QT_QPA_PLATFORM=wayland PYTHONPATH="$PWD/src" PYTHONNOUSERSITE=1 \
  .venv/bin/python scripts/validation/current_cursor_workflow_probe.py \
  --package-root "$PWD/src" --fixture-backend x11 \
  --output "$PWD/build/current-cursor-source-result.json"
```

The result file reports version `0.1.0a7`, the source package path under
`src/inkecho`, host session `wayland`, target transport `xwayland`, and
`passed=true`. This was the working source, not a rebuilt AppImage.

- The real recorder started while an owned noneditable GTK button had focus.
  After recording stopped, the local ASR response was delayed and a second owned
  editable window became active. The task stayed in `transcribing`; all 28
  Unicode code points then arrived exactly in the new window.
- A second short recording was cancelled after the local ASR request began.
  After the delayed response, no additional key press or text appeared. Outcomes
  were one success, one cancellation and zero failures, with no diagnostic error.
- Two microphone captures totaled 1.25525 seconds. Only the certificate-verified
  localhost HTTPS fixture received the audio: WAV payloads were 20,470 and 19,786
  bytes. Polishing was disabled, so there were two local ASR requests and zero
  polishing requests. Fixed replies test orchestration and delivery, not ASR
  quality.
- The production MainWindow notification policy produced seven accepted desktop
  notifications, with zero visible Qt top-level windows. The test guard observed
  28 key presses, and the normalized whole keymap matched its starting state.
- Temporary configuration/statistics/logs, both owned fixtures and recording
  resources were cleaned up. No user credentials, cloud calls, clipboard, system
  input method or saved audio file were involved.

This Session run did not test a physical shortcut, focus changes during emission,
partial-output cancellation or polishing. The latter transport cases have the
separate backend evidence above. It does not establish Codex delivery or native
Wayland GTK support. The final packaged acceptance is recorded below.

## Owned VTE XWayland production-keyboard check

After the package's owned GTK and UI checks released the desktop, the backend
agent ran `KeyboardInput` against an owned VTE 0.84.0 (`libvte-2.91-0` and
`gir1.2-vte-2.91` packages `0.84.0-2`) fixture on the existing XWayland server:

```sh
PYTHONPATH=src \
LD_LIBRARY_PATH="$PWD/build/listening-test-tools/root/usr/lib/x86_64-linux-gnu" \
.venv/bin/python scripts/feasibility/terminal_keyboard_probe.py \
  --xdotool "$PWD/build/listening-test-tools/root/usr/bin/xdotool"
```

The first run passed: 28 code points sent, `unicode_content_exact=true`,
`raw_utf8_with_return_exact=true`, and all 53 expected raw PTY bytes received.
Return correctly arrived as one CR byte and zero LF bytes in the raw terminal
protocol; this is not a missing-newline failure. No shell ran, no command was
executed, no clipboard was used, and the normalized map was restored. The fixture
was cleaned up. This verifies that owned terminal transport only, not arbitrary
shell/application behavior or an additional microphone/cloud workflow.


## Final alpha7 artifact and packaged workflow: passed

The final artifact is `dist/InkEcho-0.1.0a7-x86_64.AppImage`, **108,698,104 bytes**:

```text
c39b3755479b67228c174c01469651873c2b853ff509d8e5155c649e422eff4b
```

The build used existing hash-verified cached dependencies and AppImage runtime;
no dependency upgrade or system package installation was performed:

```sh
.venv/bin/python scripts/packaging/build_appimage.py
```

Before the initial candidate build, Ruff lint and format checks passed (129 files)
and the complete host-side suite passed **348 tests, with 2 opt-in tests skipped,
in 5.42 seconds**. A restricted-sandbox attempt could not create the local sockets
needed by the suite; rerunning with host socket access passed. A final hotkey
status text correction then passed its 19 focused tests. The application was
rebuilt and all artifact checks below repeated after that correction. The earlier
candidate hash is not this final artifact; the later exact-commit gate is a
separate release step.

The final extracted inventory verified 3,886 regular files and 1,048 contained
symlinks. All 34 application Python/asset files matched the frozen working source
byte for byte. Runtime metadata reports InkEcho 0.1.0a7, Python 3.13.15 and
PySide6 6.12.0. `.DirIcon` points to the bundled PNG. The sidecar checksum matches.
The metadata-only receipt is `build/current-cursor-alpha7-inventory-result.json`.

The reviewed helper ran using this exact artifact's Python, libraries and package
root, on the existing GNOME Wayland host with owned XWayland fixtures. To
reproduce, first extract the final image with `--appimage-extract` from an empty
`build/current-cursor-alpha7-extracted` directory, then run from the repository
root (coordinate exclusive use of the native desktop):

```sh
appdir="$PWD/build/current-cursor-alpha7-extracted/squashfs-root"
env QT_QPA_PLATFORM=wayland \
  QT_PLUGIN_PATH="$appdir/packages/PySide6/Qt/plugins" \
  PYTHONHOME="$appdir/usr" PYTHONPATH="$appdir/packages" \
  LD_LIBRARY_PATH="$appdir/usr/lib/inkecho" PYTHONNOUSERSITE=1 \
  "$appdir/usr/bin/python3" scripts/validation/current_cursor_workflow_probe.py \
  --package-root "$appdir/packages" --fixture-backend x11 \
  --output "$PWD/build/current-cursor-alpha7-workflow-result.json"
```

It exited 0 with `passed=true`: recording started on the noneditable button;
switching windows during transcription did not cancel; 28 Unicode code points
arrived exactly at the second window; explicit cancellation prevented a late
reply from adding text. There were two real microphone captures totaling
**1.2979375 seconds**, one success, one cancellation and zero failures. Two WAV
requests (21,152 and 20,470 bytes) went only to verified local HTTPS; polishing
was disabled. Seven production notifications were accepted, no Qt top-level
window was visible, diagnostics were empty, and the normalized whole keymap was
restored. There was no saved audio, user credential, cloud request, clipboard or
system input method. The test gate counted 28 presses and all owned resources
were cleaned up. Physical shortcuts and output-time focus/partial cancellation
were not repeated in this Session run; separate backend evidence above covers
the latter transport behavior.

The final actual AppImage then ran sequentially on native Qt Wayland with fresh
temporary configuration/data, development Python/library variables removed,
`--screenshot-dir build/current-cursor-alpha7-pages --quit-after 3`, using its
`--appimage-extract-and-run` option. It exited 0 and produced all nine page PNGs.
The home and compatibility pages were visually inspected for readable Chinese,
correct current-cursor instructions and unclipped layout. The README image is
this final package's home screenshot; F13 is the disposable default, not the
user's configured shortcut. No recording test ran concurrently with the GUI.

No new Ubuntu 24.04 container or other desktop matrix is claimed by these checks;
previous release results remain historical. The user-facing stable alias and
configuration were left unchanged during build and acceptance.

## Deployment

The root agent independently accepted and atomically deployed the final image to
`dist/InkEcho-0.1.0-alpha-x86_64.AppImage`, with SHA-256
`c39b3755479b67228c174c01469651873c2b853ff509d8e5155c649e422eff4b`.
The versioned alpha6 image remains preserved. The stable entry launched with
`--background` as PID 145834; diagnostics after its latest startup contained zero
ERROR records. Standard output contained only Qt FFmpeg information.

All three user JSON files retained identical before/after SHA-256 values. The
GNOME shortcut adapter confirmed Ctrl+F4 remained registered. No Secret Service
read or write was performed during deployment. These are configuration and
startup checks, not a physical-shortcut or user-Codex editing test. The receipt is
`build/current-cursor-deployment-result.json`.
