# Ubuntu 24.04 audio pipeline repair (2026-10-22)

This report covers the capture/startup module of the user-reported v0.8.0
regression. It does not establish a real microphone or authenticated cloud ASR
accuracy result. Keyboard delivery and CLI rendering require separate actual
application evidence.

## Reproduced startup gap

`Session.toggle()` previously awaited the transcription credential and, when
polishing was enabled, the polishing credential before calling `Recorder.start()`.
The existing recorder-only virtual-source probe began playback after capture
started, so it could not detect this gap. A new Session regression deliberately
blocks credential retrieval and checks that capture already exists. Against the
pre-change code it failed at `assert session.recorder.recording`: no audio could
be captured during the credential wait.

The correction starts the recorder immediately after local configuration and
protocol validation, before asynchronous credential retrieval. A realtime task
retains up to two seconds of initial PCM in RAM while waiting for its credential;
those samples enter the same session in order. Overflow fails the task explicitly
instead of discarding the beginning. HTTP capture keeps using its existing
bounded full-recording buffer. The ASR connection now starts before retrieval of
the optional polishing credential. Keyboard authorization continues concurrently
and still gates every output path.

A per-task `startup_ready` barrier handles a second shortcut press that ends a
short recording before credentials are available. Processing waits for its own
startup result instead of mistaking the not-yet-constructed realtime connection
for an HTTP model. Cancellation, missing credentials and overflow stop capture,
clear the initial buffer and prevent late key results from starting output.

## Focused verification

The new onset test first failed on the old implementation and now passes. Added
regressions also cover a short recording stopped during key retrieval,
cancellation-resistant late key retrieval, startup PCM overflow and missing
credentials after capture began. Further checks cover cancelling processing
without cancelling the shared startup future, a short-stop/cancel/late-key race,
and exactly one accurate notification for missing credentials.

At the time of this module check, these suites passed: 56 tests in
`test_application_realtime.py`, `test_application_streaming.py` and
`test_application_early_realtime.py`. The latter includes actual loopback TLS
WebSocket/HTTPS/SSE traffic using synthetic credentials, not a cloud request.
Additional application tests are owned by the interaction module and will be
included in final integrated checks. Ruff passed for the changed startup code
and tests.

An independent single-module application test that constructs a real Recorder
without first creating a Qt application stalled in Qt multimedia initialization;
that diagnostic run was interrupted, and its timed rerun exited 124. It was not
counted as a passing microphone test or as evidence of the reported user failure.
The final suite must include its normal Qt application fixture lifecycle.

## Additional full-Session audio probe

The review candidate `build/ubuntu24-pipeline-repair/audio_pipeline_probe.py`
creates uniquely owned PulseAudio-compatible virtual devices and temporary
configuration, generates an onset marker during a 400 ms synthetic credential
wait, feeds actual QAudioSource data through Session and a loopback TLS ASR
server, and measures an observing input port. It never opens real credentials,
changes default devices, captures a physical microphone or sends a cloud request.
It is intentionally labelled synthetic, and its observing port does not establish
actual keyboard delivery or target application rendering. Execution results must
be reviewed and appended before claiming this gate passed on either desktop.

## Remaining scope

The websocket success path already aborts its owned transport during cleanup;
`close_timeout=1` alone is not evidence of a one-second post-recognition pause.
No speculative weakening of final ASR confirmation was introduced. Replaceable
ASR drafts remain preview-only, and no clipboard or input method was introduced.

The reported post-recognition batch rendering and repeated two-character CLI
input are investigated in the keyboard module. The actual physical microphone's
startup delay, the remote provider's first-utterance recognition accuracy and
provider-specific network latency remain unverified here. A synthetic marker
must not be presented as proof that all user speech is recognized correctly.

## Ubuntu 26.04 actual virtual-audio Session comparison

The root reviewed the isolated probe before execution. Both runs used the host's
actual Qt audio backend and PulseAudio-compatible desktop service; this is not a
container audio simulation. Playback went to a uniquely named null sink and its
explicitly selected remapped source. No physical microphone was opened. The
input receiver was an observing fake, not a target application or keyboard.

