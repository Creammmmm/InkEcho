# Logging/UI repaired AppImage candidate 545e: same-artifact desktop validation

2026-10-29. Candidate only. No shared working-tree edits, commit, push, publication, stable-entry change, real cloud credentials or physical microphone were used.

## Identity and build

- Version0.10.2,104401400 bytes, SHA-256 `545e07e080f05b90fdec4216edf8ff10e3acf6167af3ef505b6fd0a351401c06`.
- Preserved artifact: `/tmp/inkecho-logging-ui-candidate-20261029/source/dist/InkEcho-0.10.2-x86_64.AppImage`.
- Snapshot source HEAD was `fecef0577f9a4df8dc30780ae426cda1be7c97d7` with pending work. `SOURCE-SHA256SUMS.json` freezes510 files; this is a content binding, not a claim that the dirty candidate already has a reviewed release-source commit.
- All93 application files actually extracted from this AppImage match the frozen source and actual packaged inventory. Seven owned V5 resource size/hash pins match. Packaged logging hash `8180a4de054c285686c27b67290d72cbdcb93ab570db1327fb3886a53bafb4e9`; compatibility UI hash `93d4b3c49f0e8772d860c531e4b236f37cbce7fb58cdaf5e34047d01b7a22f2c`. The fixed `input_capability_unknown` code is present.
- Normal builder exit0. Frozen logging/UI focused tests:129 passed in11.74s. Frozen `src scripts tests` Ruff/format:232 files passed. This deliberately scoped result does not claim the repository-wide experimental scripts or final clean-HEAD workflow passed.
- Existing pinned runtime and13 system archives were read, never altered. Only this task's rebuilt AppDir/squashfs/extraction cache were removed after successful build/inventory checks; all candidate AppImages, frozen source and original records remain.

## Isolation and tested environments

Ubuntu24.04.5 began in actual GNOME X11/Xorg, then the disposable guest alone was switched through GDM to actual native Wayland. Ubuntu26.04.1 used actual GNOME native Wayland and separately identified XWayland targets. GNOME46/50 major provenance is the same pre-existing read-only parent desktop image; this run records real GDM/user-manager session identities but did not freshly run a Shell-version command. No distro system packages were changed.

Both KVM guests ran sequentially with separate child qcow2 files and read-only stopped parent/base/seed mounts, Docker network none and no-new-privileges. Each guest independently checked SHA545e before first extraction. Subsequent tests reused the extraction. All mutable profiles, text targets, generated audio and fixed credentials are private. These are actual guest desktops/system buses, not container/headless desktop claims.

Actual FUSE AppImage entry opens the five current pages and quits normally. Protocol tests use the same image's extracted packaged Python/modules, without source overlays. Actual Recorder captures only a generated Pulse marker, then real packaged local-TLS Qwen WebSocket and HTTPS SSE paths run. Local HTTP ASR is separate. A new independent GTK3 TextView is created while recording: it must receive the output, with the original target empty. The real default Session constructor receives no injected inputs/router/factory. Forwarding observers record actual choices, never replace capability replies or continuation checks.

## Actual same-SHA results

| Gate | Ubuntu24 | Ubuntu26 |
|---|---|---|
| FUSE entry/UI | exit0,5 pages, xcb/visible | exit0,5 pages, native wayland/visible |
| Cold controls after exit | toggle/cancel/quit all exit0; no private instance/socket/lock revival; config/data hashes unchanged | same |
| Local HTTP ASR | exact synthetic WAV on wire and mixed Unicode response; handler cleanup pass | same |
| Actual Recorder→TLSWS→SSE→keyboard |22 codepoints exact, new current target only; receiver-first cancel leaves1 and no late text; maps/audio defaults/cleanup pass | same, native map restored |
| Server-VAD configuration compatibility | server advertises VAD, product explicitly negotiates turn_detection=null/manual,22-codepoint final input passes | same |
| Independent keyboard monitor | full9 presses/9 releases; cancel1/1; actual XQueryKeymap before/after has no down keys | native full9/9, cancel1/1; received held-set empty, actual Mutter keymap/group/modifiers identical before/after |
| Actual packaged diagnostic repair | all35 fixed input labels log successfully, including input_capability_unknown | same |
| Actual packaged changed UI | optional card/buttons/new honest routing description visually reviewed; real install button programmatically pressed; strict files true, enabled settings unchanged | same |
| Enabled V5 default autoIBus |22 codepoints exact in current target; full outcome remains unconfirmed/ibus_delivery_unknown; receiver-first cancel3 codepoints, no late text | same |
| Enabled V5 real Fcitx priority |200 codepoints switch A→B,36+164 exact; first-received cancel1; no keyboard insertion |200 codepoints69+131; cancel1; no keyboard insertion |
| Enabled V5 + Fcitx no_target | accepted0/offset0/uncertain=false, empty receiver, failed safely, no keyboard fallback; cancel after first real status3 returns cancelled with zero text/no keyboard | not repeated in this system; no inference from24 |
| Explicitly disabled V5, Fcitx confirmed-zero fallback | actual X11 receiver gets15 codepoints; cancel1; no replay | actual XWayland receiver gets15, press15/release15; cancel1/1; XQueryKeymap before/after empty |

