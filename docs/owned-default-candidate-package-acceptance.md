# Owned V5 default-routing AppImage candidate: actual-package acceptance

Date: 2026-10-29. Candidate only; no shared working-tree edits, release, stable-entry change, host configuration change or real cloud/microphone use.

## Artifact and build

- Version 0.10.2; bytes 104401400.
- SHA-256 `77f252509097fe550188122acbe912783e9ad4b4ea33296fe23a2d64da3729ef`.
- Preserved artifact: `/tmp/inkecho-owned-default-candidate-20261029/source/dist/InkEcho-0.10.2-x86_64.AppImage`.
- `SOURCE-SHA256SUMS.json` binds 508 frozen source files. All 93 actual extracted application files match the frozen source and packaged inventory. All seven owned V5 resources match the product's size/hash pins (`inventory-review.json`). No source overlays replace packaged modules during acceptance.
- Build exited 0. Focused router/hybrid/lifecycle suite: 117 passed. Ruff and formatting: 232 files passed. This is focused validation, not a receipt for the root agent's eventual final commit.

## Isolation and reproducibility

`launch-vm.py 24` and then `launch-vm.py 26` create separate KVM child qcow2 disks. Existing stopped parent/base/seed paths are mounted read-only. Containers have no Docker network, no-new-privileges and only a loopback QEMU SSH forward through the local Unix proxy. The actual guest graphical desktop and system session D-Bus are used. Guest input is read-only; outputs are written to the task evidence directory. No second VM runs concurrently.

Replay from the preserved base after confirming the parent and prior child are stopped: create empty `vmN/state`, run `python3 launch-vm.py N`, use `sshN.sh 'bash -s' < vmN/input/prepare.sh`, then `sshN.sh 'bash /mnt/input/gui.sh; bash /mnt/input/protocol-run.sh'`. The scripts name the exact expected artifact SHA and verify it inside each guest. Ubuntu24 needs its actual normal network-online boot waits; retain the same process. Replaying owned tests requires the explicit UI install step (`ui-owned.py`), a disposable guest GDM relogin, actual package `enable-owned.sh`, then `owned-protocol-run.sh`. Ubuntu24's real Wayland transition is separately recorded in `select-wayland.sh`; setting environment flags alone does not count.

The standard GUI uses the actual FUSE AppImage. Protocol tests run its extracted packaged Python/modules (the same verified artifact bytes). They use actual Recorder with a generated Pulse marker, trusted test-local TLS Qwen WebSocket and HTTPS SSE, plus an independent GTK TextView. The marker must arrive on the wire before stopping; local HTTP ASR is checked separately. The receiver creates a new window while recording: the old window must remain empty, and output goes to the current target. The test constructs the real `Session(store, client=..., realtime_factory=...)` with **no inputs injection or replacement router/factory**. Pure forwarding wrappers observe preparation and the real automatic choice. For explicit-keyboard samples, normal production desktop keyboard selection is retained. Independent receiver-first-nonempty cancellation calls real Session.cancel, then checks no late characters and normal resource cleanup.

Fcitx cases use the actual distro `/usr/bin/fcitx5`, the actual packaged installer/native plugin and default Session auto selection; only recorder/transcriber are synthetic in these separate routing cases. The daemon uses private config/cache, clipboard/IBus-frontend/XIM addons are disabled, and the real user's data directory inside the disposable guest holds the actual addon. The sender sees that same real directory and the installed V5. Fcitx tests are not independent real-microphone or cloud accuracy evidence.

## Actual results, same SHA

| Guest / actual session | Sample | Result and limit |
|---|---|---|
| Ubuntu24.04.5, GNOME X11 | FUSE GUI | exit0, five pages, xcb, visible; screenshots retained |
| Ubuntu26.04.1, GNOME Wayland | FUSE GUI | exit0, five pages, native wayland, visible; screenshots retained |
| 24 X11 and 26 Wayland | Local HTTP ASR + actual Recorder→TLS WS→SSE→explicit keyboard | both 22 codepoints exact; newly focused window receives all, old window empty; first-received cancel leaves one codepoint, unchanged after delay; mapping restoration, audio defaults restored, cleanup_errors=[] |
| 24 and 26 native Wayland | Explicit V5 install, relogin, explicit enable, actual default auto routing | strict installed hashes true, state enabled, router automatically selects ibus; 22 codepoints independently received exactly; outcome remains **unconfirmed / ibus_delivery_unknown**, not a target delivery acknowledgement |
| 24 and 26 native Wayland | Same auto IBus pipeline, receiver-triggered partial cancel | each receiver retains three codepoints and receives no late text; real Session cancellation and resource cleanup pass. Product cancellation accounting reports two characters; receiver count is independently three and is not rewritten as an acknowledgement count |
| 24 X11, installed V5 disabled | Real Fcitx default auto selection | 200-codepoint continuous output follows A→B (26+174), exact concatenation; partial cancellation retains one codepoint; no keyboard route |
| 26 Wayland, installed V5 enabled | Real Fcitx retains priority | 200 codepoints follow A→B (68+132), exact concatenation; partial cancel retains one codepoint; no keyboard route |
| 24 X11, V5 disabled | Fcitx no_target with confirmed zero sends, fallback keyboard | 15 codepoints exact; partial cancel one codepoint; no replay before/after no_target |
| 26 Wayland, V5 explicitly disabled; actual XWayland receiver | Same zero-send fallback / cancel | 15 codepoints exact / cancel one; actual X11-prefix keyboard path observed inside real Wayland session |

