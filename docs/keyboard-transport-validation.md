# Current-focus keyboard transport validation — 2026-10-14

This validates the user's revised output-time keyboard semantics. It does not
claim compatibility with native Wayland editors or prove delivery in the user's
existing Codex window. All injected text belonged to newly created fixtures;
no clipboard, input-method registration, user document or credential was used.

## Actual platform and phase-0 findings

GNOME Wayland; XWayland `24.1.10` (package `2:24.1.10-1`), GTK
`3.24.52-0ubuntu1`, Chrome `154.0.8037.97` with a fresh disposable profile and
`--ozone-platform=x11`.

- Keyboard-only RemoteDesktop portal consent succeeded, but the fixed 28-codepoint
  Unicode sample produced only 15 ASCII/newline characters. Mutter 50.1's
  [native keyval implementation](https://raw.githubusercontent.com/GNOME/mutter/50.1/src/backends/native/meta-virtual-input-device-native.c)
  looks up existing symbols in the current keymap and skips missing ones.
- XTEST on this host uses XWayland's `-enable-ei-portal` route. Its pending
  remote-desktop authorization was explicitly cancelled through the ordinary
  dialog. This route was not adopted.
- XSendEvent with a core KeyPressMask delivered no GTK characters. An existing
  `a` keycode and NoEventMask delivered a synthetic event and exact `a` without
  any mapping changes. NoEventMask sends to the selected window's owning client.
- The final XSendEvent probe received all 28 Unicode codepoints in both owned
  GTK and Chrome text fields. Chrome initially omitted the newline when Return
  occupied the temporary character slot. Using the existing Return keycode
  fixed this; the final comparison included the newline and passed.
- The final probes restored only their originally empty slot (248 in these
  runs). Whole-map comparisons normalized trailing NoSymbol entries and passed,
  with no changed keycodes. An earlier whole-map byte comparison failed.
  Canonical width differences are a possible explanation, but its original
  snapshot was not retained, so the cause cannot be confirmed. A subsequent
  read found no remaining U+3002 last-sample symbol. That earlier attempt is
  not described as a successful restoration; later runs retained complete
  snapshots and passed normalized comparisons.

The final Unicode probe persists a keymap-only recovery snapshot in `/tmp`
before modifying its own empty slot. Production never persists text/keymap
snapshots and never resets the entire keymap.

## Production backend, not just a prototype

`KeyboardInput` uses ctypes/Xlib, not an `xdotool` text command. Supplied text
never enters subprocess arguments. It refreshes InputFocus and active-window
ownership after mapping waits; beginning a recording does not inspect focus.
A native Wayland fixture changed X focus to a Mutter proxy with no window PID,
which is rejected instead of sending to the historical XWayland window.

The production probe passed all of these on the real desktop:

```json
{"unicode_count":28,"production_unicode_exact":true,
 "switch_first_exact":true,"switch_second_exact":true,
 "cancel_code":"input_cancelled","cancel_one_press_one_release":true,
 "cancel_no_tail":true,"closed_window_code":"injection_failed",
 "map_restored":true}
```

It sent the fixed Unicode sample, changed between two owned editors after the
first character, cancelled after one press, and tested BadWindow using an
unmapped resource created/destroyed on the backend's still-live X connection.
All fixtures and connections were closed. No pending portal authorization is
needed by this backend.

Reproduce only in disposable owned fixtures on an unlocked desktop:

```bash
PYTHONPATH=src LD_LIBRARY_PATH="$PWD/build/listening-test-tools/root/usr/lib/x86_64-linux-gnu" \
  .venv/bin/python scripts/feasibility/xwayland_unicode_probe.py \
  --fixture chrome --transport xsend --owner-mask \
  --xdotool "$PWD/build/listening-test-tools/root/usr/bin/xdotool"
PYTHONPATH=src LD_LIBRARY_PATH="$PWD/build/listening-test-tools/root/usr/lib/x86_64-linux-gnu" \
  .venv/bin/python scripts/feasibility/keyboard_backend_probe.py \
  --xdotool "$PWD/build/listening-test-tools/root/usr/bin/xdotool"
.venv/bin/pytest -q tests/test_keyboard.py
```

The helper executable/library are existing cached test dependencies, not new
system installations or production dependencies. Focused result: **22 passed**;
Ruff passed for the backend, tests, and added/modified feasibility scripts.

Tests cover cancellation at asynchronous boundaries, current-focus refresh,
close/busy behavior, whole-string control-character rejection, Return handling,
owned-slot restoration, foreign layout preservation, failed mapping readback,
canonical width changes, and preserving another display's X error handler.

Successful XSendEvent submission cannot acknowledge arbitrary applications'
editing behavior. Native GTK and Chrome fixture contents were separately
checked; application behavior outside those fixtures remains a compatibility
boundary. Full microphone/provider/UI/package results are recorded separately in
[current-cursor input validation](current-cursor-input-validation.md).

## Owned terminal / raw PTY

The same production `KeyboardInput` passed an additional native XWayland VTE
fixture on 2026-10-14 (`libvte-2.91-0` and `gir1.2-vte-2.91` version `0.84.0-2`).
Its child runs only Python `tty.setraw` and `os.read`; it never starts a shell.
Every press was gated to the newly created terminal's PID and current focus.

```json
{"sent_codepoints":28,"raw_utf8_with_return_exact":true,
 "unicode_content_exact":true,"carriage_returns":1,"line_feeds":0,
 "expected_bytes":53,"received_bytes":53,"native_xwayland":true,
 "shell_started":false,"clipboard_used":false,"map_restored":true}
```

The Return key produces CR (`0x0d`) in this raw PTY, rather than LF (`0x0a`).
The expected byte sequence explicitly accounts for that terminal protocol;
normalizing CR to LF also matches the fixed Unicode sample exactly. This is a
terminal keyboard result, not silent character loss or literal-LF injection.
The terminal, byte receiver, and connections were cleaned up. The application
source and existing alpha7 artifact were unchanged by this additional test.

```bash
PYTHONPATH=src LD_LIBRARY_PATH="$PWD/build/listening-test-tools/root/usr/lib/x86_64-linux-gnu" \
  .venv/bin/python scripts/feasibility/terminal_keyboard_probe.py \
  --xdotool "$PWD/build/listening-test-tools/root/usr/bin/xdotool"
```

Both added terminal scripts passed Ruff and compilation checks. The terminal
result joins the new-route browser and editor evidence; old XTEST results were
not reused as evidence for this backend.
