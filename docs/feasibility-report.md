# Stage 0 feasibility report

Test date: 2026-10-12 (Asia/Shanghai). This report distinguishes actual input
transport from production safety, and isolated fixtures from complete desktops.
No test read, replaced, or used a clipboard. No test sent text to user documents.

## Environment and result

- Host: Ubuntu 26.04.1 LTS, GNOME, native Wayland; an Xwayland display also exists.
- Additional laboratory display: Xvfb `:91`, without a compositor/window manager.
- Google Chrome 154.0.8037.97; GNOME Text Editor 50.1, GTK 4.22.4,
  GtkSourceView 5.18.0; GTK 3 TextView and VTE terminal fixtures.
- RemoteDesktop portal: version 2, available device mask 7. Tests requested only
  keyboard (`types=1`), `persist_mode=0`, no screen/clipboard access.
- GlobalShortcuts portal: actual runtime version **1**. Presence alone does not
  prove successful binding or activation.

**Proven:** Chinese, Latin, Greek, emoji, punctuation and newlines can be delivered
without a clipboard. Real X11 Chrome, GNOME Text Editor and a VTE terminal received
the sample. The targeted AT-SPI adapter additionally passed real focused GTK editor
insertion, cancellation and focus-away-then-back rejection in an isolated D-Bus/X11
session. This provides a tested, restricted safe-adapter starting point.

**Not proven:** general native Wayland browser/terminal input, native global shortcut
activation, native overlay focus behavior, physical F13/F14 presses, or either full
Ubuntu 24.04 desktop session. These remain required compatibility work. The complete
application acceptance gate is not passed by these stage 0 results.

## Unicode transport evidence

| Target and transport | Actual result | Important limit |
|---|---|---|
| Native Wayland GNOME Text Editor, AT-SPI `EditableText.InsertText` | Exact `你好 InkEcho，世界！ café Ω 😀\n第二行。` read back from the dedicated temporary document | Target was not active/focused; this was transport-only, not a production-safe input operation |
| Native Wayland Chrome, forced accessibility | Textarea exposed `Text`, no `EditableText` | Accessibility insertion unsupported for this tested target/version |
| Native VTE terminal | Exposed `Text`, no `EditableText` | Accessibility insertion unsupported; no clipboard fallback |
| Xvfb Chrome textarea, XTest keysyms | Exact `中文输入 InkEcho — Καλημέρα 🌍\n第二行！` received by page `input` event | Diagnostic transport only; global key delivery has a focus race |
| Xvfb VTE terminal, XTest keysyms | Exact raw UTF-8 bytes received by child | Child captures bytes and does not execute a shell; diagnostic only |
| Xvfb GNOME Text Editor, XTest keysyms | Exact sample saved, plus editor-added final newline | Needed 100 ms pacing; faster initial test lost characters |
| Xvfb GTK TextView, production AT-SPI adapter | Exact Unicode sample; cancellation and lost-then-restored focus refused with text unchanged | Restricted editable target, not all X11 applications |

AT-SPI's `InsertText` length is the **UTF-8 byte length**, while the caret is a
character offset. The initial probe using Python character count truncated the
sample; the corrected adapter passes `len(text.encode("utf-8"))`.

`scripts/feasibility/x11_probe.py` restores the entire original keyboard mapping.
Its cancelled-task and wrong-window checks left all three target outputs unchanged.
These checks are useful diagnostics, but checking focus and sending a global XTest
event are not atomic. **That script is not the application's injection backend.**

The application adapter in `src/inkecho/platform/accessibility.py` addresses one
specific accessibility object. It observes focus events, permanently invalidates
the captured generation, requires fresh focused/editable/active states and an
unchanged caret before dispatch, rejects selections/password/unsupported controls,
and checks cancellation again after the last asynchronous query. It does not
retarget a late result to whichever window is now focused. Once a remote application
has accepted an `InsertText` request, that single operation cannot be retracted;
there are no automatic retries after dispatch or ambiguous timeout.

## Native portal investigation

The standard RemoteDesktop consent dialog was inspected and approved through its
normal visible remote-interaction switch and Share button for the keyboard-only
test. No permission database, private compositor API, or consent bypass was used.
`Start` returned `devices=1`. Each request/session was closed after the test.

The own native Chrome fixture had an internally focused textarea but its containing
window was not active. Normal accessibility focus requests and bounded Alt+Escape
portal navigation did not produce a freshly verified active fixture. The diagnostic
therefore refused every sample before sending text. This is evidence of a working
permission/session handshake, **not native Unicode input success**.

