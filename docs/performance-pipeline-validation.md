# Realtime and incremental pipeline integration — 2026-10-15

This report records integration beyond the standalone
[HTTP/pool work](performance-provider-validation.md),
[timing](performance-timing-validation.md) and
[Qwen WebSocket adapter](performance-realtime-validation.md). It does not extend
the platform claims in [current-cursor-input-validation.md](current-cursor-input-validation.md)
or [native-wayland-parent-validation.md](native-wayland-parent-validation.md).
The available host is Ubuntu 26.04.1; Ubuntu 24.04 remains separately unmeasured.

## Realtime ASR orchestration

Realtime is explicitly selected with provider parameters
`asr_protocol: qwen_realtime`; an incompatible realtime model configured as HTTP
still fails its existing HTTP protocol guard. `RealtimeConfig` validates the
selected protocol, endpoint and 16 kHz mono signed-16-bit PCM before permission,
credentials or microphone access. No user provider files were modified. The
standalone adapter report describes verified official endpoints and the explicit
`realtime_url` required for an unknown gateway; listing a model does not establish
that a gateway implements its WebSocket protocol.

The recorder's streaming mode emits complete PCM samples through `pcm_ready`
while recording. It keeps only a one-byte alignment tail and a byte count, with
the existing maximum-duration bound. It retains no complete PCM recording and
does not encode or copy an entire WAV on stop. Ordinary HTTP recording and the
microphone test continue to produce WAV as before. An incomplete final sample,
empty recording, microphone interruption or duration limit fails the task rather
than committing a partial recording.

Session starts one task-owned connection while recording, buffers only within
the adapter's bounded queue, and forwards PCM in bounded feed calls. Stopping
before handshake completion waits for that same start operation; it neither opens
a second session nor uploads a completed recording. Only after stop does it
request the final committed ASR result. Partial preview text is never injected.
The public `wait_failure` monitor makes a transport failure during recording stop
the microphone immediately, without waiting for another shortcut press. Cancelling
the monitor does not cancel the shared transport failure future.

Each asynchronous result retains the current task ID and deadline. Cancellation,
expiry or replacement cancels start/final/monitor work, clears task state, and
closes the connection. Dedicated cleanup tasks are not themselves cancelled by
the normal task cancellation sweep; application shutdown waits for them before
closing the shared HTTP client. Focus is never captured at start and is not a
cancellation condition. A late final result cannot type into a replacement task.
The realtime transcription timing includes the connection's recording overlap;
stop-to-first and stop-to-finished milestones remain separately observable.

### Reproducible checks and actual results

```sh
.venv/bin/python -m pytest -q tests/test_realtime.py \
  tests/test_application.py tests/test_application_realtime.py tests/test_audio.py
```

Actual result: **114 passed, 2 skipped**, recorded in
`build/performance-realtime-integration-tests.log`. Local TLS WebSocket fixtures
exercise the actual adapter protocol, including a public recording-time failure
monitor and independent cancellation of that monitor. They require permission to
bind localhost sockets. The orchestration and PCM tests use fake devices and
providers, including upload-before-stop, stopping-before-handshake, mid-recording
failure, cancellation/expiry/replacement with cancellation-resistant late results,
bad sample-rate preflight, constructor failure, sample alignment, memory bounds
and avoiding whole-recording WAV work. These are not authenticated cloud or
complete desktop voice-input tests.

The real-microphone streaming check is opt-in:

```sh
INKECHO_TEST_MICROPHONE=1 .venv/bin/python -m pytest -q -s \
  tests/test_audio.py -k live_streaming
```

Actual result: **1 passed**, `build/performance-streaming-real-microphone.log`.
The current host microphone produced **33 complete-sample chunks during recording,
0.7023125 seconds total**; chunks were already available before stop, the full PCM
buffer remained empty, stop returned no WAV, and all PCM/tail/count state was
cleared. Only counts and duration were printed; no audio was saved or sent to a
cloud service. This proves this host's capture path, not ASR accuracy or Ubuntu
24.04 capture compatibility. Changed Python files passed Ruff lint and formatting.

### Remaining acceptance

No authenticated Qwen cloud request has been performed in this integration check.
End-to-end cloud latency, real speech accuracy, the user's custom gateway and
Ubuntu 24.04 still require their own evidence. A full queue is an explicit failure,
not an audio drop or automatic retry. The existing HTTP route remains available
when explicitly configured. No push, release or deployment was performed.
