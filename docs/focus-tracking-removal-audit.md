# Production focus-tracking removal audit — 2026-10-14

The revised requirement permits recording without an input target and allows
focus/caret changes throughout a task. Explicit cancellation, deadlines and stale
task IDs still stop unsent output. This audit checks production source separation;
it does not add new native desktop compatibility evidence.

## Removed from the product

`src/inkecho/platform/accessibility.py` was removed. Its AT-SPI event subscriptions,
background focus/caret verification, captured target/window/caret, focus generation,
consumed token and focus-loss cancellation policy are no longer in the production
source tree. `Session` continues to use `KeyboardInput`; no legacy fallback was
added. Platform detection no longer describes the removed AT-SPI policy.

The unchanged historical algorithm now lives in
[scripts/feasibility/historical_accessibility.py](../scripts/feasibility/historical_accessibility.py),
with an explicit historical header. Historical tests and owned-fixture diagnostics
import this test-only module. Pytest adds that directory to its test import path;
standalone validation scripts explicitly locate it. No production module imports
it. The AppImage builder copies only `src/inkecho` for the application and removes
all `__pycache__` directories, so neither the historical module nor stale source
bytecode is selected for the next package. No artifact was built in this audit;
final artifact absence must also be checked during release validation.

Earlier reports are unchanged. `accessibility_probe.py`,
`native_voice_workflow_probe.py` and `native_cloud_workflow_probe.py` depend on the
old captured-target Core/Session API. Their entry points now reject the current
API before starting desktop/fixture/cloud operations and explain that a historical
checkout/runtime is required. Import migration does not make these workflows
current-version acceptance. The older audio-feedback and voice-workflow scripts
also state their historical scope. Shared LocalProvider/TestSecret utilities are
still usable by current validation.

## Intentionally retained

The keyboard driver reads the current X11/XWayland recipient at emission time,
including after asynchronous waits. It does not subscribe to focus changes,
remember a recording-start recipient, or cancel merely because focus changes.
Each new character resolves the current recipient again. Its active-window/PID
and ancestry checks distinguish an actual supported X receiver from a native
Wayland proxy. The driver does not prohibit InkEcho's own windows. The window
retained for a key-release operation
belongs to that already-dispatched press; it does not bind subsequent text.

`Session.epoch`, task IDs, deadlines and notification generations protect against
explicit cancellation, replaced requests and stale callbacks. The notification
D-Bus subscription handles notification actions/closure, not window focus. UI
focus styling and nonactivating status windows do not track external targets.
Owned-PID/focus guards in feasibility and acceptance helpers are test confinement,
not shipped application policy. In particular, the current cursor workflow uses
the historical AT-SPI support only to inspect its owned fixture; text is sent by
the production keyboard backend.

## Checks

- Source search found no `capture_target`, `target_is_current`, `on_focus_lost`,
  `CaretOffset` or AT-SPI focus-event subscription in `src`.
- With only `PYTHONPATH=src`, Python cannot find
  `inkecho.platform.accessibility`. The three historical workflow guards exited
  with their explicit explanation before desktop startup.
- `PYTHONPATH=src .venv/bin/python scripts/validation/current_cursor_workflow_probe.py --help`
  loaded the current helper and its relocated fixture support successfully. This
  is an import/CLI check, not a rerun of native input acceptance.
- Focused historical-adapter/platform/keyboard/Session/core tests: **120 passed,
  1 skipped**. Complete offscreen suite with localhost fixture permission:
  **348 passed, 2 skipped in 5.37 seconds**.
- Ruff lint and formatting checks across `src`, `scripts`, and `tests` passed;
  `git diff --check` passed. No user configuration, microphone, cloud request,
  native window, version, artifact build or deployment changed in this audit.
