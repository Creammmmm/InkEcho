# Candidate 6d: isolated Ubuntu desktop output observations

Candidate `InkEcho-0.10.2-x86_64.AppImage` SHA-256 `6d537689d5e30f4611f1e8376025705bf5fcc26c9198c9cda7c51717d434e34a`, tested 2026-10-29. Logs and probe scripts are unmodified recordings of this candidate's runs; the package itself is not included. The evidence is a limited experiment, not complete release acceptance.

| Guest session | automatic / manual Fcitx full | cancellation | Fcitx focus switch / no-focus gap | simple control, zero-prefix fallback |
| --- | --- | --- | --- | --- |
| Ubuntu 24.04.5, GNOME 46, X11, Fcitx 5.1.7 | 200/200 each, passed | 1 and 2 characters, passed | 1+199 / 27+173, passed | 200/200, passed |
| Ubuntu 24.04.5, GNOME 46, Wayland, Fcitx 5.1.7 | 200/200 each, passed | 1 each, passed | 1+199 / 27+173, passed | 0 characters, `unsupported_compositor`, failed |
| Ubuntu 26.04.1, GNOME 50.1, Wayland, Fcitx 5.1.19 | 200/200 each, passed | 1 each, passed | 1+199 / 103+97, passed | 200/200, outcome succeeded; probe reports `passed=false` |

The final 26.04 sample reports false because this older probe identifies fallback only through the X11 `KeyboardInput.insert` method and doesn't recognize the native Wayland route; the original assertion is left unchanged. Its log independently records `no_target`, zero accepted, `hybrid_authorize`, outcome succeeded, and 200 received characters. The 24.04 Wayland fallback is a real failure, not a probe false negative. It records `no_target`, zero accepted, and `unsupported_compositor`.

The first 24.04 Wayland-labeled run (`6d-wayland.log`) was executed in an actual X11 session and fails to initialize GTK. It is invalid as Wayland evidence. The next first attempt (`6d-real-wayland.log`) failed because reboot cleared guest `/tmp`; the valid rerun is `6d-real-wayland-r2.log` after confirming Wayland, active, unlocked in `session-after-reboot.log`. Failure logs are preserved.

## Method and boundaries

Independent QEMU guest containers ran without network access outside their own container; the input images and snapshot base disks were mounted read-only, QEMU `-snapshot` used a disposable writable layer, and no source files in the package were replaced. The 24 guest was temporarily changed from X11 to Wayland and rebooted within that writable layer. Both test containers were removed after testing. The Fcitx bridge and configuration were staged inside the guest under disposable directories and removed by the probes. Synthetic `风云日月山川河海` repeated 25 times went through the packaged `Session` using a synthetic recorder and client; the sender instrumentation observes calls and targets fixed self-created GTK controls, not a genuine dictation workflow. The fake `probe-key` is a nonsecret test constant.

For reproduction, provision equivalent isolated guests with the specified desktop sessions, GTK3, Fcitx5, and test account. Copy the candidate to guest `/tmp/inkecho-r4-test/` and these files to `/tmp/inkecho-r4-test/probes/`. Confirm the actual session type, active state and lock state with `loginctl`; scripts use `XDG_RUNTIME_DIR=/run/user/1000`, display `:0` and the user session bus, and require adjustment for a different account. Then run `bash probes/run.sh <full-sha256> x11` or `wayland` and `bash probes/focus.sh <full-sha256> x11` or `wayland`. Both scripts verify the candidate SHA before extracting and running packaged Python, start a private Fcitx5, and clean up; run only in an isolated guest. `retry-wayland.sh` records the actual orchestration on this host and is not portable as written. Preparation, dependencies, and VM creation are prerequisites and were not independently rerun from scratch by this evidence.

No real microphone, cloud ASR, physical shortcut, Chrome, terminal, IBus, all target applications, Ubuntu 26 X11, or packaging update workflow was covered here. These observations do not establish complete project or release compatibility.

The archived Python probe files have a `.py.txt` suffix to preserve their exact executed bytes. When copying them to the isolated guest, remove the final `.txt` suffix so the original shell scripts find their expected `.py` filenames. Do not edit the scripts or historical logs.
