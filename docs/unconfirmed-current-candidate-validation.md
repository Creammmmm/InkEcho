# Unconfirmed outcome candidate package validation — 2026-10-29

This records actual package checks of one development candidate, not publication or a stable-entry update. The unchanged version number does not identify the artifact; the SHA below does. Earlier SHA421180 evidence is historical and was not inherited.

- Artifact: `/tmp/inkecho-unconfirmed-candidate-20261029/source/dist/InkEcho-0.10.2-x86_64.AppImage`
- SHA-256: `222c017a4f9e10bf4d6422cf402a2b7ea57245adb267a4409cce87ca74551694`
- Size:104393208 bytes; version0.10.2.
- Frozen488-file working-tree input: [manifest](../experiments/unconfirmed-package-20261029/SOURCE-SHA256SUMS.json). This is an uncommitted-source snapshot, not identified by HEAD alone.
- Actual image extraction checked all80 app files against frozen source and package inventory, including9 changed outcome/UI modules: [inventory review](../experiments/unconfirmed-package-20261029/inventory-review.json).

## Results and scope

[Machine summary](../experiments/unconfirmed-package-20261029/dual-system-summary.json) records8 actual receiver cases and2 HTTP ASR checks. Ubuntu24.04.5/GNOME46/X11 and Ubuntu26.04.1/GNOME50.1/nativeWayland used exactly the same package SHA. Independent KVM guest overlays had the original state/base/seed mounted read-only. Both old parent VMs were stopped. Inputs were read-only; output logs and each disposable overlay were the only host writes. No clipboard, real cloud credentials or user documents were used.

| Actual same-package check | Ubuntu24 X11 | Ubuntu26 nativeWayland |
|---|---|---|
| AppImage FUSE GUI |5 screenshots, xcb, visibletrue, exit0 |5 screenshots, wayland, visibletrue, exit0 |
| HTTP ASR supplier path |Verified local TLS, exact generated WAV/request/response, pass |Same, pass |
| Normal keyboard Session |Private Pulse generated marker1601→local TLS Qwen realtime WS→local TLS HTTP SSE→22 exact BMP characters, succeeded |Same, succeeded |
| Recording-time current-target switch |New owned GTK target exact text; old target empty |Same |
| Keyboard partial cancellation |Only你, cancelled, no extra text after1.3s |Same |
| Complete IBus dispatch |Actual target24 exact characters including emoji; task unconfirmed, ibus_delivery_unknown, no replay |Same |
| IBus partial cancellation |Only你, cancelled, no extra text after1.3s |Same |
| Mapping/audio cleanup |Full X map restored; Pulse defaults restored; cleanup_errors[] |Native map SHA/group/depressed/latched/locked restored; Pulse defaults restored; cleanup_errors[] |

IBus's independently observed target result does not give production an acknowledgement that it lacks. Its product outcome correctly remains `unconfirmed` and is not counted as confirmed receipt or as the successful normal-task gate. Keyboard supplies that gate. Cancellation metrics on keyboard report characters0 while the receiver observed1; do not equate that metric to zero emitted or retractable text. Timing/receiver reports retain actual values.

Each task imported app.py SHA `a9f9484618d487cfd0b7b39836ae8bcfe576ee2cfb0fa50bfc6f6481fb988989` from the extracted actual package. It matches the new inventory, rather than the older artifact. No live cloud test, actual speech-recognition accuracy or physical-microphone claim follows from generated audio and fixed local responses. Owned GTK and programmatic creation/presentation of the new target do not establish arbitrary browser/terminal compatibility or natural mid-emission focus switching.

## Reproduction

Build from the frozen source using the existing locked environment:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/lth/github/InkEcho/.venv/bin/python \
  /tmp/inkecho-unconfirmed-candidate-20261029/source/scripts/packaging/build_appimage.py