Fcitx cleanup records show input-source and user-manager IM environment comparisons both 0, daemon exit0 and service owner false. Protocol reports check defaults and transport/task cleanup; keyboard mapping checks are scoped to keyboard samples (IBus samples do not claim keyboard-map coverage). The optional per-key monitor was not activated in these invocations: events=[] and balanced=true is therefore vacuous, not evidence of a press/release count or held-key gate. Those exact instrumentation gates remain unverified for this SHA.

The actual packaged UI install button was programmatically pressed in each own guest, rather than invoking an installer substitute. Before/after enabled/disabled/global extension settings are identical: install does not automatically enable. Strict file verification succeeds. Immediately after first installation GNOME has not discovered the UUID and the UI honestly reports unavailable; a real GDM relogin is required before explicit enable succeeds. The optional owned card and its four buttons were visually inspected from actual rendered screenshots; the first 24 screenshot missed the lower card due to the test scroll timing, so a corrected observer screenshot is separately retained. No production UI code was modified.

## Failures and limits retained

1. Ubuntu24 normal boot has two network-online waits. Several SSH banner timeouts are retained; one VM process was kept throughout.
2. First 24 Fcitx fixture installed in a private XDG_DATA_HOME while the sender used the real home. Strict installation detection therefore selected keyboard. Actual output was correct but the Fcitx routing gate failed; this is retained as failure, not counted as Fcitx acceptance. The fixture was corrected to use the actual guest home installation directory, and all four affected cases reran successfully. This did not alter product routing or spoof a detector.
3. A later 24 V5-enabled/Fcitx-priority attempt repeatedly extracted the artifact with the old fixture. Shared quota reached 2048 bytes free; extraction reported fopen I/O error and the guest serial reports block I/O errors. This case **did not pass**. Previously completed reports remain intact, but no results after that fault are accepted. Normal shutdown was requested; after SSH closed, container stop/inspection confirmed exited0, PID0, no OOM. The damaged child disk was never reused. Its raw serial/log records are retained. Only that stopped unreferenced task overlay was deleted, releasing 1,399,930,880 bytes. The 26 fixture was corrected to reuse the already extracted package. Ubuntu24 V5-enabled Fcitx-priority remains unverified for this SHA.
4. The 26 guest completed normally, serial confirms poweroff, exited0/PID0/noOOM. Its unreferenced child overlay was deleted after evidence collection, releasing 61,149,184 bytes. Candidate/source/raw logs/screenshots remain. Quota then had 1,398,396,928 bytes available before the small report copy.
5. Per-key guardian/held-key instrumentation was not enabled in these actual-package runs; no balanced-event-count assertion is credited. Initial target focus freshness and independent actual reception were checked, but the test did not install per-character target ownership guards. The entire desktop is disposable.
6. No real Chrome DeepSeek page, Codex/Electron, GTK4, Qt application input matrix, Ubuntu26 Xorg, password/secure field, IBus preedit block or malformed-installation fail-closed case was exercised here. The independent GTK3 sample proves only the listed actual context. No blanket cross-app compatibility or general IBus delivery acknowledgement is claimed.
7. This run does not test real provider authentication, cloud recognition accuracy, physical microphones, first-user Portal authorization, external focus ownership, or actual shortcut interactions. Existing historical evidence is not inherited as a pass for this artifact.

## Evidence locations

All original files remain under `/tmp/inkecho-owned-default-candidate-20261029/`: build/inventory receipts and `vm24/output`, `vm26/output`. The companion repository evidence patch contains selected original text receipts, executable fixture sources saved with `.txt`, manifest hashes and references to retained local screenshots. It excludes binaries and the stopped disposable disk images. Full serial logs and all failed/corrected results are retained locally. Neither stable entry nor release was touched.
