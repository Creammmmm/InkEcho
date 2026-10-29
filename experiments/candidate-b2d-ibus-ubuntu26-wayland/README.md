# Candidate b2d: Ubuntu 26 GNOME Wayland explicit IBus

Candidate 0.10.2 AppImage SHA-256 `b2d47dee9295dadbbbff644e0f9553875ef7ac8971a97c56eec7de68d603c5d2` was extracted unmodified in an externally network-isolated Ubuntu 26.04.1 GNOME 50.1 QEMU snapshot; original disk/base and input share were read-only. Setup verifies matching hashes for all four package extension files and temporary installed copies. Run verifies package and app module hashes, active unlocked Wayland, enabled extension ACTIVE, and engine `xkb:us::eng`. No host desktop, user data, real audio, cloud credentials, clipboard or real input-method service was touched. The test SSH key remained on the host.

Actual packaged Session and explicit IBus output used synthetic audio and a local stub transcript of 200 fixed Chinese characters directed to owned GTK3 controls; raw `run.log` records:

- Full: 200 characters received, then `ibus_delivery_unknown` and failed outcome. Actual widget receipt establishes this sample only; IBus panel submission is not a generic end-to-end acknowledgement.
- Cancel: SIGUSR1 on first arrival produced a correct two-character prefix, two Commit calls, then cancelled; no later characters were observed during 1.3 seconds. The second may already have been dispatched before cancellation; this is not a physical Esc test.
- No-target: non-text button and window were confirmed focused/active before transcription returned, neither TextView received characters; 200 calls ended with uncertainty and failed outcome. This only covers that non-text control.
- Switch-ready: sender was stopped after first arrival; second TextView was confirmed focused and active before resuming. First and second received 2 and 198 characters, concatenating exactly. The outcome remained unknown/failed. This synchronized sample does not cover unpaused focus races.

Begin, Commit and Cancel replies had sender matching the session destination `:1.17`, and daemon identity replies came from `org.freedesktop.DBus`. No keyboard fallback was recorded. The old `passed` field is a Fcitx-specific assertion and is invalid for IBus; interpret captured characters and events instead. `commit_timeout` entries are configured call deadlines, not proof of actual timeouts. These targeted tests do not cover IBus auto-selection, browser/terminal, real audio/providers, physical shortcuts, arbitrary applications or full release acceptance.

For reproduction only in a disposable matching guest, copy the exact AppImage, `setup.sh`, `run.sh`, `probes/sender.py`, and `probes/target-focus.py` to a read-only 9p share tagged `inkecho_input`. Remove `.txt` from archived script filenames. Run setup, reboot guest, and run the test script. The extension is installed and enabled only in the disposable guest; guest provisioning is a prerequisite.

The temporary extension was disabled and removed; enabled extensions were empty. Guest poweroff completed, Docker wait returned 0 and the container was removed (`shutdown.log`).
