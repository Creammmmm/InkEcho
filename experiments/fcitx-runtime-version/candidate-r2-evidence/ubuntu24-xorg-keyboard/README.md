# Ubuntu 24 Xorg automatic keyboard and FUSE diagnostics

On 2026-10-28 the isolated Ubuntu 24.04 Xorg guest tested the same candidate
AppImage SHA-256 `f6378650f230215a0ff0a7196a80ddc48e9429e2546b55afe40105d8a5889d05`.
The package's actual Session and router selected its real X11 keyboard backend
in `auto` mode with no Fcitx process and no Fcitx-committed prefix. Two owned
GTK3 simple TextViews and synthetic audio/transcription were used; no clipboard,
cloud, microphone, system input method, or user application was used. The
existing Xorg session authority was passed to the test without logging its
contents; input-method environment was not changed.

The full sample of 200 Chinese characters reached A exactly; cancellation
after the first observed character yielded a cancelled outcome and one in-flight prefix character in A, B empty; already-sent input cannot be withdrawn. Two initial switch
runs failed to establish B focus, each yielding A/B 200/0. Their synchronous
`xdotool windowactivate --sync` call ran inside the GTK change callback, so it
blocked that event loop while waiting for a focus event. Those failed results
remain in `wayland24-xorg-keyboard-r5.log` and are not passes.

The separately retained r6 fixture requests X11 focus asynchronously and
verifies B's actual focus. Three natural switches, without pausing the production
sender, each returned A/B 1/199 and exact concatenation of all 200 characters;
all three reported backend `keyboard`, succeeded and sender exit 0. See
`wayland24-xorg-keyboard-r6.log` SHA-256
`6e3649eb6d6b65c99344084899bbd79b2c59e114c8c44838ad94ecc079d31fea`.
This tests absent Fcitx before output, not fallback after an accepted prefix or
an uncertain Fcitx delivery, nor behavior in other applications.

The same AppImage was directly run with `--help`, exiting 0 (output retained).
A separate `--appimage-mount` invocation yielded a live mount of type
`fuse.InkEcho-0.10.2-x86_64.AppImage` containing AppRun; stopping the mount
process unmounted it, as recorded in `wayland24-xorg-fuse-r5.log`. The full GUI
was not launched in this FUSE check, and this is not package acceptance.

To reproduce in a disposable Ubuntu 24 Xorg guest, copy the candidate into
`/tmp/inkecho-native-test/` with the retained r5 runner, sender and fixture in
its `probes/` directory without `.txt`, then run `bash probes/run.sh`. For the
r6 comparisons, use its separate fixture with the same environment and candidate
runtime, invoke `/usr/bin/python3 probes/target-focus-r6.py switch` three times;
the environment values and authority retrieval are retained in `run.sh.txt`.
The run restored no settings because it changed none; private config and guest
files were removed, no Fcitx process or FUSE mount remained, and the VM was
normally powered down with container exit 0. See the cleanup log. Results are
specific to this Xorg guest and do not constitute full dual-system acceptance.
