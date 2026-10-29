# Candidate b5: isolated Fcitx checks on Ubuntu 24 and 26

Candidate AppImage 0.10.2 SHA-256 `b5fe22b632432453d85ef475b6b1ad2c575e6b2b7834b85b4db5338ae205d3c7` was built from the 2026-10-29 07:25:19 +08:00 snapshot. `build.log` and `extract.log` record build and extraction. Empty `package.diff` compares extracted `packages/inkecho` against the complete source snapshot; empty `worktree.diff` compares the snapshot with working source at build time, excluding bytecode caches. These comparisons do not verify dependency/asset integrity or later edits.

Separate network-isolated Ubuntu 24.04.5 and 26.04.1 QEMU snapshots mounted original disks, bases and input share read-only. The 24 guest changed from X11 to Wayland only inside its temporary layer and rebooted; 26 ran Wayland. Logs identify active, unlocked sessions and recheck the exact package SHA, with packaged application source unmodified. The test used private Fcitx configuration, owned GTK3 controls, synthetic fixed text and stubbed recording/transcription; no host desktop, user text, real credentials, clipboard, microphone or cloud API was accessed. The disposable SSH key remained on the host.

| Session | Automatic / explicit Fcitx | Cancellation | Simple control zero-prefix fallback |
| --- | --- | --- | --- |
| Ubuntu 24 GNOME X11 | each 200 characters, succeeded | each one character | 200, succeeded |
| Ubuntu 24 GNOME Wayland | each 200 characters, succeeded | each one character | zero, failed `unsupported_compositor` |
| Ubuntu 26 GNOME Wayland | each 200 characters, succeeded | each one character | 200, succeeded |

The 24 Wayland fallback failure is real and retained: Fcitx reported no-target with zero accepted; keyboard fallback returned `unsupported_compositor`. The 26 Wayland fallback probe reports `passed=false` because its old assertion recognizes only X11 keyboard insertion; raw events show zero-prefix no-target, hybrid authorization, exactly 200 received and succeeded. Cancellation uses programmatic SIGUSR1 after first receipt, not physical Esc; dispatched input cannot be retracted. Results do not cover real speech, providers, terminal/browser, arbitrary target applications, unsynchronized focus races, or the complete dual-system release gate.

26 `wayland.log` preserves an initial SSH connection failure before the guest was ready; no test ran in that attempt. `wayland-retry.log` is the same guest and exact candidate after session readiness. To reproduce in comparable isolated guests, copy the candidate and probe scripts (remove `.txt` suffix from archived filenames) to a read-only share tagged `inkecho_input`, and run `guest-run.sh x11` or `wayland` after confirming active/unlocked session. Scripts assume UID 1000 and DISPLAY=:0, start a private Fcitx and change guest-only session environment; never run on a real desktop. Guest provisioning is a prerequisite.

Both guests powered off normally, Docker wait returned 0 for each, and both containers were removed (`shutdown.log`).
