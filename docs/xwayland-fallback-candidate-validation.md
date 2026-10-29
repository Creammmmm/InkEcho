# XWayland fallback fix: same-artifact package validation

2026-10-29. Candidate only: no publication, stable-entry replacement or production configuration write. This is a newly built artifact. Earlier SHA222c package/session/browser/Fcitx results remain historical and were not inherited as new-artifact acceptance.

- AppImage: `/tmp/inkecho-xwayland-candidate-20261029/source/dist/InkEcho-0.10.2-x86_64.AppImage`.
- SHA-256: `4ef35afaf863562a38bd90646cc6d4337d20c22545aa080876ddaab0a5d667e5`.
- Version0.10.2,104393208 bytes.
- Source: frozen494-file working-tree snapshot, [manifest](../experiments/xwayland-fallback-package-20261029/SOURCE-SHA256SUMS.json). `source-HEAD.txt` identifies checkout ancestry, not the uncommitted snapshot by itself. `source-delta.json` binds the changes from the preceding222c snapshot: the only runtime file difference is platform/hybrid_keyboard.py.
- Actual artifact extraction: all80 application files exactly matched frozen source and inventory, including Hybrid SHA `204b46020cc7ed2aa287488388071cdc91b720fd3518a483e57140f697d3273f`; app.py SHA `a9f9484618d487cfd0b7b39836ae8bcfe576ee2cfb0fa50bfc6f6481fb988989`. Version and libei license entry verified in inventory. [Review](../experiments/xwayland-fallback-package-20261029/inventory-review.json).
-32 focused Hybrid tests passed; Ruff lint and format passed227 files. These are source/synthetic checks, not actual desktop or clean-HEAD workflow acceptance. Final494-file hash comparison found no differences from the shared working tree. No shared-tree source files were edited by this validation task.

## Required actual dual-system subset

[Machine summary](../experiments/xwayland-fallback-package-20261029/dual-system-summary.json) binds both systems to this exact SHA. Each independently checked the whole artifact hash and used its extracted packaged Session/Recorder/ProviderClient/keyboard code. Input modules were not overlaid with source files. Guest directories, fixture credentials and targets were disposable; no real user configuration, accounts, cloud keys, browser profile or documents were opened. No clipboard was used.

| Same-artifact requirement | Ubuntu24.04.5/GNOME46/X11 | Ubuntu26.04.1/GNOME50.1/nativeWayland |
|---|---|---|
| Actual FUSE GUI |5 screenshots, xcb, visibletrue, exit0 |5 screenshots, wayland, visibletrue, exit0 |
| HTTP ASR |Verified local TLS, exact generated WAV/request/response, passed |Same, passed |
| Realtime cloud-protocol path |Actual Recorder/private Pulse generated marker1601→configured local TLS Qwen realtimeWS→local TLS HTTP SSE polishing |Same |
| Normal real output |22 exact mixed BMP characters including Chinese/Latin/accent/Greek/punctuation/newline; Session succeeded |Same |
| Current cursor during recording |New ownedGTK target created after recording began; old target empty, new target exact |Same |
| Actual partial cancellation |Independent receiver first nonempty text triggered real Session.cancel; only你, cancelled, no extra text after1.3s |Same |
| Cleanup |Full originalX keyboard table restored, audio defaults restored, cleanup_errors[] |Native mapSHA/group/depressed/latched/locked restored, audio defaults restored, cleanup_errors[] |
| Guest lifecycle |Normal guest shutdown, container exited0/noOOM/PID0 |Same |

Both help screenshots were visually inspected and correctly showed version/OS/session without clipping. Raw GUI PNGs remain in local vm24/output/ui24-session and vm26/output/ui26 directories. Generated audio and fixed local protocol responses exercise configuration/transport/lifecycle, not physical speech-recognition accuracy or authenticated cloud behavior. The Session.key fixture supplies only a synthetic test credential. HTTP and realtimeWS are separately verified. The empty event-list/balanced field is not physical key-event instrumentation and is not treated as an event count.

## Actual24 Wayland regression for the changed route

After the required24 X11 samples, only that disposable guest's gdm/session selection was changed to the already installed realGNOME Wayland session. System user-manager environment confirmed XDG_SESSION_TYPE=wayland and WAYLAND_DISPLAY=wayland-0. The same SHA artifact and already verified extraction were reused to avoid another280MB write. No application modules changed during the session switch.

Real systemFcitx5.1.7 on the actual desktop session bus was installed/enabled using the actual packaged addon/installer with private fixture addon/config/cache paths. Clipboard, IBus-emulation and unusedXIM frontends were disabled. Simple-input targets deliberately supplied no compatibleFcitx context; Fcitx returned explicit no_target(accepted0, unsent_offset0, uncertainfalse) before any keyboard fallback. GTK display type independently separated native from XWayland:

| Target/case | Actual result | Scope |
|---|---|---|
| NativeWayland simple control |GdkWaylandDisplay;0 text, Sessionfailed, unsupported_compositor |Negative zero-send safety check passed; nativeUnicode remains unsupported on GNOME46 |
| XWayland simple control, full15-character mixed text |X11Display inside actualWayland session; exact15, Sessionsucceeded |Real Hybrid X11 `_insert_prefix` fallback after verified emptyFcitx attempt |
| XWayland simple control, cancel on first received input |Only1 character, Sessioncancelled, no late text after completion observation |Real cancellation after output began, no replay |

