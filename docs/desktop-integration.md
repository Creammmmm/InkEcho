# Desktop launchers and opt-in autostart

Construct `DesktopIntegration` with the absolute AppImage path, or for development
the environment Python executable and `args=("-m", "inkecho")`. `install` writes
the managed application-menu launcher and SVG/PNG icons at 16, 24, 32, 48, 64,
128 and 256 pixels. It does not enable autostart. `set_autostart(True)` is an
explicit separate user action; the startup entry adds `--background`.

The launcher follows `$XDG_DATA_HOME/applications`; icons follow the hicolor
theme beneath `$XDG_DATA_HOME/icons`. Autostart uses `$XDG_CONFIG_HOME/autostart`.
Relative XDG variables fall back to standard home locations. Executable paths
must exist and be executable. Arguments use desktop-entry quoting, including
spaces, literal percent signs, quotes, dollar signs and backslashes; no shell is
invoked. [Freedesktop Exec specification](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html).
The launcher dispatches through `/usr/bin/env --` without a shell because GIO
checks an executable before expanding escaped percent signs in its filename.
Optional desktop/icon cache tools are refreshed with a three-second timeout;
missing or failed cache tools do not block managed-file updates.

`status` reports installation, whether the launcher matches the current path,
and autostart state. After moving an AppImage, open it at its new path and choose
`repair`; both the launcher and an already-enabled autostart entry are updated.
Repair never turns on a previously absent autostart entry. `remove` deletes
only marked launchers and icons matching the bundled bytes, preserving unrelated
files, changed icons, application settings, statistics and system credentials.
There is no keyring access in this module. Conflicting files or symbolic links
are preserved and produce an explicit error instead of being overwritten.

Reproduce the isolated checks:

```sh
uv run pytest -q tests/test_integration.py
```

The tests use temporary XDG directories and a harmless temporary executable.
They validate menu/autostart files with `desktop-file-validate`, inspect all
eight icon resources, move/repair an executable with spaces, toggle autostart,
and remove integration while preserving a user configuration file and unrelated
content. The GIO launch test checks real argument delivery with reserved
characters. This verifies generated launcher behavior; it does not prove a full
desktop login/autostart cycle or the final packaged application startup.
Measured on 2026-10-12: seven tests passed, including actual GIO argument delivery
with spaces, percent, quotes, backslashes and dollar signs in both executable
path and arguments. The real launcher test requires `gio` and
`desktop-file-validate`; it is explicitly skipped if either tool is absent.
