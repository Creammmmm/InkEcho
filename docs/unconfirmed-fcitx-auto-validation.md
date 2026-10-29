# Real system Fcitx auto routing for the unconfirmed-outcome candidate

2026-10-29. This extends [same-artifact package validation](unconfirmed-current-candidate-validation.md) with fresh real-system Fcitx checks for the new artifact; older SHA421180 Fcitx results were not inherited. No shared-tree production changes, stable-entry update, publication or push were performed.

- AppImage0.10.2: `/tmp/inkecho-unconfirmed-candidate-20261029/source/dist/InkEcho-0.10.2-x86_64.AppImage`.
- SHA-256: `222c017a4f9e10bf4d6422cf402a2b7ea57245adb267a4409cce87ca74551694`.
- Every actual sender imported packaged app.py SHA `a9f9484618d487cfd0b7b39836ae8bcfe576ee2cfb0fa50bfc6f6481fb988989`; the guest checked the whole artifact SHA before extracting it. No source-launch substitution.
- [Summary and cleanup states](../experiments/unconfirmed-fcitx-auto-20261029/fcitx-dual-system-summary.json).

## Actual scope and results

Ubuntu24.04.5/GNOME46/X11 and Ubuntu26.04.1/GNOME50.1/nativeWayland were tested sequentially in fresh independent KVM overlays over stopped original VMs. Parent/base/seed remained read-only. No system package installs or original disk writes occurred. The candidate input was read-only. Only disposable guest state and local `/tmp` evidence were written.

The daemon was the real system `/usr/bin/fcitx5`, version5.1.7 on24 and5.1.19 on26, on the desktop session bus `/run/user/1000/bus`. The collector, detector and actual live service agreed on owner `:1.94` on24 and `:1.83` on26 (raw system-detection evidence is authoritative). The packaged installer verified and enabled the bundled addon. Daemon config/cache/data were private fixture directories; it remained the real system executable and service rather than a mocked service or private D-Bus. The clipboard, IBus-service-emulation and unused XIM frontends were disabled, so the fixture neither read clipboard content nor impersonated IBus.

Temporary system-user environment XMODIFIERS/GTK_IM_MODULE/QT_IM_MODULE selected Fcitx for newly created owned GTK test controls. Original source settings were observed and preserved. The receiver was an independently owned target; sender used actual packaged Session and automatic OutputRouter. Recorder/recognition responses were synthetic fixed fixtures, not physical microphone or network-provider checks.

| Actual check | Ubuntu24 X11 | Ubuntu26 nativeWayland |
|---|---|---|
| Auto choice to live Fcitx, continuous200 CJK, A→B focus switch |A43/B157, exact concatenation, B focus confirmed, succeeded |A99/B101, exact concatenation, B focus confirmed, succeeded |
| Active cancellation of Fcitx output |Only1 character, cancelled, no extra text after observation |Same |
| Explicit zero-send `no_target` safety fallback |accepted0, unsent_offset0, uncertainfalse before actual X11 keyboard;15 exact characters, succeeded |Same gate before actual nativeWayland keyboard;15 exact, succeeded |
| Cancellation after fallback begins |Only1 character, cancelled |Same |
| Input-module scope |Fcitx module loaded on Fcitx controls; simple input context for no-target controls |Same; all receiver display backends GdkWaylandDisplay |

The switch did not SIGSTOP or otherwise pause the sender. Receiver programmatically focused B after first observed arrival, and independently confirmed B focus; later characters reached B. This is actual continuous-emission current-focus evidence in owned GTK controls, not a physical mouse or arbitrary application claim. `resumed=false` in the result distinguishes it from the separate stopped-sender experiment mode that was not run here. Cancellation is triggered by actual first receiver arrival and invokes the real Session.cancel. The receiver waits for sender completion plus1300ms before its final snapshot.

The successful Fcitx cases contain real Commit receipts and no keyboard fallback. The fallback cases establish only the explicit verified zero-send condition. No replay after ambiguous or partially accepted output was tested or permitted. Sender observations wrap and forward the real calls; the Wayland `_insert_prefix` observer is included so the actual Hybrid path is recorded without changing dispatch behavior. All8 strict target reports passed.

## Reproduction and cleanup

Exact fixture source is archived with `.txt` suffix under `vm24/input/fcitx-auto` and `vm26/input/fcitx-auto`. `launch-vm.py.txt` records the independent overlay and only-readonly-parent launch, KVM group991, no-new-privileges, external container network disabled, and private Unix SSH proxy. Input/output are9p mounts at `/mnt/input` and `/mnt/output`. The guest commands were:

```sh
sh /mnt/input/fcitx-auto/run.sh
/usr/bin/python3 /mnt/input/fcitx-auto/final-cleanup.py
sudo shutdown -h now
```

On24, the same process completed the known120-second network-online wait. An SSH banner observation timed out; no VM restart followed. Escape exited only the disposable guest login overview before initial owned-target activation. On26, the first SSH connection was too early and closed; the same running guest was retried successfully. There were no test assertion failures in either final four-case run. Original main-package acceptance failures remain documented separately rather than erased.

Both daemon processes exited0, desktop service owner became false, environment and input-source before/after comparisons were byte-identical. No capability remained. The persistent0600 lock was checked using O_NOFOLLOW, inode/UID/type validation and nonblocking flock to prove no holder; the fixture then removed it. No Fcitx process or AppImage mount remained. The24 final engine read xkb/us. The26 system `ibus engine` CLI returned IBUS_IS_BUS/No engine is set again; final IBus engine identity is explicitly unverified, not declared restored. The source configuration comparison still passed; no engine switch was requested by the test.

Both guests shut down with exit0/noOOM/PID0. Only after confirming those states were the two own overlays removed, releasing474091520 and53940224 bytes. Original disks, candidate AppImage and raw evidence remained. The raw local output directories are `/tmp/inkecho-unconfirmed-candidate-20261029/vm24/output/fcitx-auto24` and `vm26/output/fcitx-auto26`.

## Limits

This establishes only these same-SHA sessions, actual system-Fcitx versions and owned GTK targets. It does not establish Ubuntu24 nativeWayland or Ubuntu26 Xorg, arbitrary browser/terminal/Qt/native applications, non-XKB/preedit composition, hostile owner changes, simultaneous input frameworks, unknown/partially accepted fallback, physical shortcuts/microphone, real cloud recognition or a full compatibility matrix. IBus unconfirmed-receipt behavior remains a separate measured result from the earlier same-SHA report; it is not a Fcitx successful-receipt substitute. No extra experiments were run after the necessary samples.