The live sender reported the new packaged Hybrid hash and `keyboard_backend=x11_prefix`. This closes the old222c failure for these XWayland cases; it does not make GNOME46's native keyboard interface available or silently change the desktop session. NormalFcitx receipt, IBus, Chrome or all-target support is not inferred from these deliberately no-target fallback cases.

Environment and input-source before/after comparisons0, daemonwait0, service ownerfalse, no capability,0600 lock verified released by nonblocking flock and removed. Source setting remainedxkb/us. No listed private process/FUSE mount remained.24 then shut down normally; own overlay538841088 bytes was removed only after stopped-state verification.26 own overlay54923264 bytes was likewise removed after normal shutdown. Original parent/base/seed were read-only throughout.

## Retained failures and fixture corrections

1. Before building, only root-authorized redundant system-deps extraction copies under two old build directories were removed. No active references were found. All regular bytes matched the original extraction of pinned root archives;26 generated extraction subdirectories freed190693376 bytes. All old AppImages, source snapshots, archives and logs were retained. `cache-cleanup.json` records identities and reconstructing archive hashes.
2. Attempting hardlinks from root archives to/tmp failedEXDEV. The first builder, lacking the archives, attempted pinned downloads and failed sandboxDNS. Both failures were retained. Copying the verified local archives fixed setup; the normal builder then exited0. Successful-artifact source/inventory checks followed.
3. Shared UID/tmp quota was exhausted by concurrent tests during the first24 guest boot. The first overlay's serial reported EXT4 journal abort before any package test. It was stopped, records retained, then only that invalid9.8MB own overlay was discarded. Its container exit0 after dockerstop is not described as normal guest shutdown or package acceptance. After other writes stopped and834930688 bytes were available, a wholly new overlay was created from the read-only parent. No corrupted environment or output was reused. The healthy replacement completed the known120-second network-online wait on the same process; SSH banner timeouts did not trigger reboots. Both subsequent tests were sequential. Dedicated QEMU softnofile was set8192 up front to avoid the earlier9p1024-fd fixture limitation.
4. On healthy24 X11, the first partial-cancel fixture acted on product first_sent. Sessioncancelled and no text arrived; the strict receiver nonempty-prefix assertion failed. This illustrates that first_sent is dispatch metadata, not receipt confirmation. The raw0-character sample remains failed for the partial-output gate. A corrected fixture polls only its independently owned receiver, then calls the unchanged real Session.cancel once text is nonempty. Only that case was repeated; it received1 character and passed cancellation/no-tail/restoration.26 used this receiver-triggered fixture from the start. No assertion was relaxed to allow empty output as partial cancellation.
5. The first24 Wayland fallback observer wrapped KeyboardInput.insert, but actualHybrid calls X11 `_insert_prefix`. Actual full15/cancel1 and Session outcomes were correct; strict route-event checks still failed and the original overallrunner exit1 is retained. The exact executed pre-correction sender is archived in matrix-fallback24/sender-executed.py.txt. Added only a pure-forwarding X11 prefix observer and packaged-module hash observation. Only the2 affected cases were repeated, with exact same strict route checks, and both passed. The native negative sample was not repeated.

No production code was modified to address a fixture failure, hide failed attempts or change platform behavior during validation. The actual app code was frozen before building.

## Reproduction

The normal builder was run using the locked local environment:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/lth/github/InkEcho/.venv/bin/python \
  /tmp/inkecho-xwayland-candidate-20261029/source/scripts/packaging/build_appimage.py
```

`launch-vm.py.txt` captures independent qcow2 creation, original state/base/seed read-only, KVM group991, no-new-privileges, no external container network, softnofile8192, input9p read-only/output9p writable and private Unix SSH proxy. Only this task's overlays were writable. Run24 and26 sequentially. Mount9p input/output into guest `/mnt/input` and `/mnt/output`. The archived guest scripts then run prepare.sh, gui.sh and protocol-run.sh.24's actual-receipt partial cancellation uses protocol-cancel-r2.sh after its retained first_sent sample. Later24 guest gdm/session switch enables Wayland, then matrix-fallback-run.sh and the pure observer-corrected matrix-fallback-r2.sh execute the bounded regression. Each fixture checks the new artifact SHA, actual module origins and independent target content. Exact fixture source is archived with `.txt` suffix, not used as a replacement product implementation.

Both actual successful GUI/protocol runs and all failures/cleanup/container states are included as raw text evidence. `source-final-comparison.json` and source-HEAD.txt make the snapshot status explicit. No full workflow receipt is asserted from these local checks.

## Remaining limits

The required same-artifact dual-OS package subset and changed24 Wayland/XWayland route are covered as above. This is not a complete new-SHA four-session/all-backend/application matrix:26 Xorg, normal systemFcitx/IBus paths across bothsystems, physical microphone/shortcuts/Escapeportal/F13/F14, nonfocus overlay, installation/path repair/autostart, full UI/provider/real authenticated cloud, arbitrary browser/terminal/Qt/non-XKB/preedit targets, hostile owner changes, cross-framework races and ambiguous partial-send fallback were not revalidated on4ef35. Older222c measurements remain tied to that older artifact. No initial recording target is required by the product, and the tests' owned-target focus controls do not add product focus pinning.

This candidate was not published, tagged, pushed, deployed or attached to a stable entry. Root review, final source integration/versioning and any clean-HEAD workflow checks remain separate.
