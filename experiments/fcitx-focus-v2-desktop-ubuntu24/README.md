# Fcitx v2 actual desktop candidate verification

## Ubuntu 24.04 actual Xorg / GTK3

The frozen v2 plugin built previously has SHA-256 `3a3c80fb464bbfce465b52cb73e998a00705998a768c45400416daf29e89a497`. The frozen Python bridge is from `/tmp/inkecho-fcitx-v2-native-lab/input/src`; this run never overlays shared repository code. The temporary overlay VM is `inkecho-fcitx-v2-native-lab`; original base/state mounts are read-only.

`run.py` creates a private D-Bus session daemon, loads only the production plugin (no synthetic-context addon), and starts two actual GTK3 Entry clients with process-local fcitx IM module selection. It waits at an explicit approval file until both owned blank windows and PID/start/XID are reviewed. Activation targets only these two owned XIDs. No simulated keyboard or clipboard is used.

`raw24/inkecho-fcitx-v2-desktop-run-r2/result.json`: PASS. One bridge sends A=甲, B=乙, A=丙丁, with actual client readback A=甲丙丁 and B=乙. A new bridge sends public 戊己庚, and its first-accepted callback invalidates continuation. After 1.253509 seconds, actual A contains exactly 甲丙丁戊, B exactly 乙. Each target and daemon original wait returned 0; original host tool session 36043 exited 0. This is explicit first-sent cancellation, not a physical ESC test.

## Preserved failures

- First launch failed before daemon or windows: guest `/tmp` was cleared on reboot, so frozen dbus-next/source/binary files had to be transferred again. Receipt: `candidate-transfer.json`.
- `raw24/inkecho-fcitx-v2-desktop-run/result.json`: readiness failed before any text was sent. An unused standalone Gtk.IMMulticontext reports null ID; fixture was corrected to inspect the actual Entry `im-module` and loaded `im-fcitx5.so` mapping. Failed target and daemon original waits both 0. Candidate plugin/source unchanged.
- Private GVfs emits a permission warning for an already-used runtime mount, but actual input and all owned process waits passed; no runtime mount/service changes were made.

## Limits and remaining work

This proves actual GTK3 fcitx frontend delivery under a private bus on an isolated Ubuntu24 Xorg desktop. Explicit module and owner selection do not prove system automatic detection, arbitrary applications, disabled/read-only/password controls, physical ESC, missing focus, ambiguous real-seat focus, or Ubuntu26 native Wayland. Those remain separate scopes. Private bus protocol no/multiple-focus and old/new compatibility were covered by the prior real Fcitx Core test, which is not substituted for real toolkit delivery here.

Ubuntu26 verification is pending the other owner releasing its actual VM. An unused empty child qcow2 header was created before that concurrent-owner warning; it was never booted and must not be used as a snapshot. See guest26/UNUSED.txt.
