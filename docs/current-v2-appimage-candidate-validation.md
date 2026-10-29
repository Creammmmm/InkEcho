# V2 AppImage candidate — 2026-10-29

Candidate only; no publication or stable-entry update. The later mandatory gate below supersedes the first-pass pending items: both systems now have actual same-artifact GUI and usable keyboard-route local protocol/Unicode/cancellation/cleanup evidence. IBus delivery uncertainty remains a separately failed task result and is never substituted for a successful normal task.

- Frozen working-tree source: 382 files, `SOURCE-SHA256SUMS.json`; builder completed from `/tmp` with pinned cached runtime/system archives.
- Artifact: `source/dist/InkEcho-0.10.2-x86_64.AppImage`
- SHA-256: `42118031876729529974e6c20d746638d5d09611f4bb34b4ae189fb4717ada7b`
- `inventory-review.json`: all application source bytes match snapshot; current V2 extension/gate/capability/metadata included. This is a content check, not desktop acceptance.

## Ubuntu24 attempt

Original VM was stopped (docker state exited0). New child qcow2 overlay in `/tmp`, with original guest and base mounted readonly. Fresh container `inkecho-v2-package24-20261029` uses KVM. Two early SSH banner timeouts occurred while serial showed boot waiting for network. Boot completed after the 120-second network-online wait. The first SSH username `ubuntu` was wrong and rejected; repository VM creation code confirmed `inkecho`, which succeeded. No VM restart was used for observation timeouts.

Ubuntu24.04.5 / GNOME46 / X11 measured. Same SHA candidate GUI directly launched by FUSE, visible, five screenshots, exit0 (`vm24/output/gui24.log`, `mount24.txt`, `ui24/`). SSH environment initially lacked XDG session/desktop fields, so help displayed unknown session; retained. Repeating with accurately supplied `XDG_SESSION_TYPE=x11` and GNOME desktop produced five visible screenshots with correct metadata (`ui24-session/`, `gui24-session.log`), but the SSH channel finally broke and its exit code is not claimed successful. Later process check found no candidate or mount process.

Candidate-package ExtensionManager.install succeeded. Immediate enable failed because GNOME had not discovered the newly installed UUID; traceback was retained in the recorded command output. Restarting only the disposable guest GDM made it discoverable; package installer/enable then verified installed files and reported running. Using the extracted same AppImage's actual `IBusBridge` and current V2 extension, owned GTK A received 甲 and B received 乙丙, an explicitly invalid active predicate rejected 丁, the xkb/us engine was unchanged, and no capability files remained. `vm24/output/input24.json` is passed; input used package modules from its extracted runtime, not a standalone prototype. FUSE GUI and extracted input are distinct checks.

A repeat GUI attempt hit /tmp per-user quota and failed while writing mount evidence. Only this task's redundant AppDir/copy of cached archives/intermediate squashfs were removed; candidate, frozen source manifest and all evidence retained. Normal sandbox execution resumed. Test extension was disabled/uninstalled, enabled-extension list returned empty, engine remained xkb/us, no caps or FUSE mount remained (`cleanup24.log`). Guest shut down normally; Docker recorded exited0 with no OOM. Only the child overlay was then deleted to release space; original backing remained read-only throughout.

## First-pass acceptance limits (before the additional gate below)

Both OSes must use exactly the SHA above. Ubuntu26 research completed and its container was confirmed exited; a separate /tmp child-overlay test used readonly backing with the same candidate SHA. Ubuntu26.04.1 / GNOME50.1 / native Wayland measured. Same AppImage SHA was checked inside guest; FUSE GUI visible, five screenshots and exit0 (`vm26/output/gui26.log`, `mount26.txt`, `ui26/`). Help screenshot visually inspected and reported Ubuntu26/GNOME/Wayland accurately.

The package installer succeeded but immediate enable again failed until new login (expected discovery boundary, not silently bypassed). Restarting only the disposable guest GDM made the UUID available; the packaged enable operation verified payload and reported running. Same extracted package `IBusBridge` SHA02fdefd9b0ffeee15fe7da8c32e05f3d321eadcc73545e6e3cf400b687cc9dcf passed owned native GTK A甲/B乙丙, inactive predicate rejected丁, engine unchanged xkb/us, no capability files (`input26.json`, `input26.log`). Both OS tests used the identical candidate artifact rather than rebuilding per OS.

Extension disabled/uninstalled, enabled list empty and xkb/us unchanged, no caps/FUSE (`cleanup26.log`); guest normal shutdown and Docker exited0/noOOM confirmed. Original backing remained read-only. No guest package install, input engine change or existing user documents/accounts used. The measured subset now covers actual FUSE GUI startup and packaged V2 extension installation/enable plus extracted package bridge into owned GTK targets and cleanup on both systems. At that first checkpoint it was **not complete dual-system release acceptance**: no actual microphone/cloud flow, physical shortcuts/Escape portal, GUI clicks of installation controls, full settings/integration/autostart, native browser, terminal, non-XKB/preedit or hostile same-UID races were tested. Two controlled insert calls on one bridge (A then B) do not establish natural focus changes during one continuous insert. The GUI was mounted; the input probe used the same artifact's extracted modules with system GI for the target. No blanket Wayland/X11/backend compatibility claim follows. The additional mandatory checks below were subsequently completed; the optional/untested platform limits remain and this remains a candidate for root review, not a published or stable artifact. Microphone/cloud/physical shortcuts and full application compatibility are not established by source checks or separate prototype evidence.


