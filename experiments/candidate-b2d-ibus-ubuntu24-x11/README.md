# Candidate b2d: Ubuntu 24 GNOME X11 explicit IBus

AppImage SHA-256 `b2d47dee9295dadbbbff644e0f9553875ef7ac8971a97c56eec7de68d603c5d2` was checked twice and extracted unmodified in an externally network-isolated Ubuntu 24.04.5 GNOME X11 QEMU snapshot. Original guest/base disks and input share were read-only. `setup.log` records matching hashes of the package's extension and its temporary installed copy; `run.log` records an active unlocked session, enabled extension `ACTIVE` and IBus engine `xkb:us::eng`. No host session, input method, user data, clipboard, real audio or provider credentials were accessed. The test SSH key stayed on the host.

The actual packaged Session and explicit IBus route used synthetic audio, local stub transcription of 200 fixed Chinese characters and owned GTK3 TextViews. Raw `run.log` records:

- Full: first TextView received all 200 characters; 200 Commit calls then `ibus_delivery_unknown` and failed outcome. Widget receipt proves this case only, not generic delivery acknowledgement.
- Cancel: a signal after first text arrival yielded a correct two-character prefix, two Commit calls, and cancelled outcome; no later character appeared during the 1.3-second settling interval. The second might already have been dispatched before cancellation; this is not a physical Esc test.
- No-target: a non-text button and its window were confirmed focused and active before sending; both owned TextViews remained empty. 200 Commit calls ended in the same uncertainty diagnostic and failed outcome. This only covers the tested control.
- Switch-ready: the sender was stopped after first arrival, second TextView focus and active window were confirmed, then sender resumed. TextViews contained 2 and 198 characters, concatenating to the expected input. The application still reports unknown receipt and failed outcome. This deliberate synchronization does not cover unpaused focus races.

Begin, Commit and Cancel replies had sender matching destination `:1.37`; owner query replies came from `org.freedesktop.DBus`. No keyboard fallback is recorded. The legacy `passed` field is a Fcitx-specific assertion and is invalid for these IBus samples; use actual contents and events. `commit_timeout` entries indicate configured call timeouts, not actual timeout or target receipt. These are targeted samples, not dual-system package acceptance, and do not cover a real microphone, cloud API, terminal/browser, physical shortcut, IBus auto-selection or arbitrary applications.

To reproduce only in a matching disposable GNOME X11 guest, put the candidate as `candidate.AppImage`, `setup.sh`, `run.sh` and `probes/ibus-sender.py`, `probes/ibus-target.py` in a read-only 9p share tagged `inkecho_input`. The archive appends `.txt` to script names; restore the original names when copying. Execute setup, reboot the guest, then run the probe script. Setup installs the candidate's extension only in the disposable guest. Guest provisioning is a prerequisite.

The temporary extension was disabled and removed, the enabled extensions list was empty, the guest powered off normally, Docker wait returned 0, and the container was removed (`shutdown.log`).
