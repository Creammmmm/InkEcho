# Candidate b2d: isolated Fcitx testing on Ubuntu 24 and 26

Candidate AppImage 0.10.2 SHA-256 `b2d47dee9295dadbbbff644e0f9553875ef7ac8971a97c56eec7de68d603c5d2` was built from a 2026-10-29 06:45:54 +08:00 snapshot. `build.log` and `extract.log` preserve the build/extraction. Empty `package.diff` compares extracted package `packages/inkecho` against the full source snapshot; empty `worktree.diff` compares it to the working source at build time, excluding bytecode caches. These checks do not establish dependency/asset integrity or agreement with future edits.

Two independent, externally network-isolated QEMU snapshots mounted guest/base images read-only. The 24 guest changed its own disposable session from X11 to Wayland and rebooted; the 26 guest ran Wayland. Logs show active, unlocked sessions, candidate SHA and packaged module hashes. Packaged source was not overlaid. Private Fcitx configurations and synthetic data were used; no host desktop, user text, real credentials, clipboard, real audio or cloud provider were accessed. Test SSH keys remained on the host. Logs labelled `3507-*` belong to earlier SHA `3507bd52c52cf97f318e88a0bed5a0a3e4199b016e10ba784d89c9be0df24499`, before a subsequent connection cleanup fix; they are retained separately and do not constitute tests of b2d.

| b2d session | Auto and explicit Fcitx | Cancel | Simple control, zero-prefix fallback |
| --- | --- | --- | --- |
| 24 GNOME X11 | each exactly 200, succeeded | each one character | 200, succeeded |
| 24 GNOME Wayland | each exactly 200, succeeded | each one character | zero characters, failed `unsupported_compositor` |
| 26 GNOME Wayland | each exactly 200, succeeded | each one character | 200, succeeded |

The 26 Wayland fallback result has an obsolete `passed=false` from a probe that only recognizes X11 keyboard insertion; raw events show definite Fcitx no-target with zero accepted, hybrid authorization, 200 received characters and succeeded. In 24 Wayland the unsupported compositor is a real, retained failure. Cancellation uses SIGUSR1 after first receipt, not physical Esc; an already dispatched event cannot be retracted. Owned GTK controls, synthetic fixed text, and stubbed audio/transcription do not prove actual microphone, cloud, normal browser/terminal, arbitrary targets, physical shortcuts, unrestricted focus races, or complete release acceptance. These targeted tests are not the full dual-system package gate.

To reproduce only in equivalent disposable guests, copy the exact candidate, `probes/run.sh`, `sender.py` and `target-focus.py` to `/tmp/inkecho-r4-test/` and its `probes` folder; remove `.txt` from archived Python filenames. Run `bash probes/run.sh <full-SHA> x11` or `wayland` with the actual active unlocked guest session and correct DISPLAY/bus. The provided `guest-run.sh.txt` records the 9p-based launch used for 3507 and b2d 24 Wayland; b2d X11 and 26 Wayland reused the same probe in the same guests after replacing the package over SSH and checking session metadata. The scripts start a private Fcitx and alter guest-session environment: never use on a real desktop. VM provisioning was not independently verified from scratch here.

Both guests completed normal shutdown, each Docker wait returned 0, and the containers were removed (`shutdown.log`).