## Reproduction and evidence

Build command (the builder verifies pinned caches and runtime):

```sh
/home/lth/github/InkEcho/.venv/bin/python /tmp/inkecho-v2-appimage-candidate-20261029/source/scripts/packaging/build_appimage.py
```

The frozen source includes packaging scripts, native Fcitx payload and current V2 assets. `SOURCE-SHA256SUMS.json` captures source hashes before build and was revalidated after build; `inventory-review.json` captures bundle payload checks. Redundant AppDir, downloaded-cache copies and intermediate squashfs were later removed to avoid quota pressure; the AppImage, frozen source and all evidence are retained. A rebuild is a new artifact requiring a fresh digest and acceptance; do not infer the same SHA from the same version.

`ssh24.sh` / `ssh26.sh` are local-only connection wrappers. `vm*/input/gui.sh` contains actual GUI commands and same-SHA assertion. `vm24/input/gui-session.sh` records the corrected session-env repeat. `vm*/input/input.sh` uses packaged ExtensionManager.enable, then system GI targets load the extracted artifact's actual package via PYTHONPATH; `input_probe.py` contains exact assertions. Candidate install used packaged ExtensionManager.install and enable, then required desktop re-login to discover UUID. No GNOME security setting was weakened. Guest restart was `sudo systemctl restart gdm3` in each independent child overlay, not the host desktop. The helper has no clipboard calls, real provider requests or surrounding-text reads.

Both parent VMs were confirmed stopped before their qcow2 state and base were bound readonly into new containers. Only /tmp child overlays were writable. The local container had no external Docker network and guest SSH was reached via a private Unix-socket proxy to QEMU user networking. Each guest was shut down normally. Original VM backing data was never written. Docker final states are preserved separately.

Failed setup steps retained in this report: early24 boot SSH banner timeouts, incorrect initial ubuntu username, missing9p mounts, immediate extension discovery/enable failures on both systems, initial missingXDG SSH metadata, /tmp quota during second24 GUI attempt, and its later broken SSH channel. Successful checks do not erase these failures. No input-text rejection or mismatch occurred in either completed package-bridge probe.

At final comparison, none of the 382 frozen repository files changed relative to shared working tree (`WORKTREE-AFTER-COMPARE.json`). This checks the snapshot's files, not every untracked repository file. No shared-tree changes, stable alias updates, commits, pushes or releases were performed by this subtask.


## Additional required protocol/pipeline gate — both systems measured

Same artifact SHA42118031876729529974e6c20d746638d5d09611f4bb34b4ae189fb4717ada7b; no rebuild. Same package modules and source origins verified in each run's report.

Ubuntu26 GNOME50.1 native Wayland now passed the usable **keyboard** route's full generated-audio/local-protocol task: actual packaged Session and Recorder captured a private Pulse source, the TLS Qwen realtime WebSocket received the 1601-sample marker, the configured local HTTP SSE polishing service returned fixed text, and the owned GTK TextView received exact 22 BMP characters `你好 InkEcho，café Ω\n第二行。`. Session outcome succeeded. A real first-character callback called Session.cancel; target retained only `你` and no late text after 1.3 seconds; task outcome cancelled. Independent metadata-only Mutter observer compared original map SHA/group/depressed/latched/locked before and after and found all equal for both normal and cancel (`protocol26-r4`). Defaults audio sink/source restored, cleanup_errors empty. The event-list field is not keyboard-event instrumentation; it must not be interpreted as a count of actual presses.

A separate normal task (`protocol26-r5`) opened a new owned GTK target **after recording had started**, without pausing sender processing. The old target remained empty and the new target received all 22 BMP characters, task succeeded, original mapping/modifiers and audio defaults restored. This verifies moving focus while recording; it does not establish natural mid-emission cross-window behavior.

The independent packaged Qwen **HTTP** ASR client sent the exact generated WAV through local verified HTTPS, POST /v1/chat/completions, parsed fixed mixed Unicode including emoji, and left zero server handlers. This is separate from Qwen realtime WebSocket; HTTP model configuration and realtime_url/model/asr_protocol were actually exercised separately. Neither used real cloud credentials or an authenticated cloud request. Synthesized marker audio and fixed local responses cannot demonstrate recognition accuracy or a physical microphone.

Experimental IBus route remains explicitly different: same packet produced the full 24-character sample including emoji in the owned target, but **Session outcome failed with ibus_delivery_unknown** because current OutputRouter deliberately treats panel attempted as lacking target confirmation. It is not counted as successful task acceptance and is not retried. Its first-character cancellation retained only `你` and no tail. `protocol26-r3/ibus-*` preserves both actual receiver observations and task outcomes. The old r4 Fcitx probe's success-only assertion initially failed against this expected IBus contract (`protocol26/normal`); adding raw task_result then hit Usage serialization and left a truncated JSON (`protocol26-r2/normal`). Both failures retained. R3 records only JSON-safe task metrics and distinguishes this contract; it does not alter product logic.

