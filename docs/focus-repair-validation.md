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