The diagnostic uses fresh accessibility state and a nonblocking GLib timer between
characters, releases keyboard modifiers/keys on cleanup, and exits nonzero on a
refusal, mismatch, denial or timeout. It remains a lab probe, not production input.

GlobalShortcuts initially rejected an anonymous caller. After registering a temporary
own `.desktop` identity through the official host portal registry, `CreateSession`
succeeded but `BindShortcuts` timed out in 90-second and 10-second attempts. No owned
permission dialog was visible, no bindings were confirmed, and no synthetic events
were sent to unconfirmed shortcuts. Requests/sessions and temporary identity were
cleaned up. Native shortcut support remains pending.

## Hotkeys, overlay, audio and packaging

- Xvfb `XGrabKey`: F13, F14 and Ctrl+Alt+K each activated through synthetic XTest
  events on two runs. The test temporarily mapped otherwise unused keycodes for
  F13/F14 and restored the entire map. A held Ctrl+Alt+K registration conflict was
  rejected. Ctrl+Alt+F12 did not activate (possibly reserved by the X server).
  These are not physical keyboard tests.
- Xvfb Qt overlay: target focus was identical before, during two samples and after
  showing the nonfocusable overlay. The display has no compositor, so stacking,
  transparency/click-through and native Wayland remain unverified.
- Real default Logitech microphone: 48 kHz, mono Int16; repeated fresh-process
  captures returned 178176, 180224, 190464 and 200704 bytes without device errors.
  The parent independently observed 198656 bytes. RAM buffers were cleared and no
  audio file was retained. See `scripts/audio_probe.py`.
- Actual stage 0 AppImage: launched as a visible native Wayland window from outside
  the checkout; screenshot inspected. Two full builds were byte-identical after
  timestamp normalization. A nonroot, network-disabled, read-only Ubuntu 24.04
  userspace container passed the offscreen smoke test. This container has no real
  desktop, so it proves runtime loading only. See [packaging](packaging.md) for
  commands, dependencies, checksum and known limits.

## Reproduce the targeted adapter safety test

Install the development dependencies with `uv sync`. Laboratory fixtures also need
the distribution's `python3-gi`, GTK 3/AT-SPI/VTE introspection libraries, Xvfb and
xdotool. Run Xvfb on an unused private display; never point the diagnostic at `:0`.

```bash
Xvfb :91 -screen 0 1280x800x24 -nolisten tcp
dbus-run-session -- env DISPLAY=:91 GDK_BACKEND=x11 XDG_SESSION_TYPE=x11 \
  PYTHONPATH=src .venv/bin/python scripts/feasibility/accessibility_probe.py
```

The actual development-machine run used extracted distribution packages under
`/tmp/inkecho-x11` (no system installation), with their library directory in
`LD_LIBRARY_PATH` and `--xdotool /tmp/inkecho-x11/usr/bin/xdotool`.

Expected JSON: `exact_unicode`, `cancelled_unchanged` and
`focus_away_back_unchanged` all true. The script launches its own empty GTK editor,
verifies the received file, and terminates its own child. Automated tests also
cover cancellation during the final awaited focus query, UTF-8 byte length,
single-use tokens and generation invalidation.

## Reproduce individual transport probes

On a private Xvfb session, start `scripts/feasibility/gtk_target.py terminal OUTPUT`
for a safe raw-byte sink or `editor OUTPUT` for a GTK editor. The child terminal
does not run a command shell. `x11_browser_target.py` launches a separate Chrome
profile and records only its own textarea events. Use `x11_probe.py --help` for
explicit expected-window and cancellation options. For the standalone editor,
open a new temporary file using `gnome-text-editor --standalone`, inject into that
verified fixture and save it normally; compare its contents with the exact sample.

For native Wayland, open an **empty temporary document named exactly**
`InkEcho-isolated-wayland.txt` with `GDK_BACKEND=wayland gnome-text-editor --standalone`.
Run `python3 scripts/feasibility/wayland_probe.py editor --transport` only in this
laboratory fixture. It refuses nonempty targets and labels output transport-only.
`wayland_probe.py browser` and `terminal` report interface capabilities without
inserting anything. `portal_keyboard_probe.py --help` explains its explicit own PID
requirement; it must only be used with disposable fixtures and normal OS consent.

## Recommended implementation boundary

Continue core workflow/configuration/UI construction around the verified targeted
adapter, while keeping unsupported targets disabled with clear reasons. Do not
promote XTest, portal presence, or one GTK success into universal Linux support.
Finish native browser/terminal transport and hotkey investigations and the remaining
desktop matrix before claiming the complete product is accepted. A later supported
transport must retain cancellation and target checks and must never silently use a
clipboard or act as a system input method.
