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
