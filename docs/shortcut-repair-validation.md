# Shortcut response repair validation

Date: 2026-10-12. Environment: Ubuntu 26.04 GNOME Wayland; Python 3.13.15,
PySide6 6.12.0. This report distinguishes configuration inspection, automated Qt
tests, and native desktop activation.

## Reproduced configuration mismatch

Read-only inspection found the application preference `shortcut = F4` while the
managed GNOME binding's `binding` value was the empty string. Its command still
pointed to the existing `dist/InkEcho-0.1.0-alpha-x86_64.AppImage --toggle`.
The path was present in GNOME's custom bindings list. Thus a displayed shortcut
preference did not mean that any key was actually registered. The existing
conflict detector reported no other GNOME assignment for F4. These checks read
only shortcut metadata, not credentials or document content; unrelated bindings
were not modified during diagnosis.

## Changes

- The primary recording-page action now saves and enables the shortcut. The
  secondary action explicitly saves recording settings only.
- Startup and the new check action inspect actual GNOME registration and report
  an empty binding, a different key, or a stale executable command. A late check
  cannot overwrite a newer enable result. Desktop reads and mutations share an
  asynchronous lock so enable and disable cannot race in worker threads.
- Cold-start IPC retains a toggle until initialization completes. Cancel and quit
  invalidate pending starts; quitting during initialization skips later UI checks.
- Session failures appear in a readable, non-activating notice even while settings
  are hidden. A tray notification is also requested when a tray is available.
  The last failure remains in the overview. The notice never reads the clipboard.

## Automated checks

Run from the checkout with local Qt audio and socket access:

```sh
.venv/bin/python -m pytest -q tests/test_hotkeys.py tests/test_startup.py tests/test_ui.py
```

Result: **33 passed**. This includes a real same-user Qt local socket delivering a
command before the handler attaches; a cancelled cold start; disabled and stale
GNOME settings using isolated test adapters; ordered enable/disable operations;
late health results; and a hidden
failure notice with the Qt offscreen backend. Offscreen widget tests verify notice
visibility and focus-prohibition flags, not native compositor behavior.

Ruff lint and formatting passed for all changed shortcut, startup and UI files.
The first sandboxed Qt run stalled while enumerating audio devices without local
service access; it was stopped, and the complete command above passed with local
service access. No live cloud request or credential access was part of these
checks.

## Native acceptance boundary

The notice was also launched directly on the actual Wayland desktop, without
opening a user document or changing focus: `platform = wayland`, `visible = true`,
and `QApplication.activeWindow() is notice = false` after 500 milliseconds. The
test notice closed automatically after 1.8 seconds. An initial `ToolTip` design
failed on Wayland because it lacked a parent surface; the accepted version uses
a frameless top-level `Tool` window with `WindowDoesNotAcceptFocus` and
`WA_ShowWithoutActivating`. No private compositor API or clipboard was involved.

The empty user binding still needs to be restored through the conflict-checking
adapter after package acceptance. A successful settings readback alone is not
evidence of a physical F4 key event. Native Wayland text input remains subject to
the input backend's independently documented compatibility and focus checks.
