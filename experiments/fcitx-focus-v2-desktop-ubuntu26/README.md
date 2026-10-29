# Fcitx focus v2 — actual Ubuntu26 native Wayland GTK verification

## Result and identity

PASS within the limited scope below. Ubuntu26.04.1, kernel7.0.0-38, real GNOME Wayland seat (loginctl Type=wayland Active=yes), Fcitx5.1.19-1 with GTK3 frontend5.1.6-1. `environment-receipt.json` preserves read-only observations. The original `inkecho-ubuntu26-release-vm` was stopped before the tested child overlay was created and remained stopped throughout; its state and base mounts were read-only in the new container `inkecho-fcitx-v2-wayland-lab`.

Identical actual v2 plugin binary as Ubuntu24: SHA-256 `3a3c80fb464bbfce465b52cb73e998a00705998a768c45400416daf29e89a497`. Actual frozen bridge SHA-256 `7bb21cfbff3b1fc44a5f0b5bdd719bfefe6adb0066730b477296831b30eb47d2`. Runtime dependency resolution is in `candidate-identity.json`. The frozen bridge source/deps are the earlier `/tmp/inkecho-fcitx-v2-native-lab/input/{src,deps}`; no shared worktree overlay, install, configuration or system environment was changed. No AppImage/package compatibility claim is made by this native addon/bridge test.

## Actual target delivery and cancellation

`raw/inkecho-fcitx-v2-native-wayland-run-r2/result.json` is the original result. A real GTK3 native Wayland window held two real Entry widgets, each explicitly selecting the fcitx input module for this process. `/proc/self/maps` confirmed the actual `im-fcitx5.so`. DISPLAY was absent; GDK display was `GdkWaylandDisplay`; WAYLAND_DISPLAY was wayland-0. No synthetic test-control InputContexts were loaded into the private Fcitx daemon.

The first approved fixed public sample used one bridge and real child focus changes A→B→A: A received 甲, B received 乙, A received 丙丁. Actual widget readback was exactly A=甲丙丁, B=乙. Each test-directed child focus change required window active and entry has_focus; no foreign focus was repaired.

A new bridge then attempted 戊己庚. Its first accepted callback invalidated continuation, invoking the production cancellation path. After 1.253602 seconds, actual widgets held exactly A=甲丙丁戊 and B=乙. No 己庚 appeared. This tests first-sent cancellation, not physical ESC. It does not make an unconfirmed transport acceptance into an application receipt: the separate actual GTK readback is the delivery evidence here.

The root reviewer viewed the owned blank control drawing and approved the sample, then viewed the final control drawing and readback. Images are GTK own-widget Cairo drawings, explicitly **not compositor captures** or proof of monitor presentation. Their hashes and host raw paths are in `screenshot-pins.json`; no full desktop image or user text was recorded.

## Preserved failures and cleanup

The first Wayland preparation failed before any text was sent: a fixture checked the older PyGObject class spelling `WaylandDisplay`, but this runtime reported `GdkWaylandDisplay`. Its real ready data already confirmed native Wayland, loaded fcitx module and active window. `raw/inkecho-fcitx-v2-native-wayland-run/` preserves that failure, and target/daemon original waits were both0. The fixture-only correction accepts these two explicit Wayland type names and uses a fresh target/work directory; candidate plugin and bridge were unchanged. The original script is `run26-r1-preserved.py`.

The successful original host owner session86680 exited0; target and daemon original waits both0. All owned target/sender processes were absent before a normal guest poweroff. Original docker wait returned0; final state exited0/Runningfalse/OOMfalse. `wait-and-cleanup.json` preserves tool evidence references and original container stopped state. An empty child header prepared before the concurrent backing-owner warning was never booted; it was discarded as an unused file, and a fresh overlay was created only after the backing owner confirmed normal shutdown. No running backing snapshot was used.

## Reproduction

Use only a disposable GNOME Wayland guest with this tested runtime and an owned desktop. Copy the frozen previous task's src/deps into `/tmp/inkecho-fcitx-v2/{src,deps}`, and the identical built plugin plus its configured descriptor into `/tmp/inkecho-fcitx-v2/product-native-build/`. Copy these scripts to `/tmp/inkecho-fcitx-v2-desktop/`. The existing target/work paths must be absent; do not remove another process's files.

Run `/usr/bin/env XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 XDG_SESSION_TYPE=wayland dbus-run-session -- /usr/bin/python3 /tmp/inkecho-fcitx-v2-desktop/run26.py`. It creates a private bus and private addon/config paths, then waits for `/tmp/inkecho-fcitx-v2-native-wayland-run-r2/approve`. Before creating that file, review the self-owned ready identity, empty control drawing, expiration and actual native backend. This gate authorizes only the fixed public sample. The harness uses a 180-second approval wait, 240-second target TTL, per-insert3-second deadlines and natural stopfile/daemon Exit cleanup. Do not use against a real user desktop or enter credentials. File transfer/build details are inherited from the separately retained native build/private-bus evidence.

## Scope limits

This extends the prior Ubuntu24 actual Xorg/GTK result with **Ubuntu26 native Wayland, two Entry controls within one owned window**. It does not validate native Wayland cross-window activation, arbitrary toolkit controls, Chrome/Electron/terminal IM behavior, password/read-only controls, system auto detection with an already-running daemon, actual keyboard fallback, native compositor text-input protocols, physical ESC, hardware microphone/cloud, or all seat-focus ambiguity cases. The earlier real Core/private-bus v1/v2 protocol tests cover no/multiple focus statuses and compatibility separately, not actual toolkit receipt in those cases. No clipboard is used. No silent general compatibility claim is justified. The original24 report's pending26 statement was a point-in-time status; this report completes only the limited new26 scope described here.