The frozen baseline is source commit
`967cd1d1bb92e60a866923937358bd348d50147f` (0.8.2). The repaired r1 source
snapshot includes the new capture ordering and buffering; later notification and
shared-future race fixes do not change that capture ordering. Bindings:

- Probe SHA-256: `5fc744b664aebb5e69505c5ea5c515531d4c799f5c2a562c1d7c428808821adc`.
- Baseline source manifest SHA-256: `eac56c29457f0f4a6736534a504a7b60e562e02a9c244285282efb83f49fa2d5`.
- Repaired r1 source manifest SHA-256: `86e19639e6414158db3abe5d5eb659aceeea1aa4a3694b92dc63b640bc2763ef`.

Each run deliberately delays a synthetic credential read by approximately 400 ms
and starts a 100 ms marker near 80 ms after the shortcut-equivalent toggle.
The loopback server validates the selected protocol and emits a known final
result after 120 ms; it does not recognize speech. All times below are measured
from the outer toggle request, rather than from the later task timing origin.

| Observation | Frozen baseline | Repaired r1 |
| --- | ---: | ---: |
| Credential wait started | 1.078 ms | 4.163 ms |
| First captured frame/readiness | 442.329 ms | 7.943 ms |
| Marker playback requested | 79.383 ms | 86.250 ms |
| Credential wait finished | 420.016 ms | 384.176 ms |
| First PCM observed on TLS wire | 529.056 ms | 390.768 ms |
| Stop requested | 958.497 ms | 909.611 ms |
| Local final result emitted | 1090.020 ms | 1025.646 ms |
| First observing-input dispatch | 1092.248 ms | 1026.163 ms |
| Marker samples received | **0** | **1601** |
| Captured wire bytes | 17012 | 29300 |
| Natural process exit | **1: expected onset assertion failure** | **0** |

The baseline's task nevertheless accepted the fixture's known final text. This
shows why checking only successful final text or an audio probe that begins
playback after Recorder.start cannot establish that early audio was preserved.
The repaired run retained the whole marker during credential loading and
forwarded it after connecting. Neither result proves zero hardware startup delay
or real cloud recognition accuracy. The repaired capture still takes several
milliseconds, and no audio before the actual source opens can be recovered.

Raw stdout, stderr, source manifests and terminal receipts are under
`build/ubuntu24-pipeline-repair/host26-{baseline,current}-r1.*` and the
`baseline-967cd1d` / `current-source-r1` directories. Both original process handles
were awaited to natural completion (baseline session 78625, repaired session
7765), with no signal or timeout. Both runs executed their `finally` cleanup and
default-device equality checks. A separate post-check found zero remaining
`inkecho_pipeline_` modules. Private existing Pulse tools were used; no packages
were installed and no default device was changed.

## Ubuntu 24.04 actual virtual-audio Session comparison

The dedicated Ubuntu 24.04 desktop VM's 9p shared mount failed; the same pinned
probe and source directories were copied over its existing SSH connection into
a new private ext4 directory. No mount repair, reboot or GUI input was performed
by this module. The previously extracted 0.8.0 AppImage runtime supplied Python
and dependencies only. **This is source validation, not acceptance of a newly
built AppImage.** The source/tool stage manifest SHA-256 was
`62bef9e75b8da11cbd3155ce52c54b946f9f30fc1d4a648039e502372506abf2`.
The repaired r2 snapshot additionally includes the single accurate credential
notification and shared-startup-future cancellation protection.

| Observation | Frozen baseline | Repaired r2 |
| --- | ---: | ---: |
| Credential wait started | 1.443 ms | 8.097 ms |
| First captured frame/readiness | 435.302 ms | 13.671 ms |
| Marker playback requested | 79.835 ms | 86.560 ms |
| Credential wait finished | 382.570 ms | 401.659 ms |
| First PCM observed on TLS wire | 521.940 ms | 410.879 ms |
| Stop requested | 917.775 ms | 901.930 ms |
| Local final result emitted | 1037.334 ms | 1026.911 ms |
| First observing-input dispatch | 1039.832 ms | 1029.300 ms |
| Marker samples received | **0** | **1601** |
| Captured wire bytes | 15644 | 28614 |
| Natural child exit | **1: expected onset assertion failure** | **0** |

