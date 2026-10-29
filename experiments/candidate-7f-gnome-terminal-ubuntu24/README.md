# Candidate 7f: Ubuntu 24 Wayland GNOME Terminal

This is the earlier candidate AppImage `0.10.2`, SHA-256 `7f4039504d710c9e13a10cb826c3753c11517b0550ebfbc9bd01631b26de1f97`; later source changes are not included. Ubuntu 24.04.5, GNOME 46.0, Fcitx 5.1.7, and GNOME Terminal 3.52.0-1ubuntu2 were verified in `terminal.log`; the desktop was Wayland, active and unlocked. The terminal server's own Wayland/XWayland backend was not established. A network-isolated QEMU snapshot mounted the original disks and input share read-only, and was switched from X11 to Wayland only in the temporary guest layer. The candidate was checked and extracted without overlays. The private Fcitx profile, synthetic text and dummy key were isolated; no host desktop, user content, real credentials, clipboard, real audio or cloud provider was accessed.

The real GNOME Terminal launched a custom raw-mode Python reader rather than a normal shell. Packaged Session used a synthetic transcript of 200 Chinese characters and stub recording/transcription. Each Fcitx Commit reply was artificially delayed 25 ms in the sender process; this is not a speed test. In `terminal.log`:

- `full`: terminal reader received the exact 200 characters and the task succeeded.
- `cancel`: upon first received character, a SIGUSR1 triggered cancellation; the terminal contained the same one-character prefix at cancellation and after completion, with cancelled outcome. It does not test a physical Esc key or prove in-flight messages can be recalled.
- `switch`: the sender was stopped after one character, a second terminal was opened, then sending resumed after its reader was ready and two seconds elapsed. The terminals received 1 and 199 characters, concatenating to the exact transcript; task succeeded. Second-window focus was not separately measured; actual second-reader receipt proves this sample only, not arbitrary focus races.

Fcitx's Commit success is an attempted delivery, not a general target receipt acknowledgement. These tests do not cover real microphones or cloud, actual shell/CLI applications, browser, unpaused focus races, Ubuntu 26, or complete release acceptance. Retain raw logs without treating this older candidate as the latest source.

To reproduce only in a comparable isolated guest, copy the exact AppImage and the archived probe files to a read-only 9p share tagged `inkecho_input`, removing `.txt` from their filenames. Execute `guest-run.sh` after verifying an active unlocked Wayland session. Guest provisioning is a prerequisite; its scripts start a private Fcitx service and modify test-only environment. Never run against an ordinary desktop session.

The guest shut down normally, Docker wait returned 0 and the temporary container was removed (`shutdown.log`). The test SSH key remained on the host.
