# Ubuntu 24 GNOME Wayland Unicode compose comparison

On 2026-10-28 an isolated Ubuntu 24.04 GNOME Wayland session tested three
independently owned targets after standard keyboard-only RemoteDesktop portal
consent. The actual portal `ConnectToEIS` device sent the ASCII `b` and then
Ctrl+Shift+U, `4e2d`, Enter via key events. No clipboard, user applications,
input-engine switching or production code was used. The source runtime was
extracted from AppImage SHA-256
`e4f2c6de3450cd997607baaeba41dd1764f8365c0bda73d9b9dd7c4ac395db54`;
this is an exploratory test, not package acceptance.

| Owned target | ASCII observed | After compose | Scope |
|---|---|---|---|
| GTK 3 TextView | `b` | `b中` | GTK simple context specified only for the fixture |
| Qt 6 QTextEdit | `b` | `b中` | Qt Wayland fixture; existing session IBus configuration |
| GTK VTE 0.76 terminal | `b` | `b中` | test child process read the actual terminal bytes |

All three scripts and the standard-consent actions exited 0. The VTE child was
an owned raw-mode Python reader, not a shell or an actual CLI product; the Qt
fixture is QTextEdit, not an entire third-party application. The GTK/VTE
fixtures select `gtk-im-context-simple` only in their own process. Session
`QT_IM_MODULE=ibus`, `XMODIFIERS=@im=ibus`, and IBus was running; no change to
its engine was made. The exact Qt composition implementation was not traced,
so this does not prove which component performed it. The log field named
`gtk_unicode_compose_*` / `gtk_simple_ctrl_shift_u` is a fixed label inherited
from the earlier GTK probe: for the `qt` target it describes the same key
sequence and observed text, not evidence that Qt used GTK simple.

The EIS keymap had no direct `中` or emoji mapping, and the observer had no
modifier snapshot before timeout. Sending shortcut sequences is not a universal
Unicode protocol: unsupported applications may interpret the shortcut or the
hex digits and Enter as commands; focus changes during the sequence can split
it; existing modifiers or composition state can alter output. This experiment
cannot establish safe automatic use in arbitrary editors, browsers, terminal
shells, or Codex/Claude CLI. Do not enable it as a universal production
fallback based on this result. A future opt-in target-specific design needs
independent capability evidence, cancellation/partial-sequence handling and a
way to preserve existing input-method state; an uncertain sequence must not be
replayed.

Raw logs, exact scripts and keymap are retained here. Probe SHA-256
`bdda44ae646a987e1a2f44ac69e54cced414d678eccb1ab7df80d4b2b04e14e5`;
GTK, Qt and VTE logs respectively
`50ce50fd72d2b51a30e42b13c7ce3fe1a68c70a8e1ecdfc4286d71ea0dc3099a`,
`3f24de64614b2da4a6d5dc3e56122f4f9ffdc63d7e2c223c4f9191e762bbf6f1`,
`b1cdd4e0040e72d8259f5ee543db57484c3e847f9a36ffbfae2c49425206e888`.
Code files retain `.txt` suffix. Reproduce only in a disposable Wayland VM by
copying scripts without that suffix and the runtime AppImage to
`/tmp/wayland24-compose-r12/`, extracting it, setting the guest Wayland, D-Bus,
`PYTHONHOME`, `PYTHONPATH`, and `LD_LIBRARY_PATH` as in the previous
`../eis-r7/README.md`, and running bundled Python `eis_probe.py gtk`, `qt`, or
`vte` with fresh standard portal authorization for each. Test-owned window
focus is checked before the sequence. The guest GDM/account configuration was
restored and byte-compared, guest test files removed, and the VM normally shut
down with container exit 0 (`wayland24-compose-r12-restore.log`).