The guest runner original child PIDs 3638 and 3662 were awaited without signals
or timeouts; its own outer SSH handle exited 0 after checking the expected
baseline-failure/repaired-success pair. Raw evidence, environment and per-child
terminal receipts are under `build/ubuntu24-pipeline-repair/vm-audio-r2/`.
The baseline stderr ends at the onset-marker assertion, while repaired stderr
contains only the Qt multimedia backend notice. Both executed cleanup and
default-device preservation checks. This demonstrates preserving virtual audio
during startup on both systems, not physical microphone or cloud accuracy.

## Default streaming-polishing path: actual TLS timing, observing input

The independent full-Session SSE fixture retains actual Recorder, a local Qwen
TLS connection, and the production ProviderClient speaking HTTPS/SSE. Only the
input receiver remains a labelled observing fake. Its provider emits a first
segment after approximately 80 ms and its remaining text about 400 ms later.
No real key or cloud request is used. Both source snapshots already default to
`polishing_streaming=True`; an explicit saved False setting is not overwritten.

The first two probe variants mistakenly instantiated raw qasync `QEventLoop`,
although InkEcho's existing `__main__.py` already uses
`inkecho.runtime.ManagedQtEventLoop`. The raw loop omits CPython async-generator
cleanup hooks. Those probe variants and a matching minimal isolation reproduced
HTTP generator cleanup errors despite natural exit 0. **This was a probe
construction error, not a newly discovered product defect.** Their raw stdout
and stderr remain available as invalid lifecycle acceptance. No runtime adapter
was added or changed in this repair.

The corrected minimal isolation using the frozen product ManagedQtEventLoop
exited 0 with empty stderr. Corrected full-Session probes used that same existing
product loop. Ubuntu 26 r3 and Ubuntu 24 r3 both completed naturally with no
async-generator or TLS shutdown errors. The Ubuntu 24 runtime prints existing
VA-library/Qt/PipeWire dummy-device notices; these are retained in its stderr.

| Measured outer timeline | Ubuntu 26 repaired r3 | Ubuntu 24 repaired r3 |
| --- | ---: | ---: |
| First captured frame | 7.118 ms | 26.257 ms |
| Marker samples delivered | 1601 | 1600 |
| Local final ASR emitted | 1371.226 ms | 1426.492 ms |
| Local first polishing SSE segment | 1482.505 ms | 1540.900 ms |
| First observing-input dispatch | 1485.112 ms | 1543.631 ms |
| Local full polished text emitted | 1902.728 ms | 1962.159 ms |
| First dispatch before full text | **417.616 ms** | **418.528 ms** |

This demonstrates the default Session orchestration does not wait for the whole
polished sentence before beginning output. It does not prove a target application
renders every key: actual keyboard and target-prefix observation require the
separate end-to-end input gate. It also does not measure a real provider's
latency or guarantee that every configured provider flushes SSE promptly.

The corrected SSE probe SHA-256 is
`a7081b252c2856eb1362f0253d42fc66a7e86bab19f0404646bc2228f90d2983`.
The Ubuntu 24 corrected stage manifest is
`435fb190c7290f7f0846154212f6f46660e937ce92b958642ac3138941ae163a`.
Guest raw files and original child receipts are under
`build/ubuntu24-pipeline-repair/vm-{audio,sse}-r3/`; host files are
`host26-sse-current-r3.*`. The ordinary audio probe was also rerun on Ubuntu 24
with the corrected loop: baseline first capture 405.139 ms/marker 0, repaired
first capture 6.898 ms/marker 1601. Both guest runner invocations naturally
exited 0 after validating baseline exit 1 and repaired exit 0, without signals.

The baseline SSE run also streamed before final polished text, but lost its
initial audio marker and therefore correctly exited 1. The startup repair
addresses the capture gap; it does not mislabel already working SSE streaming as
a new fix. The protocol still returns immediately on a valid DONE event rather
than waiting for HTTP EOF, and final ASR confirmation remains intact.


## Actual native Wayland full-chain source verification (Ubuntu 26.04)

