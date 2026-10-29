# Candidate b5: real settings UI and ConfigStore on Ubuntu 24/26

Candidate 0.10.2 AppImage SHA-256 `b5fe22b632432453d85ef475b6b1ad2c575e6b2b7834b85b4db5338ae205d3c7` was checked and extracted unchanged in separate externally network-isolated QEMU snapshots. The original guest/base disks and input share were read-only. Ubuntu 24.04.5 ran active unlocked GNOME X11 with Qt xcb; Ubuntu 26.04.1 ran active unlocked GNOME Wayland with Qt wayland. Logs record package and application module hashes. This is the earlier b5 package, before the subsequent waiting-control failure fix; no claim is made for a rebuilt package.

The probes display actual packaged `CompatibilityPage`, `ConfigStore` and `Session`, with independent temporary configuration directories. They exercise widgets programmatically (not physical mouse/keyboard) in real desktop GUI sessions. `ubuntu24.log` and `ubuntu26.log` each record:

- Defaults `auto`, mapping wait 40 ms and feedback 40 ms. Saving IBus/75/60, reconstructing page/store, and reading same values passed. A running task kept IBus/75 despite subsequent control changes; the next task read keyboard/90.
- A separate writer process saved Fcitx/82/64 and exited; a second process loaded the same values successfully.
- An injected `OSError` from `save_settings` made the output method control return to the stored `auto` and show a save failure message. In the same test setting the mapping wait control to 75 showed 75 even though the file remained 40, also displaying the save failure message. This is a reproducible old-package UI inconsistency, not evidence about the later fix.

The first task probe substitutes recorder, authorization and credential lookup; failure is deliberately injected and not a real filesystem outage. No real user configuration, host input method, microphone, API, clipboard or real text output is touched. Real X11 timing behavior, physical controls, IBus/Fcitx delivery, Wayland presentation and complete package acceptance are outside this test. Neither the 40 ms setting nor this UI test establishes application rendering acknowledgement.

To reproduce only in matching disposable guests, put the exact candidate and scripts (remove `.txt` suffix from archived names) on read-only 9p share `inkecho_input`; run `guest-run.sh x11` or `wayland` on the corresponding active unlocked GNOME session. The runner checks the SHA, extracts without overlays, uses bundled Python/Qt and package application code, and cleans up temporary configuration. Guest provisioning is a prerequisite.

Both guests powered off normally, Docker wait returned 0 and both containers were removed (`shutdown24.log`, `shutdown26.log`).
