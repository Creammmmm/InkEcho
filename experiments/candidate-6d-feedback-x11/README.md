# Candidate 6d: X11 draw hints and timeout lower bound

2026-10-29, candidate AppImage SHA-256 `6d537689d5e30f4611f1e8376025705bf5fcc26c9198c9cda7c51717d434e34a`. Ubuntu 24.04.5 GNOME X11 and Ubuntu 26.04.1 XFCE X11 were separate QEMU snapshots with original disks and base read-only, private guest configurations and Fcitx bridge, no external network or real credentials. Both candidate extractions were unmodified; only the standalone test sender monkeypatches the packaged pacer in its own process to record observation/await timings, and, in explicitly marked control cases, suppress accepted hints. Each test uses a synthetic 16-character transcript and self-created GTK3 simple-context controls. Fcitx reports `no_target` with accepted=0, then automatic routing uses X11 keyboard fallback; all eight samples output the exact 16 characters and report succeeded.

| Guest | Config | Hint suppression | Accepted draw hints | Full-window waits | Observed full-window duration |
| --- | --- | --- | --- | --- | --- |
| 24 GNOME X11 | 40 ms | no | 9 | 9 with hints | 0.0–28.7 ms |
| 24 GNOME X11 | 40 ms | yes | 0 | 15 without hints | 40.2–41.2 ms |
| 24 GNOME X11 | 80 ms | no | 9 | 9 with hints | 0.0–15.4 ms |
| 24 GNOME X11 | 80 ms | yes | 0 | 3 without hints, then NONE | 80.3–80.9 ms before downgrade |
| 26 XFCE X11 | 40 ms | no | 9 | 9 with hints | 0.0–4.4 ms |
| 26 XFCE X11 | 40 ms | yes | 0 | 15 without hints | 40.1–41.2 ms |
| 26 XFCE X11 | 80 ms | no | 9 | 9 with hints | 0.0–1.3 ms |
| 26 XFCE X11 | 80 ms | yes | 0 | 15 without hints | 80.4–81.4 ms |

An accepted draw hint is only weak scheduling evidence, not a per-character draw, a physical frame, actual presentation, or acknowledgement that an application consumed the character. Existing hints can arrive before the observed wait begins, producing near-zero wait. The suppression cases deliberately alter observation to exercise timeout behavior and do not represent natural desktop behavior. The 24/80 suppression sample moved from DRAW to NONE after three waits; its reason was not recorded and is not inferred. Timing includes any other work inside `before_send`, not isolated presentation timing. Normal draw tests remain small fixed samples and do not prove general performance or visual smoothness.

On 24, initial hardcoded `loginctl` session 1 reported `Type=tty`; the controller stopped before input. `failed-session1.log` and `sessions.log` preserve this; session 4 was then confirmed X11, active and unlocked in `inventory.log`, and only then was the test run. Both containers were stopped and removed after testing. `test-final.log` records 182 offline tests passing against an independent current-source copy; initial `test.log` and `test-retry.log` each record 181 passes and one setup error because a synthetic-provider helper was not on the test path. Those runs and the final corrected run are not desktop timing measurements.

Code review: `x11_feedback_timeout_ms` is read from the settings snapshot at task start, forwarded to the keyboard adapter, and controls only the DRAW dynamic timeout floor. X11 DRAW is conditional on availability of XSync/XDamage and can fall back to NONE; XWayland observation is disabled by default. Native Wayland uses INPUT request timing, and Fcitx/IBus direct submission do not use the X11 feedback setting. The keyboard route may use it after a zero-prefix Fcitx fallback. None of these imply a presentation receipt. The UI description improvement was prepared separately at `/tmp/inkecho-feedback-ui.patch`; it is not part of candidate 6d or this evidence.

To reproduce in an isolated guest, copy the exact candidate to `/tmp/inkecho-r4-test/` and the three probe scripts into `/tmp/inkecho-r4-test/probes/`. Use `ubuntu24/run.sh` for GNOME X11 or `probes/run.sh` for XFCE X11 and run it with the full candidate SHA and `x11` from `/tmp/inkecho-r4-test`. Adjust UID, DISPLAY and session bus to the test guest; these scripts start a private Fcitx service and temporarily alter user-manager input-method environment, so never run them on the real user desktop. VM provisioning and all user-facing settings interactions were not reproduced here. No physical Esc, real microphone, cloud provider, actual browser/terminal, real app rendering or native Wayland presentation were measured; this is not release acceptance.

The archived Python probe files have a `.py.txt` suffix to preserve their exact executed bytes. When copying them to the isolated guest, remove the final `.txt` suffix so the original shell scripts find their expected `.py` filenames. Do not edit the scripts or historical logs.