The root reviewer inspected the empty, focused owned target before authorizing
this run. On Ubuntu 26.04/GNOME Wayland, frozen source `dc3ac5a2bacd126e6924ea6331e5e1a10aa1916f`
(version 0.8.7) ran the real Recorder, Session, local TLS Qwen-compatible ASR,
real HTTPS/SSE ProviderClient, production keyboard factory and native guardian.
The audio source was a unique virtual device and credentials were fake. The
receiver was a private owned native Chrome window, with DISPLAY unset and
observed Wayland surface and xdg_toplevel. This does not validate a physical
microphone, actual cloud recognition accuracy, Ubuntu 24, or an AppImage.

Actual trusted insertText events produced all prefixes of `本地完整链路测试。`,
lengths 1 through 9, in order. The intermediate screenshot shows `本地`;
receiver state before and after taking that screenshot remained `本地`.
The final screenshot and receiver history contain the exact nine characters.
The first two receiver events were 2.1 ms apart; the deliberate SSE fixture
pause separated the second and third events by 366.4 ms. The remaining text
continued character by character rather than being assigned as a DOM value.

| Measured interval | Actual result |
| --- | ---: |
| Toggle to first captured PCM | 11.795 ms |
| Final ASR to first keyboard dispatch | 213.118 ms |
| First polished SSE delta to first dispatch | 101.460 ms |
| First dispatch before complete polished text | 318.556 ms |

Nine actual native presses, nine releases and nine acknowledgements were
observed, with zero guard rejections. Mutter's keymap SHA-256, group and all
modifier states matched before/after; default audio devices were unchanged.
The sender PID 39138, guardian PID 39158 and owned browser PID 37454 each
completed their original Popen wait naturally with exit 0. No forced signals or
cleanup errors occurred. The outer runner also exited 0. Source and worker
module origins and SHA-256 values were recorded and bound to the frozen source.

Raw evidence is in `build/ubuntu24-pipeline-repair/host26-native-source-r1/`.
`evidence-summary.json` records the full original file digests. Important pins:

| Item | SHA-256 |
| --- | --- |
| Frozen stage manifest | `e81ceba75bd3b6ed16f643e3cc383ab52a864bbf9f1097111ee3d56701a0d155` |
| Native sender | `8fc96d96bcc3ea8593b747fad5db2f42484d62f45083c9036be0fe7770eb5f95` |
| Native adapter | `2ee89c294742d1acf96942537d6d0e5088d481d44a863637a8aac2d8474bd195` |
| Native runner | `aad1d67fef246e15ce9fd8a6e80cc4f063e86d0e108f0529d016c694552c64fb` |
| terminal.json | `bb7de75886cf378faac41639ead7c1920dbc4fbd8101f50bded84dec78e2bac5` |
| delivery.json | `8edf8ff9689a555dfd3b501e0cea747303a8805fa56393a5c29c6d78839db809` |
| receiver-final.json | `77a6abbae292f25b57a2d2adaff4dde6397053eaa37167d236af5003e2c14274` |
| partial.json | `b118ab18207db0a075f32b9427d1154084adf10a6864dc2e98071594d8373235` |
| partial.png | `d3e8f35c1205d2f8881c8d80007cf30d9fc38d04a2ba2aaa5d0e8a9d30bd1ce8` |
| final.png | `16b8f5ce7cc52ffc773bfb00d84642492d7bc4ded5c12dc164a931c7854ddf5d` |

## Reproducible generic full-chain tools

The repository now contains one generic sender,
`scripts/validation/audio_pipeline_keyboard.py`, with Xorg PID/XID guards or a
native guard selected explicitly. `audio_pipeline_native_guard.py` adds only
owned-target guard/observation seams to the real guardian; it does not replace
mapping, pacing or ASR final confirmation. `native_pipeline_runner.py` prepares
a private native target, waits for reviewer release, records real prefixes and
screenshots, and performs normal owned-process cleanup. Package mode retains
selected-artifact, inventory, interpreter and module-origin checks.

Freeze a fresh source/helper stage without opening any desktop target:

```sh
.venv/bin/python scripts/validation/stage_audio_pipeline.py \
  --stage build/audio-pipeline-review \
  --pulse-bin /absolute/path/to/reviewed/pulse-tools
```

