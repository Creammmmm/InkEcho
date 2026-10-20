# Shortcut commands after a complete exit

Date: 2026-10-20. Source validation, before packaging; no AppImage or dual-system
acceptance is claimed by this report.

## Cause and behavior

GNOME custom shortcuts retain an executable command after the application exits.
The existing command ends in `--toggle`. Previously the single-instance entry
point acquired a free lock, created a server and started the entire application
when that command found no running instance. This was a cold launch, rather than
an exited background process still recording.

`--toggle`, `--cancel` and `--quit` now only address an existing instance. If the
instance lock is free they immediately release it and return successfully without
creating a local server, initializing configuration, constructing a Session or
starting microphone/network work. Existing GNOME `--toggle` registrations remain
compatible; users need not reassign the shortcut. Deliberate launcher / `--show`
and `--background` startup still acquire the service normally. Commands arriving
while an explicitly launched instance initializes remain queued until ready.

Closing the settings window still hides it to the tray (or minimizes when no
tray is available). That is not a complete exit, so its running background
instance continues to accept the shortcut. A complete tray exit / `--quit`
releases the service; subsequent shortcut commands cannot restart it. This fix
does not unregister or modify another application's GNOME settings.

## Reproducible checks and actual results

On the Ubuntu 26.04 development host, using the repository Python environment:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_startup.py tests/test_hotkeys.py
.venv/bin/ruff check src/inkecho/__main__.py tests/test_startup.py
.venv/bin/ruff format --check src/inkecho/__main__.py tests/test_startup.py
```

26 tests passed in 1.41 seconds; Ruff lint passed. The tests use private temporary
configuration / runtime / data / cache / state directories and actual Qt local
sockets. They verify:

- No-instance control commands terminate with status 0 and create no config or
  runtime entries; a later deliberate startup still acquires the lock.
- An already running local server receives `toggle` through the real socket;
  startup queues and cancellation ordering remain intact.
- An actual offscreen `python -m inkecho --background` subprocess creates its own
  private configuration, receives `--quit`, and terminates normally with status 0.
  A subsequent `--toggle` subprocess also terminates normally, leaves every
  config file timestamp unchanged, leaves no instance lock, and adds nothing to
  the runtime directory. The initialized audio library may leave its private
  PulseAudio directory; this is compared unchanged rather than removed.
- Existing shortcut command quoting, registration and conflict checks still pass.

Sandboxed first execution could not create the Qt lock/socket in the host runtime;
the same tests passed with the approved local-socket permission. During test
development the real-process readiness check initially used the wrong config
filename; after correcting it, a second assertion exposed the expected private
PulseAudio directory. The final checks explicitly distinguish that directory
from the application's lock and check runtime contents before/after the toggle.

No real user configuration, credentials or system shortcut settings were read or
changed. No physical keypress, real microphone capture, cloud request, Ubuntu
24.04 desktop session, packaged executable or tray GUI is established by these
headless source checks. Package / desktop acceptance must be recorded separately.
