# Lightweight control command validation

Date: 2026-10-20. This is Ubuntu 26.04 source validation, not AppImage or
Ubuntu 24.04 package acceptance.

## Change

Every GNOME shortcut invocation starts an InkEcho command process. Even with an
existing background service, the entry point previously imported the main window,
audio, provider HTTP clients and asynchronous GUI runtime before forwarding the
command. This delayed the request reaching the already running recorder.

The `--toggle`, `--cancel` and `--quit` paths now use QCoreApplication and import
only QtCore / QtNetwork plus the configuration-root helper. They retain the same
same-user socket name, protocol, lock and no-cold-start behavior. Explicit GUI
startup loads QtGui / QtWidgets, fonts and application identity; Session, audio,
providers and main-window imports occur only when the service starts. Control
errors print a fixed message to stderr, without exception details, config paths
or a dialog. A closed settings window still leaves the tray service running;
a complete exit still prevents a shortcut from restarting the service.

## Measurements

Five separate Python processes per condition executed the same source command:
`runpy.run_module('inkecho', run_name='__main__')` with `--toggle --config-dir`
pointing at a fresh private directory. HOME and all XDG directories were private;
no instance existed and no configuration was initialized. The timer starts
immediately before running the entry module and stops when it returns, so it
includes module imports and local control handling but excludes interpreter
startup, GNOME dispatch, AppImage mounting and actual recording/recognition.
These are warm-file-cache development-host observations, not a microphone or
end-to-end latency claim.

| Condition | Five durations (ms) | Median (ms) |
| --- | --- | --- |
| Before | 126.17, 125.69, 127.49, 130.43, 127.40 | 127.40 |
| After | 54.48, 46.39, 46.04, 47.30, 46.74 | 46.74 |

The measured median decreased by 80.66 ms (63.3%) for this isolated command path.
A separate imports-only QtCore / QtNetwork baseline was about 39.4 ms; it was
never treated as an implemented command result. Before, sys.modules contained
QtGui, QtWidgets, QtMultimedia, inkecho.app, inkecho.audio, inkecho.ui.window,
inkecho.providers, httpx and qasync. After, all were absent; QtCore and QtNetwork
were present. Local raw metadata is retained in
`build/audio-onset-exit-preparation/control-import-timings-r1.json` and `-r2.json`.

## Reproducible checks and actual results

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_startup.py tests/test_hotkeys.py
.venv/bin/ruff check src/inkecho/__main__.py tests/test_startup.py
.venv/bin/ruff format --check src/inkecho/__main__.py tests/test_startup.py
```

28 tests passed in 1.26 seconds; Ruff lint and formatting passed. Tests cover real
private Qt local-socket forwarding, commands queued during startup, cancellation,
a deliberate real offscreen background instance receiving quit and exiting,
and a later toggle returning without recreating its service or modifying config.
Fresh control subprocesses also run with an intentionally unavailable GUI plugin:
all three control actions exit successfully without loading GUI/audio/provider
modules. An injected control error exits 1 with only the fixed error message.

No real user config, credentials, system shortcut binding, physical microphone or
cloud service was used. Actual Ubuntu 24.04 and packaged command latency require
separate evidence. This optimization does not make the ASR model more accurate
or make a non-streaming protocol emit partial text.