Review the printed manifest digest and tool code before launching the runner.
Use the frozen runner with `--stage`, `--manifest-sha256`, `--source-root
STAGE/frozen/src`, `--python`, `--expected-version`, a fresh `--output`, and
`--run-reviewed`. It publishes ready.png/json and waits. It never creates
send-request itself: after reviewing the empty owned target, the reviewer may
write literal `send` to OUTPUT/send-request; OUTPUT/close-request closes without
sending. The Xorg sender additionally requires the separately reviewed owned
receiver PID/XID and independent receiver observation.

The tracked-tool migration was checked with Ruff, AST/CLI parsing and a fresh
178-file stage plus stage_check, without opening another desktop target. The
stage manifest was `f07f6993d917844aaa12bad04828183892c783128b691567e99cdbe4328cfe5f`.
These migration checks are not another desktop acceptance run. Ubuntu 24
full-chain verification was still pending at preparation time. A release 0.9.0
candidate must separately bind the same AppImage SHA-256 on both systems and
rerun the actual package path; the source evidence above cannot satisfy that gate.

## Pending 0.9.0 package gate: explicit argument binding

No 0.9.0 artifact or package result is asserted here. First freeze the final
release source and these helpers, then build one candidate AppImage. Record its
absolute path, SHA-256 and bytes before copying that exact file to each system.
Extract each verified copy into a fresh private directory using that AppImage's
own extraction mode; retain the extraction command and original exit status.
Pin the extracted `usr/share/doc/inkecho/inventory.json` SHA-256 on both systems.
Use that AppDir's `usr/bin/python3`, never the development virtual environment
or the old 0.8.0 dependency runtime. Bind all paths to that extraction.

For native Ubuntu 26.04 the reviewed runner's package arguments are:

```sh
/absolute/path/to/development/python STAGE/native_pipeline_runner.py \
  --stage STAGE --manifest-sha256 REVIEWED_STAGE_SHA256 \
  --package-root APPDIR/packages --frozen-source-root STAGE/frozen/src \
  --python APPDIR/usr/bin/python3 --expected-version 0.9.0 \
  --artifact SAME_CANDIDATE.AppImage --artifact-sha256 SAME_ARTIFACT_SHA256 \
  --inventory-sha256 EXTRACTED_INVENTORY_SHA256 \
  --output FRESH_NATIVE_RESULT --run-reviewed
```

Every placeholder must be replaced with a concrete absolute path or full digest
and reviewed before execution. The parent interpreter runs only the owned
browser controller. The runner starts package audit and sender subprocesses with
the selected packaged interpreter, APPDIR/PYTHONHOME/library paths, private HOME
and selected package PYTHONPATH. The audit checks artifact bytes, inventory,
exact application source file set, every source file's bytes and runtime module
origins. Native worker origins must resolve to that same package root. Source
mode and package mode remain explicitly distinct in the final report. Inspect
ready.png/json before authorizing the fixed nine-character send request.

For Ubuntu 24.04, the independent owned Xorg receiver wrapper must first run
`artifact_scope.selected_artifact` and `audit_package` with the same artifact,
version, frozen source and package interpreter. Only after that check may it
invoke the generic sender:

```sh
APPDIR/usr/bin/python3 STAGE/audio_pipeline_keyboard.py \
  --package-root APPDIR/packages \
  --owned-pid REVIEWED_TARGET_PID --owned-window REVIEWED_TARGET_XID \
  --output FRESH_DELIVERY_JSON
```

This invocation requires the wrapper's private package environment, explicit
PID/start-time/window ownership guard and independent actual receiver prefix
history/screenshots; the sender command alone is not a package acceptance gate.
Await the Code/xterm dynamic-mapping repair before running this path. Preserve
old failures instead of reusing their output directories or replaying text.

Both systems must retain the selected artifact/inventory/stage digests, complete
module-origin receipts, actual 1–9 trusted receiver prefixes plus partial/final
screenshots, balanced actual keys, restored mappings/default devices and original
natural child waits. Compare the artifact SHA-256 across the two result sets
before declaring this package gate complete. This virtual-audio/local-service
gate still does not claim physical-microphone or real-cloud accuracy testing.

