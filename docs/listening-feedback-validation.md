# Listening cancellation feedback validation

Date: 2026-10-13. Review of the affected application's existing metadata-only logs
showed recording/transcribing followed by cancellation, with no recorded reason.
The UI already had a focus-change message, but the cancellation path emitted only
a hidden status update: diagnostics and visible error notifications were limited
to the `FAILED` state. This report covers feedback, not the separate AT-SPI event
scoping repair in [listening-repair-validation.md](listening-repair-validation.md).

## Changed behavior

- A task cancelled because its captured target changed now emits the fixed
  diagnostic `target_changed`, even though its outcome remains `cancelled`.
- The user sees that focus or the caret changed, that input was cancelled, and
  that they should click the editor's text area before starting again.
- The same explanation appears when focus is lost during preparation after the
  target was captured, including while credentials are being obtained.
- Explicit user cancellation remains distinct and does not claim a focus error.
- Wayland posts the detailed reason through the existing desktop notification
  service. It does not first post a generic cancellation notification, map an
  auxiliary application window, or activate settings. The overview retains the
  reason when the controller returns to idle.

Only the fixed error code is logged. No target text, audio, transcript, credential,
window title, or application document content is added to diagnostics.

## Validation

```sh
.venv/bin/python -m pytest -q \
  tests/test_application.py tests/test_ui.py tests/test_logging.py
```

Result: **42 passed**. Ruff lint and formatting passed for the four changed code
and test files. The regressions exercise focus cancellation during recording and transcription,
captured preparation, explicit cancellation, and the Qt UI signal-to-diagnostic
path. They verify that recording stops, the controller returns to idle, text is
not inserted, the readable notification contains the focus reason, and the real
temporary diagnostic file records `ERROR error target_changed`.

These are isolated orchestration, offscreen Qt and temporary-file checks. They do
not establish native editor compatibility or authenticated cloud behavior. Native
event-scope and packaged application acceptance are recorded separately.
