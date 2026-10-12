# Input preflight repair validation

Date: 2026-10-12, Asia/Shanghai.

## Observed defects and changes

- The application's recording entry point rejected every Wayland session before
  accessing a key or starting the microphone. This was a deliberate compatibility
  gate, but its generic status message was invisible with the settings window hidden.
  The blanket display check has been removed: Wayland now attempts experimental
  per-target AT-SPI validation, using the same unchanged active-window, focused
  editable-control, caret, epoch and cancellation checks as X11. A dedicated
  `Session.problem` signal now carries preflight and task errors to the UI, which
  presents a nonactivating notice. This is permission to try the guarded protocol,
  not a claim that the native Wayland workflow has passed acceptance.
- Preflight failures now emit fixed diagnostic identifiers. They never include
  API keys, transcript text, audio, or the raw provider response.
- A first recording request now awaits accessibility initialization, then checks
  whether it was cancelled, instead of starting a background connection and failing
  the request immediately.
- With polishing disabled, recording no longer loads its unused provider or prompt.
  A removed optional provider/template can no longer prevent transcription alone.

## Automated validation

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_application.py
.venv/bin/ruff check src/inkecho/app.py tests/test_application.py
.venv/bin/ruff format --check src/inkecho/app.py tests/test_application.py
```

Result: 15 orchestration tests passed; 22 passed together with platform tests. New regressions cover disabled polishing
with missing optional configuration, first-use connection, cancellation while the
input connection is pending, a guarded valid Wayland target reaching recording,
and an unsupported Wayland target producing a visible Chinese message before any
credential read or audio capture. These tests use controlled recorder/input/service doubles;
they do not establish native desktop or authenticated cloud compatibility.

## Native Wayland check and remaining limitation

The current desktop was Ubuntu 26.04 GNOME Wayland, active and unlocked. A disposable
GTK 3 TextView fixture was opened using `GDK_BACKEND=wayland`. The fixture exposed
`EditableText` but its window was not `ACTIVE` and its control was not `FOCUSED`.
The production `AccessibilityInput.capture_target()` refused the request with
`No active, focused editable target is available.` No text was inserted, no API
request was sent, and no clipboard was accessed. The fixture then exited.

This verifies safe refusal, not successful native input. No compositor focus or
permission restriction was bypassed. Native Wayland compatibility remains pending;
changing an API key cannot make an incompatible target editable. The isolated X11
focused-editor evidence in the feasibility report remains the proven application
input path. Browser and terminal controls without `EditableText` remain unsupported.

## Private native Wayland compositor investigation

```sh
PYTHONPATH=src .venv/bin/python scripts/feasibility/wayland_accessibility_probe.py
```

The diagnostic creates its own runtime/configuration/data directories, D-Bus
session, headless GNOME compositor, and empty GTK application window. GNOME 50.1
started successfully. Raw GTK-window and Gtk.Application variants both lacked
active/focused target state. Ordinary accessibility activation did not find an
operable owned-window thumbnail. A final private custom session mode with overview
disabled also failed the production capture check. The diagnostic exited nonzero
with `Isolated Wayland fixture did not gain safe focus`; no sample was injected.
All owned compositor/window children were terminated, and temporary directories
were removed. No OS permission or compositor focus restriction was bypassed.

The retained diagnostic is intentionally a failing acceptance probe on this setup;
it must not be counted as a passing Wayland input test. Native Unicode transport
was separately proven earlier, but complete focused native Wayland workflow,
focus-away/back and overlay retention remain pending. The experimental release
therefore refuses targets whose runtime checks cannot establish safety, rather
than rejecting every Wayland session before even checking its target.