## Ubuntu 24 actual Code/Codex full chain and Session cancellation

On Ubuntu 24.04.5/KVM, GNOME 46 Xorg, the generic sender carried actual Recorder
PCM through Session, local TLS Qwen-compatible ASR, real HTTPS/SSE polishing and
production KeyboardInput into a private normally sandboxed Code 1.140.0 /
Chromium 150 / Electron 43.7.3 terminal. Its genuine offline Codex used the normal
alternate screen and Kitty protocol flags 7. No DOM text assignment, clipboard,
input method transport or real credentials were used. The virtual source and
fixed local ASR/SSE responses do not establish physical-mic/cloud accuracy.

The r2 product source was frozen before its keyboard commit, with source
manifest `92e88de01d36fdea98756dd3442edc38641ad27de17782f84eb1b44704e8e7e4`
and keyboard SHA-256
`386d8349da0269766e3c1a9fa3c5deededce72f8b8909e040602b398a9c788dc`.
The later keyboard commit is `619bf8e`; these results are bound to the frozen
files, not relabelled as an entire clean-commit or new-AppImage result. The old
0.8.0 extracted Python supplied dependencies only; every loaded application
module resolved to the selected r2 source and had its hash recorded.

A first attempt failed reading the default audio sink: the copied host Pulse17
pactl lacked `libpulsecommon-17.0.so` on Noble. It naturally exited 1 before any
module, recording or key dispatch; independently observed DOM keys remained
empty. This failed directory was preserved. After review, a separate result
used VM-native Pulse16.1 tools with explicit hashes: pactl
`f80e4a11c6a13c927810a1b695490f689f25f7afb8881475099b45ca26f5fbbd`,
pacat/paplay `925943b3e978dfbda45d1d716aae7dc9491dcbcce290a69ddda9c163f3ca860b`.
The owner/identity/focus and still-empty target were rechecked before this
confirmed-unsent retry; no uncertain input was replayed.

Normal chain result: first captured PCM at 7.113 ms, onset marker 1600 samples,
final ASR at 1412.634 ms, first dispatch at 1636.711 ms, and full polished SSE text
at 1934.433 ms. Actual input began 297.722 ms before the full polished response.
All nine trusted DOM keydowns, all nine UTF-8 PTY characters and all nine Kitty
release codepoints exactly matched `本地完整链路测试。`, with zero NUL bytes.
Guest-local screenshot receipts measured actual before/after key counts 2/2,
5/5 and 8/8; the independent pixels show partial text, then the accurate final
nine-character Codex prompt. Sparse screenshots do not imply every individual
character had a separately verified paint. Actual production presses/releases
were balanced and mappings/default audio devices restored, with no cleanup
errors. Sender PID8931 naturally exited 0; normal Code close and original owner
wait (session90887) both completed with exit 0.

A separate fresh empty Code target then ran `--case cancel-after-first`.
The real production first-sent callback synchronously called Session.cancel;
epoch changed 1 to 3 and the task immediately became inactive. The sender kept
its original tasks and release/mapping cleanup, and emitted exactly one press
and release. Sender PID9594 naturally exited 0. After confirmed Session
cancellation, independent Code observations sampled the actual trusted key
history 60 times across 1.206536 seconds, always only `本`; actual PTY bytes and
the final Codex screenshot also contained only `本`, with no NUL or later tail.
The observation was not simulated with can_continue alone. Map/default-device
restoration and balanced keys passed; Code and original owner wait
(session20488) completed normally with exit 0.

In both cases, the genuine Codex CLI's separate relay recorded `cli_exit=-1`
when its terminal was closed with Code (PTY hangup); do not claim the CLI itself
exited 0. No direct termination signals were sent by these validation runners.
The Code and original controller natural-exit receipts remain distinct from
that child terminal outcome.

Evidence roots are `build/ubuntu24-input-pipeline/raw/pipeline-normal-r1/` and
`pipeline-cancel-r1/`; each has an evidence-summary.json with full original file
SHA-256 values, screenshots, DOM history, raw PTY bytes, source/tool proofs and
original wait receipts. The first dependency failure remains in the normal
archive beside the successful separate r2 output.

