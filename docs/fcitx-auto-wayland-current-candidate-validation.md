# Actual system Fcitx automatic route — candidate421180, Ubuntu26 Wayland

2026-10-29. Same frozen candidate **0.10.2**, SHA-256
`42118031876729529974e6c20d746638d5d09611f4bb34b4ae189fb4717ada7b`,
not rebuilt or edited for this test. Source/package origin and other required
checks are in [the candidate overview](current-v2-appimage-candidate-validation.md);
[Ubuntu24 system Fcitx](fcitx-auto-current-candidate-validation.md) is separate.
Candidate remains at
`/tmp/inkecho-v2-appimage-candidate-20261029/source/dist/InkEcho-0.10.2-x86_64.AppImage`.

## Environment and actual route

Ubuntu26.04.1, GNOME50.1, native Wayland, in an independent /tmp qcow2 child.
Parent VM was confirmed stopped; its guest/base were mounted readonly. Actual
`/usr/bin/fcitx5` **5.1.19**, actual graphical session bus
`unix:path=/run/user/1000/bus`; no private dbus-run-session or fake service.
The same AppImage's extracted FcitxInstaller staged/verified its actual plugin
and runtime-version config into a private data directory. Only the test daemon
used private config/cache; graphical source settings remained the actual user
settings. Clipboard and IBus-service-emulation frontends were disabled. The three
user-manager framework hints were temporarily configured to fcitx and restored.

The package's collect_system_framework/detect_system_framework both selected the
same authenticated Fcitx owner (r1 :1.84; r2 :1.131). Live runtime version and
system executable/UID checks were done by the real package, not a test detector.
All target reports identify **GdkWaylandDisplay** and wayland-0, so this is not an
XWayland result. Fcitx target process maps contained im-fcitx5.so; the simple
fallback target did not. These are owned GTK TextViews with fixed public text,
not reads of other applications. Actual packaged Session/OutputRouter/Fcitx bridge
and keyboard were used. Recorder/transcription were synthetic fixed-response
fixtures for this routing test, not physical audio or cloud evidence. Observer
wrappers forwarded every original operation without changing checks or sends.

## Results

| Case | Actual observation |
|---|---|
| Continuous automatic Fcitx focus switch, r1 | A83/B117, exact concatenated200 Chinese characters, B focus confirmed, Session succeeded, backend fcitx and no keyboard invocation. Sender was not stopped or resumed. First receipt opened/focused a second owned GTK window while output continued. This is programmatic focus, not a physical user click. |
| Automatic Fcitx cancel, r1 | Receiver exactly1 character, Session cancelled, no remaining text after delayed observation; backend fcitx, no keyboard. |
| Known-zero no_target→native keyboard, r2 | Auto selected real Fcitx; trusted no_target, accepted0, unsent_offset0, uncertainfalse occurred before keyboard insertion. Unmodified Hybrid then used actual **WaylandKeyboardInput._insert_prefix**, delivering exact15-character `无目标 fallback Ω。`; Session succeeded. |
| Cancel after native fallback, r2 | Same known-zero handoff, then exactly1 character and Session cancelled, no tail. No uncertain or accepted prefix was replayed. |

Raw observations, detector/install logs, before/after settings and scripts are in
`experiments/ibus-v2-package-20261029/fcitx-auto-ubuntu26/`.
`fcitx-auto-summary26.json` selects r1 Fcitx and r2 fallback cases. Product app
origin in all sender reports is the extracted candidate; app.py SHA-256 is
`8af5a728a16894e7f011388cea5e9607ae4228db0c9d421104acf94d6f3ffc8a`.

## Retained failures and cleanup

Fresh child lacked /mnt/input and /mnt/output, so initial mount/redirection
setup failed before any daemon or target started. Created those directories and
retried the same live VM; no restart for an observation timeout.

R1 fallback targets actually received the complete text / one-character cancelled
prefix with correct Session outcomes, but helper flags were false: it observed
WaylandKeyboardInput.insert while Hybrid calls _insert_prefix directly. The
original observer bytes and false results remain. Only the observer was extended
to the actual prefix call; original can_continue, deadlines, sends, return values
and exact text/outcome assertions were unchanged. Only the two affected fallback
cases were rerun. R2's strict parser required both true. No product source was
changed to achieve these outcomes.

Daemon wait0, name owner false, environment/source before/after cmp0, original
IBus engine xkb/us. No capability file remained. Expected persistent0600 lock was
verified unlocked and then fixture-removed. No candidate FUSE mount or known
native worker remained. Private addon/config/cache and candidate guest directory
were removed. VM normal shutdown exited0/noOOM; original backings readonly.
No stable entry, shared worktree, commit, push or publication was changed.

## Reproduction and limits

Copy measured .py.txt archives back to .py in a disposable logged-in GNOME50
Wayland guest and use the identical AppImage SHA. Final run.sh is r2's fallback
invocation and contains package verification, actual system daemon setup,
collector, observers and restoration trap. For r1's Fcitx cases use
GTK_IM_MODULE=fcitx, INK_TARGET_KIND=normal, INK_PROBE_MODE=auto and run
`target-focus.py switch` / `target-focus.py cancel` before cleanup. Do not use
switch-ready (it suspends the sender); it was not used here.

This proves these owned native GTK controls with this candidate on the measured
system. It does not establish browser/terminal, XWayland targets, other desktop
versions, non-XKB composition/preedit, existing arbitrary Fcitx profiles,
concurrent services, hostile same-UID races, physical microphone/shortcuts or real
cloud. “No target” means no compatible Fcitx input context while a simple text
widget is actually focused; it does not mean keyboard output is safe with no
editable destination. Fallback remains limited to explicit trusted zero/known
unsent replies; no unknown/partially accepted request was retried. This result
does not change the separate IBus delivery-unknown limitation.
