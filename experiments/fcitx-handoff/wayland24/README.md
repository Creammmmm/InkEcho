# Ubuntu 24.04 native Wayland handoff preflight

On an isolated Ubuntu 24.04.5 GNOME Wayland desktop, the r6 AppImage was extracted and its Fcitx bridge module overlaid with SHA-256 `8cd26a449056d65d9d08cb1c087c26a4d29c00bf8108a4d6f408ff7b2a28494e`; the AppImage SHA-256 was `e4f2c6de3450cd997607baaeba41dd1764f8365c0bda73d9b9dd7c4ac395db54`. In two self-owned GTK entries, Fcitx committed fixed synthetic `甲`, focus moved to a simple entry, and the following Fcitx `乙` was not committed before its deadline. The extracted package's `WaylandKeyboardInput` failed authorization with `cleanup_pending`, so no keyboard character was sent; the Fcitx entry contained `甲`, the simple entry remained empty. Raw output `build/handoff-review/wayland24-r1/cross.log`, SHA-256 `ba7eeb0e798ef6a61c46add39b36a22c29175602de17e3de15f26afd90ece3c6`.

A standalone no-text parent-backend preflight independently reported `connect=ok`, `authorize=cleanup_pending`, `close=session_closed` (`preflight-r2.log`, SHA-256 `fb6cc9dc7546837bea462b4d9e4f28a0210add1df403538a3a878c580ef7a0ac`). Direct invocation of the package's `MutterSession.authorize` instead reported `unsupported_compositor` and `close=ok` (`mutter.log`, SHA-256 `c7d1eb63eb3c805ed30cd64aad476d3114d985a5fc0f6cbe9e885d18bfcc6b33`). The original preflight's cleanup exception obscured its result; `preflight.log` is retained as a failed attempt, not a pass.

The subsequent fix prevents an intentional session stop from being reported as an unexpected compositor loss. On the same Ubuntu 24 GNOME Wayland guest, the same r6 package was extracted to a new independent directory and overlaid with fixed `wayland_worker.py` SHA-256 `45330a05e596c9b280d579457cc37bf7af7b4180762a7a1c3a78ef3ecb68c6eb`. The identical no-text preflight then reported `connect=ok`, `authorize=unsupported_compositor`, and `close=ok`; the log `build/handoff-review/wayland24-r1/retest.log` has SHA-256 `d9643a23d101afe578c5351d070f2c4128dca4a84036268c5767e1ddfb92531e`. GDM and account files were restored from new backups and compared, the temporary guest directory removed, and the VM exited 0 (`retest-cleanup.log` SHA-256 `9478bc6579e9c88a668efc47317295d049459b896881d390535f04715c3fdfba`). This is a source-overlay desktop validation of the error path, not acceptance of a new AppImage or validation of keyboard output on GNOME 46.

The actual retest inputs are preserved separately in `build/ubuntu24-perf-vm/input/wayland24-r2/`: the patched worker above, original `preflight-r2.py` SHA-256 `24a01a3c382ede3388dd7cb80f4183f283491dbca167fe857ddf389a3e7f00bc`, and the unchanged r6 AppImage. After copying this directory to `/tmp/wayland24-r2/` in the isolated guest and confirming an active Wayland session, the exact guest command was:

```sh
set -eu
cd /tmp/wayland24-r2
printf '%s  %s\n' e4f2c6de3450cd997607baaeba41dd1764f8365c0bda73d9b9dd7c4ac395db54 InkEcho-0.10.2-x86_64.AppImage | sha256sum -c -
./InkEcho-0.10.2-x86_64.AppImage --appimage-extract >/dev/null
cp wayland_worker.py squashfs-root/packages/inkecho/platform/wayland_worker.py
sha256sum squashfs-root/packages/inkecho/platform/wayland_worker.py
export XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus WAYLAND_DISPLAY=wayland-0 DISPLAY=:0 XDG_SESSION_TYPE=wayland XDG_CURRENT_DESKTOP=ubuntu:GNOME
export APPDIR=/tmp/wayland24-r2/squashfs-root PYTHONHOME=/tmp/wayland24-r2/squashfs-root/usr PYTHONPATH=/tmp/wayland24-r2/squashfs-root/packages LD_LIBRARY_PATH=/tmp/wayland24-r2/squashfs-root/usr/lib/inkecho
./squashfs-root/usr/bin/python3 /tmp/wayland24-r2/preflight-r2.py
```

The session variables above are specific to that disposable guest; do not run this on a user's desktop. No target text was sent by the preflight.

The inability to authorize the original production backend means the requested multi-slot, paused-target, cross-window and cancellation handoff tests could not be executed on this desktop. No clipboard, real audio, user content, or real external service was used. These results are not a package release acceptance or proof that all GNOME 46 variants behave identically.

The tested scripts remain in `build/ubuntu24-perf-vm/input/wayland24-r1/`: `cross.py` SHA-256 `d555fc6954714e942e441798aeeeff49826967e58312b81ddf0924835a62de77`, `cross-target.py` `9a80891662236c629627694ab7f6ceec8a3b8672d8a1835eb693171b4f5b3dbc`, `preflight-r2.py` `24a01a3c382ede3388dd7cb80f4183f283491dbca167fe857ddf389a3e7f00bc`, `mutter.py` `45e73d8f72ed07a811aa1acf2cb58fe8879a8828c84761290fffd1de145db772`, and `run-cross.sh` `6c054811eec240cf49f9cc1f7f7483d0ca07202c01d8aaa7634f0f9670c09e9b`. The versioned Python copies were subsequently formatted and have not been rerun.

To reproduce only in a disposable Ubuntu 24 GNOME Wayland guest, copy those tested scripts, the r6 AppImage and pinned `fcitx5.py` to `/tmp/wayland24-r1/`, extract the AppImage, set that isolated session's `WAYLAND_DISPLAY`, `DISPLAY`, `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`, `XDG_SESSION_TYPE`, and `XDG_CURRENT_DESKTOP`, and use the package's Python with `PYTHONHOME`, `PYTHONPATH`, and `LD_LIBRARY_PATH` set to its extracted runtime. Run `preflight-r2.py`, `mutter.py`, then `bash /tmp/wayland24-r1/run-cross.sh`. The cross script starts a temporary Fcitx process using private XDG directories and restores its session environment afterward. Do not run against a real user's desktop. GDM and account configuration were backed up before temporarily switching the guest to Wayland, restored and compared with `cmp`; temporary files were removed and the guest exited 0 (`cleanup.log` SHA-256 `04f395910d3a81e34f92b2476a9f18586d3609b6633b1aca12245d68f7c94e8a`).