| Pin | SHA-256 |
| --- | --- |
| Code receiver stage manifest | `eeec10ad5cc3f579205bb22f17b2fe6978eb26aecbe709174b973e9b93d4fa52` |
| Generic sender stage manifest | `edcb1897c65673a3882eb10df334d64e2297a4d2019bac62e27f16e2fd7fbbcc` |
| Generic sender including optional cancel | `77f719520b764f67542c78bddf2996f15faadbb0a4a5b76f7b14570ea41fcb01` |
| Guest-local 2/5/8 screenshot observer | `8873a9929a034fff1a18c6fed3becca67963bff5685f2edd07dc8517a6e9aef5` |
| Normal delivery.json | `fbbf78bf436e3b79cebad600624d341937af94dae588e2a91ce45613c87cb1ae` |
| Cancel delivery.json | `9998c097c32b82be1432d929413949147efeecc24d032151e0596d8b34613327` |

These source normal/cancel results do not replace final 0.9.0 same-SHA package
normal/cancel acceptance on both actual Ubuntu systems.

## Ubuntu 26 native source Session cancellation

A separate fresh native Wayland Chrome target ran `cancel-after-first` from the
0.8.11 source freeze, after the reviewer inspected its empty focused textarea.
The real production first-sent callback caused synchronous Session.cancel,
epoch 1→3 and immediate task invalidation. The complete Recorder/local-ASR/SSE
pipeline sent one actual native press/release and received one ACK, with zero
guard rejections. The independent actual receiver retained exactly the single
trusted prefix `本` over 107 observations spanning 1.208353 seconds after the
confirmed cancellation; partial and final screenshots both show that single
character. It did not receive the second character or later SSE tail.

The qasync sender-side nominal sleep(1.2) woke after 1.140958 seconds; this is
recorded honestly and is **not** the 1200 ms acceptance evidence. The independent
system-Python receiver measured its own monotonic ≥1200 ms observation window,
which is the no-tail gate. No application timer or pacing code was altered.

Mutter keymap SHA, group and modifier state matched before/after; X11 driver
mapping and default audio devices were also restored. Sender PID61166, guardian
PID61186, owned browser PID58894 and original runner wait session88375 all
completed naturally with exit 0, no forced signals or cleanup errors. Product
module and guardian origins/hashes bind to the frozen source. This source test
still uses virtual audio and local services and is not a new AppImage result.

Evidence root: `build/ubuntu24-pipeline-repair/host26-native-cancel-r1/`.
Its evidence-summary.json contains all raw SHA-256 values. Principal pins:

| Item | SHA-256 |
| --- | --- |
| 0.8.11 source/helper stage manifest | `e23ddc39170f59d83f6950155d0068aeca395eaa080b1feee94b8c5b49eeeecc` |
| Generic sender | `77f719520b764f67542c78bddf2996f15faadbb0a4a5b76f7b14570ea41fcb01` |
| Native runner including optional cancel case | `193efb09bfef69837e161af4a5be5862620e46ac0a02602dfe4f1c33fc86cdce` |
| terminal.json | `2e80568f5cf1de7bd44688a46b74ccdbd5c6332cdfac0bbc33b0691ad448b213` |
| delivery.json | `cca76e529bf77439ade253514b02bce187c428df584c4411cfb23ac362fb9365` |
| Actual receiver ≥1200 ms observation | `a3d3cea45e116a8c57ee02044e965974e7368054de4e437903a3945994b3506e` |
| Actual single-character final pixels | `9e4ca80e2acb6e2ab70804021c4e0e511a74f9ffdfb2ff89e1569456e3f6fe15` |

The unique sender keeps `normal` as the default and adds explicit
`cancel-after-first`; the native runner forwards that case and independently
verifies actual receiver history for ≥1200 ms. Every scenario requires a fresh
empty owned target and result directory. Source normal and real Session cancel
now have actual evidence on 24 Xorg and 26 native; final 0.9.0 package runs must
repeat both scenarios on each OS bound to the identical AppImage SHA-256.
