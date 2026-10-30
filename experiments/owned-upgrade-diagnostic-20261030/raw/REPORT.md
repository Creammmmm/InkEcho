# 0.13.0 candidate: stopped on actual upgrade-diagnostic failure

Source: `3613057ca7d026fbd5edad355225ce738884a550`, normal-hook version-only release preparation. Full clean-HEAD workflow passed Ruff and 2629 tests (2 skipped). This is a candidate, NOT a release or completed dual-Ubuntu qualification. No stable entry, tag or GitHub release was changed.

Artifact: `source/dist/InkEcho-0.13.0-x86_64.AppImage`, SHA256 `b8d14e9f815f932fc55e256f0323a9fdf2fd0699ea371fc6d94296898cda45d2`, 104425976 bytes. All application source bytes match the frozen commit. Independent inventory verification checked 3707 regular files, 1048 symlinks and all seven bounded-extension assets. Runtime/dependency caches were rechecked by the production builder.

## Actual Ubuntu24 scope and failure

One isolated, no-network Ubuntu24.04.5 GNOME46 Wayland guest used the FUSE-mounted exact artifact. Packaged GUI lifecycle, full source/package audit, HTTP ASR/local protocol checks, Qwen VAD, provider UI and packaged provider protocol test suite exited zero. These use owned profiles and local/synthetic services; they are not physical microphone, shortcut or authenticated-cloud acceptance. Native Chrome154 ran normal sandbox with a new profile and owned textarea. Loaded module origins were checked to be inside the mounted package; no candidate-source overlay was present.

With the original complete published V5 extension enabled, direct new-client introspection correctly refused the legacy schema before sending text. Default automatic output also sent zero characters, but returned `input_capability_unknown` rather than the required `ibus_upgrade_required`. Actual `legacy-auto` is therefore FALSE and has NOT been relabeled successful. This reproduced with explicit native text-input-v3 and consistent IBus environment hints, not just the earlier contradictory fixture settings. See `vm24/output/browser24-native012-legacy013-ibus-r4-textarea/results.json` and its raw suite log. Complete legacy protocol, enabled installation and authenticated owned scope were observed.

Root cause: `src/inkecho/platform/output_router.py`, direct automatic owned bridge connect error branch, collapses IBus preflight failures to `input_capability_unknown`. The handoff path has its own diagnostic mapping, and the explicit prepare-task allowlist does not cover this branch. Safety remained fail-closed: both owned fields stayed empty and all negative cases retained 1.3-second no-late observations. This is a visible upgrade-guidance defect, not evidence of replay, unauthorized input or target receipt.

The actual packaged manager also refused install/enable against the complete old extension without modifying its assets (`vm24/output/old-install-upgrade-guard.json`). The isolated test then explicitly backed up/moved old files, installed the packaged new extension, and performed normal GNOME reload. At the root agent's instruction, all further checks stopped before new-protocol positive text tests.

## Preserved failures and limits

Three initial SSH banner timeouts occurred during the guest's roughly125-second system network wait; the same VM subsequently became ready. `legacy013` failed before input because a pure browser-identity helper was absent; the exact reviewed helper was then copied. `legacy013-r2` omitted the explicit native IME flag and retained a hard-coded Fcitx session hint without a Fcitx daemon; these conditions must not be used as the sole explanation of the product failure. `legacy013-native-r3` added native IME but retained the hint mismatch. `legacy013-ibus-r4` made hints consistent and still reproduced the diagnostic defect. All raw directories remain. A host-only stage-fixture insertion assertion is recorded in `harness-setup-failures.json`.

New-service Chrome Unicode/newline/cancellation, new-service GTK preedit, Xorg/XWayland input, physical microphone/shortcuts, overlays/autostart and all Ubuntu26 checks remain UNTESTED for this SHA. Ubuntu26 fixtures were prepared but its guest was never started. Previous R3 source-only evidence or0.12.0 package results do not qualify this artifact. No application ACK, arbitrary focus-reset immunity or retraction of already in-flight input is claimed.

## Restoration

Ubuntu24 restored all seven original extension assets and all three Shell settings exactly, verified the stock Mutter library hashes, unmounted the owned FUSE image and passed owned resource checks. Normal poweroff and QEMU exit0 are retained. Original Docker wait handle:89066; final `final-receipt.json` independently confirms Docker PID0/Exit0/OOMfalse and the complete archive stream SHA256 `9c173c943c9d84fd1f1dc22f07378ac009dc9e7a1749e25f593bb6633f30f1e5` (829095936bytes), matching the wrapper receipt. Parent snapshots remain read-only. Only owned public fixture text/metadata was used; no host input method, user credentials or surrounding private text was accessed.
