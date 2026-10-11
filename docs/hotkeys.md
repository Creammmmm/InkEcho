# Global shortcuts

InkEcho's GNOME adapter uses the public GSettings custom-keybinding schema. It
requires GNOME's media-keys service and the `gsettings` command, without sudo.
Creating the adapter or opening the app does not change desktop settings. The
application must call `enable()` only when the user explicitly saves/enables a
shortcut; a matching disable action removes only InkEcho's registered path.

The owned path is
`/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/inkecho-voice-input/`.
Existing custom binding paths and their order are retained. A known shortcut
collision in existing custom bindings or standard GNOME media/window/mutter/shell
schemas is reported before writing. Another owner's binding in the InkEcho path
is not overwritten. Unknown extensions may reserve additional shortcuts, so passing
the settings check does not prove that a physical key will activate successfully.

Accepted forms include `Ctrl+Alt+K`, `Ctrl+Shift+Space`, `Super+F13`, `F13` and `F14`.
Keys F1–F35 are preserved. A plain letter/number/Space without a modifier is rejected
to avoid consuming ordinary typing. The app debounces incoming toggle commands.

Pass an argument list whose first item is an existing absolute executable:

```python
GnomeShortcuts().enable("F13", [appimage_path, "--toggle"])
GnomeShortcuts().disable()
```

For a source installation use the absolute environment Python followed by
`-m`, `inkecho`, `--toggle`. Commands are quoted with `shlex.join`, never assembled
by interpolating a shell string. `--toggle` must notify the existing app instance
without focusing its settings window; that instance captures the current input
target. UI callers should run settings operations in a worker via `asyncio.to_thread`
so conflict checks cannot stall recording, cancellation or animations.

## Actual local verification

2026-10-12, Ubuntu 26.04.1 GNOME Wayland:

- Temporary F13, F14 and Ctrl+Alt+K bindings saved and read back correctly.
- Each stored command was parsed and launched directly; its own temporary marker
  confirmed that executable paths/arguments were valid. **This was not a global
  key activation test.**
- Original parent settings and owned keys were restored exactly, including whether
  a key originally used its default rather than a user override.
- At the subsequent native key test, `loginctl` reported `LockedHint=yes` and the
  standard RemoteDesktop portal refused creation with `Session creation inhibited`.
  The test did not unlock the desktop or bypass that restriction. Native synthetic
  activation and physical key presses remain pending.
- Independent Xvfb synthetic shortcut results are recorded in the feasibility
  report; they do not establish GNOME Wayland activation.

Reproduce only on your own desktop, knowing these probes temporarily change the
owned shortcut and then restore it:

```bash
PYTHONPATH=src python3 scripts/feasibility/gnome_shortcut_probe.py --settings-only
PYTHONPATH=src python3 scripts/feasibility/gnome_shortcut_probe.py
```

The first command tests settings/readback and directly launches the marker
commands. The second requests normal keyboard-only, nonpersistent portal consent,
then sends only the registered own test shortcuts; it reports actual activation
and restoration separately. It refuses to replace an already installed InkEcho
binding during the test. The system Python needs `dbus-python` and GObject
introspection. A failed/locked portal returns a nonzero exit without claiming success.

## Other desktops and manual configuration

If the GNOME schemas/service are unavailable, report that automatic registration is
unsupported. The user can configure their desktop's own custom shortcut to launch
the absolute AppImage path with `--toggle`; desktop settings or an external keyboard
utility may then provide F13/F14 handling. The app must not silently replace the
failed backend with an X11 hook on Wayland. Physical activation, conflicts, keyboard
layout and desktop policy still need testing on each supported environment.