The VAD-configuration row measures explicit manual negotiation under that configuration; it is not server-VAD segmentation/accuracy certification. Keyboard samples are mixed BMP Unicode (`你好 InkEcho，café Ω\n第二行。` or the9-codepoint `甲Ωcafé\n乙。`); no arbitrary-emoji keyboard compatibility is claimed. HTTP parsing includes a synthetic emoji response but that is separate from delivery.

The first-receipt IBus cancellation leaves3 actual characters while product accounting reports2 acknowledged attempts; the independent receiver count is retained, not rewritten as a target acknowledgement. IBus remains an attempted/unconfirmed transport even where this owned sample received exact text. The independent key monitors record real delivered events and actual server/compositor state; native nonmodifier-release scope is the owned receiver, not a universal physical-key query. Pre-held user modifiers/caps/races were not exercised here.

## Failures and corrections retained

- First host-side inventory extraction failed because its output parent directory did not yet exist. The directory was created and extraction reran unchanged; `extract.log` and `extract-r2.log` both remain.
- Initial24 X11 protocol/VAD/key-monitor target prechecks had active=false/focused=false and no output was sent. In the isolated guest, Escape exited the initial Overview state before the next test setup. Original focus guards were kept; no periodic or production refocus was added. The affected samples reran in separate `*-r2` directories and passed. The original preflight failures remain.
- Immediately after explicit24 V5 enable, `installation_state()` once raised input_capability_unknown and the next test did not start. Read-only settings showed the UUID enabled, ACTIVE and mode0700. Repeating the unchanged strict check later returned enabled, after which real default routing tests passed. The exact first failed subcheck/cause was not identified; do not represent this as proof that every activation transition is fault-free. Both failure and later actual state are retained.
- No shared-quota I/O fault occurred in this run; the earlier77f quota failure remains historical and is not used as a pass for545e. No old-SHA result substitutes for a row above.

## Cleanup, replay and limits

Final checks show no remaining candidate-environment processes or capability files; the persistent owner-only Fcitx lock is immediately independently lockable. Fcitx user-manager environment and input-source comparisons are0, daemon exits0 and service owner isfalse. The26 final check additionally matches actual APPIMAGE/FUSE descendants;24 uses the extracted-environment check plus the cold private-config process controls. Normal guest poweroff is recorded; both containers exit0/PID0/noOOM. Their stopped unreferenced own overlays were removed:24 freed594612224 bytes,26 freed63180800. After26 cleanup quota had1141377024 bytes available before this small evidence copy. No candidate/source/evidence was deleted.

Replay uses the preserved input scripts and exact SHA. `launch-vm.py 24`, then `ssh24.sh 'bash -s' < vm24/input/prepare.sh`; run `gui.sh`. The actually successful24 protocol commands are `protocol-r2.sh`, `vad-config-r2.sh`, `key-monitor-r2.sh` after the recorded pre-send Escape setup; then `ui-owned.py` and `packaged-log-check.py` with actual bundled Python, `fcitx-auto/run-disabled-fallback.sh`, `select-wayland.sh`, `enable-owned.sh` (retain errors), `owned-protocol-run.sh`, `fcitx-auto/run-enabled-complete.sh`. After24 stops, launch/prepare26, run `gui.sh`, `protocol-run.sh`, `vad-config-run.sh`, `key-monitor.sh`, the two UI/log scripts, guest GDM relogin, `enable-owned.sh`, `owned-protocol-run.sh`, `fcitx-auto/run-owned-enabled.sh`, explicit packaged V5 disable and `fcitx-auto/run-disabled-fallback-monitor.sh`. Source scripts preserved as `.txt` in repository evidence can be copied to a private executable fixture directory; they are not production modules.

Root review, focused commits/versioning and final complete clean-HEAD checks remain separate requirements. No release/stable change is authorized by a candidate report alone. No actual Chrome/DeepSeek, Codex/Electron, GTK4/Qt input matrix,26Xorg, secure/preedit/unknown-installation matrix, real microphone/cloud, physical shortcut/F13/F14, first Portal authorization, overlay task focus or desktop integration/autostart claim is added. These are individually unverified scopes; the controlled GTK3 samples cannot certify the user's actual browser fault as repaired.

Original data live under `/tmp/inkecho-logging-ui-candidate-20261029`, including `acceptance-summary.json`, source manifest, inventory and both `vm*/output` directories. Selected raw text, exact helper sources, screenshot hashes and serial-log hashes are in the companion evidence patch; original screenshots and full serials remain locally. The new card/navigation screenshots were visually inspected, not inferred from file counts.