Long SSH disconnects were traced to the copied test proxy retaining socket timeout10 after connecting. Corrected only the private test proxy with settimeout(None); later r3/r4/r5 runners exited0. This explains previous fixture-level broken pipes, not a product or VM failure. No process was restarted solely because an observation timed out.

After 26 tests: enabled extensions returned empty, engine xkb/us, no capability/Pulse test module/FUSE/known worker remained (`protocol-cleanup26.log`). Cleanup CLI emitted an Xauthority warning, but still returned the observed xkb/us engine; do not silently discard that diagnostic. Child VM shutdown exit0 was verified; its /tmp overlay was deleted after confirmed termination to control quota. Original VM backing remained readonly. Logs retain optional VA and Qt/PipeWire notices.

Ubuntu24 completed the known 120-second network boot wait on the same live process, without restart for observation timeouts. GNOME46 X11 ran the exact same artifact and package module pipeline (`protocol24-r5`): local HTTPS HTTP ASR exact-WAV/response check passed, Recorder→TLS Qwen WebSocket→HTTP SSE→keyboard normal task succeeded with exact 22 BMP mixed Unicode/newline. A new owned target was created after recording began; the old target stayed empty and the new target received the complete result. Real first-sent callback cancellation left only 你, no late text after 1.3 seconds, task cancelled. The complete original X keyboard table compared equal after normal and cancel; audio defaults restored; cleanup_errors empty. Both audio runs received 1601 marker samples.

Both final child VMs were confirmed exited0/noOOM after normal shutdown. Extensions were disabled/uninstalled, enabled lists empty, engine xkb/us, no cap/private Pulse module/FUSE/known worker residue. The child overlays were removed only after confirmed terminal state to release quota. Original backings remained readonly.


## Final requirement-by-requirement scope

| Specification24.3 item | Ubuntu24 | Ubuntu26 | Boundary |
|---|---|---|---|
| Version/source/SHA/module origins | Same0.10.2/SHA421180…; snapshot and package origins verified | Identical artifact, no rebuild | Frozen working-tree candidate, not a new released version |
| Actual FUSE GUI | visible5 pages, exit0, GNOME46/X11 | visible5 pages, exit0, GNOME50.1/nativeWayland | Corrected session-env screenshots retained; 24 repeat SSH timeout is a fixture failure, not claimed exit0 |
| HTTP supplier path | Local verified-TLS Qwen HTTP ASR exact generated WAV and response, zero server handlers | Same check passed | No real credential/cloud request; direct packaged ProviderClient, separate from WebSocket |
| Qwen realtime configuration/local chain | asr_protocol=qwen_realtime/model/realtime_url; actual Session/Recorder/private Pulse marker1601→localTLSWS→HTTP SSE; keyboard succeeded | Same configuration/path, marker1601, keyboard succeeded | Generated audio/fixed response; no physical speech or recognition-accuracy claim |
| Mixed Unicode/current cursor | 22 BMP codepoints, accented Latin/Greek/Chinese/punctuation/newline; recording-time switch to new target, old empty | Same exact22 and recording-time switch, old empty | Actual X11 keyboard on24; GNOME native keyboard on26. Mid-output natural cross-window emission not proved |
| Partial cancellation | Receiver exactly你, stable1.3s; Session cancelled | Same | Keyboard task metrics counted0 despite observed one-character prefix; do not misstate as zero emitted or retractable |
| Cleanup | Full X map equal, Pulse defaults restored, cleanup_errors[], no listed residue, VM exited0 | Native map SHA+group/modifiers equal, Pulse defaults restored, cleanup_errors[], no listed residue, VM exited0 | Separate observers were test-only metadata, not production focus tracking |
| IBus V2 | Package install/enable and direct bridge owned-field exact result, cancellation; no normal successful Session claim | Full Session actual target24 including emoji but outcome failed/ibus_delivery_unknown; cancellation stops1 | Attempted is not receipt confirmation; keep explicit failure/uncertainty and never replay |

Unverified items required to be **listed**, not inferred from these local checks: physical microphone, physical shortcuts/F13/F14/Escape portal, overlay nonfocus behavior, desktop install/path repair/autostart, real authenticated cloud, complete settings/provider UI flows, browser/terminal IME targets, non-XKB composition/preedit, hostile same-UID capability races, continuous natural switch during one emission, Ubuntu24 nativeWayland and Ubuntu26 Xorg. No untested combination is declared supported. The measured keyboard route supplies the successful normal-task gate; IBus uncertainty never supplies it.

The raw selected results are in mandatory-gate-summary.json and per-run reports/receiver observations. Earlier assertion, serialization, proxy, discovery and quota failures remain retained. No production changes, stable entry, commit, push or release were performed. Root review and any clean-HEAD workflow validation remain separate.


Tracked raw text results: experiments/ibus-v2-package-20261029/. Full frozen snapshot and candidate are retained in the /tmp directory above; screenshot hashes pin the retained raw images.