```

The builder verifies pinned native Fcitx source/binary, cached system archives and AppImage runtime. Actual artifact files were read with unsquashfs at runtime offset944632. Run each system in its own disposable qcow2 overlay over its stopped parent VM, with parent/base/seed read-only, KVM group991, no external container network, no-new-privileges, input9p read-only and output9p writable. [Mount evidence](../experiments/unconfirmed-package-20261029/vm-readonly-mounts.log) identifies the exact local parents. SSH uses only the private Unix proxy; test key contents were never read or logged.

Archived exact guest scripts are in `vm24/input` and `vm26/input` under the evidence directory, with `.txt` appended to executable source archives. From guest, mount the inkecho_input/inkecho_output9p shares to `/mnt/input` and `/mnt/output`; run `prepare.sh`, restart only guest gdm3 for GNOME extension discovery, run `enable.sh`, `gui.sh`, then `protocol-run.sh`. Preparation checks the artifact SHA and extracts that artifact. The pipeline uses packaged Session/Recorder/ProviderClient, synthetic `Session.key`, verified local TLS WS/HTTP services and real desktop keyboard/IBus transports. Target receiver independently records content; observers compare map metadata without replacing product focus/cancellation policy.

Final successful raw runs: `vm24/output/protocol24-r4` and `vm26/output/protocol26-r5`. Each contains HTTP ASR results and four case directories, each with report, receiver and finish/delayed target observations. Source-only synthetic checks:11 unconfirmed-related tests passed,375 deselected; Ruff lint/format passed227 files. A wider offscreen run stopped after52 dots and was interrupted, so is not a pass or a clean-HEAD workflow receipt.

## Retained failures and cleanup

- Two build attempts exhausted the UID quota while copying untrimmed dependencies, exit120, no artifact. Global filesystem free space had been misleading. Only separately authorized redundant AppDir/squashfs intermediates were removed after checking manifests/artifact-tail equality/no active references; old packages, frozen source and logs remained. The third build passed. Cleanup/build records retain exact identities and released space.
- Initial isolated VM preparation omitted the read-only base mount for qemu-img, so overlay creation failed; a subsequent empty startup failed. Adding base fixed it. Another startup lacked KVM group991 and failed before guest boot; adding the existing verified group fixed it. These were setup failures, not package checks.
- Ubuntu24 waited about120s for network-online on the same running process; SSH banner timeouts did not cause restarts. Host default SSH config permissions required the isolated wrapper to use `-F /dev/null`; private Unix socket access required tool sandbox escalation. No approval rejection occurred.
- On24, the new GNOME login overview blocked the initial owned target: both strict focus guards failed before output. Exiting the disposable guest's overview with Escape enabled normal initial focus; guards were not weakened. A later receiver `cp` raced the target's atomic replacement and exited nonzero after successful product output. Changed only fixture observation to a single file read, retained r3 and repeated in r4.
- On26, the GUI script initially queried old session1 after re-login and exited before package launch; changed only the metadata query to list-sessions. GUI then passed.
- The24 cleanup helper called a nonexistent ExtensionManager.uninstall after successful disable and logged AttributeError. Enabled extensions were[] and xkb/us observed. No test Pulse module or capability was listed. The helper's pgrep matched its own shell command; it did not identify a product worker. All guest test-installation data was subsequently removed by discarding the stopped overlay.
- On26, disable succeeded and enabled extensions were[]. The system `ibus engine` diagnostic failed with IBUS_IS_BUS/No engine is set; final engine identity was not verified and is not claimed restored. There were no listed test Pulse modules, capabilities or AppImage mounts; pgrep again matched its own inspection shell. The stopped overlay was discarded, so no test installation persists.
- Both guests shut down normally: exited0, no OOM, PID0. [Final states](../experiments/unconfirmed-package-20261029/vm-final-states.jsonl). Own overlays were then removed, releasing586158080 and58396672 bytes; originals stayed read-only. Candidate and original evidence remain in `/tmp`.

## Unverified scope and disposition

The required same-artifact subset in project specification24.3 is covered on these two sessions; this is not the full four-session or all-backend matrix. Ubuntu24 nativeWayland, Ubuntu26 Xorg, actual microphone, physical Ctrl+F4/F13/F14/Escape portal, nonfocus overlay behavior, desktop install/path repair/autostart, complete settings/provider flows, real authenticated cloud, arbitrary browser/terminal/non-XKB/preedit targets, hostile same-UID/service races, and ambiguous partial-output fallback were not tested for this SHA. System Fcitx auto-routing was not rerun for this new artifact; older421180 results remain explicitly historical. No new blanket support claim follows.

Both AppImage help screenshots were visually inspected and show the correct Ubuntu/session/version without truncation. Raw PNG screenshots remain in the local `/tmp/.../vm24/output/ui24-session` and `vm26/output/ui26` directories; they are not embedded into this text evidence patch. No publication, stable alias replacement, production config write, commit or push was performed. Root review and any final clean-HEAD validation remain separate.
