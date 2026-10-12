# Foreground target identity repair

Date: 2026-10-12, Asia/Shanghai. Scope: the second shortcut repair after the
0.1.0a2 user screenshot showed GNOME Text Editor in front while InkEcho reported
that its own settings window was focused.

## Diagnosis and backend change

Qt's `QApplication.activeWindow()` describes application-local window state. It is
not authoritative proof of the desktop's currently focused process on Wayland.
The shortcut entry point must therefore allow the accessibility backend to capture
and validate the actual target instead of rejecting it from this cached pointer.

The backend now resolves each focused control's **unique AT-SPI bus name** using
the bus daemon's `GetConnectionUnixProcessID` method. It rejects InkEcho's own PID,
nonunique bus aliases, invalid process identifiers, and ownership lookup failures.
The accepted PID is stored with the target token. Each fresh target validation
before insertion verifies that the same external process still owns the bus name.
A disconnected target fails closed. No window titles or application-name guesses
are used to decide identity.

All existing active-window, focused/editable control, caret, generation,
cancellation and single-use checks remain intact. Own-process rejection occurs
before capture returns, so the application cannot reach key retrieval, microphone
capture or a cloud request for an InkEcho text field.

## Automated and native verification

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q \
  tests/test_platform_accessibility.py tests/test_application.py
```

Result: **28 passed, 1 skipped**. The skipped check requires a live desktop bus.
New regressions cover own-PID rejection, external-PID acceptance, invalid or failed
ownership resolution, a final ownership mismatch, and nonunique bus aliases. The
existing focus-change, late cancellation and UTF-8 insertion checks still pass.
Ruff lint and formatting checks passed for both modified files.

```sh
INKECHO_TEST_ACCESSIBILITY=1 PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_platform_accessibility.py::test_live_process_ownership_without_desktop_document_access
```

Result: **1 passed** against the native GNOME desktop's actual AT-SPI bus. The test
registered this test process and a disposable child connection, then verified:

- This process's real bus identity was rejected as an input destination.
- The child's real external PID was accepted.
- After the child exited, its disconnected identity was rejected.

The native test accessed only those two connection identities. It did not inspect
or insert into the user's document, create a desktop test window, use a clipboard,
read a credential, or contact a cloud service. This validates the changed ownership
boundary; it does not establish full native Wayland dictation compatibility.

## Remaining acceptance scope

The user's actual focused GNOME editor should now reach the authoritative backend
checks instead of the stale Qt-window rejection. The full editor/recording/cloud
workflow remains subject to real target focus, the target's `EditableText` support,
and provider configuration. No universal Wayland compatibility claim is added.
UI shortcut/notification validation is recorded separately below when completed.

## Shortcut dispatch and Wayland status UI

The shortcut handler no longer treats `QApplication.activeWindow()` as global
desktop focus. It hides stale auxiliary notices and dispatches to the authoritative
input backend, whose own-process rejection is described above. A retained Qt
window pointer can therefore no longer reject an external editor before its real
focus is checked.

During a Wayland voice task, recording, processing and errors use standard
`org.freedesktop.Notifications` messages. InkEcho does not map the error notice,
waveform overlay, or floating recording controls. It also no longer activates the
main window after an idle transition on Wayland. On X11 the existing auxiliary
windows remain available, and the delayed idle callback checks that a new task
has not started before showing settings.

Notifications replace the previous notification, include stop/cancel actions
where applicable, and use a two-second D-Bus deadline. Action tokens belong to a
notification generation and carry the exact task ID; delayed actions cannot stop
or cancel another task. A late notification reply cannot restore stale actions.
Shutdown requests `CloseNotification` before disconnecting. Notification service
failures retain an explicit status in the overview and never trigger an auxiliary
window or automatic clipboard fallback. Desktop notification actions depend on
the desktop's support; the shortcut can still stop recording and opening settings
provides a cancel control.

Focused automated validation:

```sh
.venv/bin/python -m pytest -q \
  tests/test_ui.py tests/test_notifications.py tests/test_startup.py
```

Result: **22 passed**. These tests cover dispatch despite a stale app-local active
window, no auxiliary or delayed main-window mapping on Wayland, replaced
notification IDs, old actions, late replies, shutdown cleanup, task ownership, and
preservation of the original error when the notification service fails.
The Qt UI tests use the offscreen backend; they do not establish compositor focus
retention. Ruff lint and formatting passed for the changed files.

Native GNOME notification protocol validation:

```sh
.venv/bin/python scripts/validation/notifications_probe.py
```

Result: `recording_accepted = true`, `completion_accepted = true`,
`notification_replaced = true`, `application_windows_created = 0`. This script
creates no Qt application or window. It sends a labeled test notification with
stop/cancel actions, replaces it, and closes it before exiting. No physical action
click was performed, and no target document was read. Acceptance by GNOME's
notification service does not by itself prove full dictation or notification
visibility when notifications are disabled by the user.

The earlier alpha2 check of `QApplication.activeWindow() is notice = false` was
only an application-local observation and is not compositor focus evidence.
