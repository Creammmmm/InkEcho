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

## Incremental polishing and serial output

`Settings.polishing_streaming` is a strict boolean, defaulting to true when absent
from an existing configuration. Reading an older configuration does not rewrite
it. Setting the option false explicitly selects the existing synchronous request;
an unsupported stream is never retried automatically as another polishing POST.
Production `ProviderClient` implements the stream interface. Older fake clients
without that method retain the synchronous test path; that compatibility does not
establish a provider's streaming support.

The first actual nonempty content delta can begin output while the provider is
still generating later content. One producer reads the provider stream and one
consumer serially calls the existing keyboard adapter. They are supervised
together: a keyboard error immediately cancels the producer, rather than leaving
a network request waiting until its timeout. All queue and output boundaries
check current task identity, deadline and cancellation. Changing focus remains
allowed; each later keyboard event goes to its then-current focus. There is no
clipboard or input-method path.

The queue holds at most **4096 Unicode codepoints** (32 chunks of up to 128), plus
one chunk being delivered. A separate **128000-codepoint** ceiling bounds the
received original-text prefix used for integrity checks. Offsets count original
Unicode codepoints, not UTF-8 bytes. A repeated offset is ignored only when its
overlap exactly matches the already received prefix. Repeated text at a new
offset is retained: two deltas saying the same word are not duplicates. Standard
chat deltas receive sequential local offsets; no content-based deduplication or
automatic network reconnection is introduced.

Normalization holds a trailing CR across delta boundaries, so `CR` followed by
`LF` becomes exactly one newline. A final standalone CR is flushed once. Initial
whitespace is held until non-whitespace arrives, so a whitespace-only failed
result types nothing. Invalid controls and unpaired surrogates fail before their
fragment reaches the keyboard. The queue itself preserves other Unicode
codepoints; actual backend limits still apply, including the existing native
Wayland non-BMP restriction. A later unsupported fragment can therefore end a
partially dispatched stream; prior input cannot be undone.

The complete returned result is only an integrity check and possible final tail.
It must begin with the exact accumulated original prefix. Only a verified new
suffix is queued; already queued content is never sent again. Conflicting final
text fails without rewriting prior input. All producer/consumer work is cancelled
and joined before deciding whether original-text fallback remains safe. Fallback
is allowed only before any call into the keyboard adapter; entering an insertion
attempt forbids it even if the backend cannot confirm whether a press occurred.
The task controller releases its original-text fallback when streaming output
begins. Partial failure never replays uncertain output or the whole original.
Counts for interrupted output include confirmed completed fragments only; an
ambiguous interrupted fragment is not guessed to be complete.

`polishing_completed` observes the adapter returning its complete result;
`output_completed` waits for the final queued fragment and backend cleanup.
`polishing_seconds` includes time spent awaiting queue backpressure. The provider
request timeout includes that backpressure too; the queue is deliberately large
enough for ordinary dictation, but a sufficiently long stream can still time out.
These observations are not pure server-generation or network round-trip times.
`output_ms` can also include waits for later model deltas and is not a promise of
constant character speed.

### Reproducible checks and actual results

```sh
.venv/bin/python -m pytest -q tests/test_streaming_output.py \
  tests/test_application_streaming.py tests/test_config.py \
  tests/test_application.py tests/test_core.py tests/test_performance_baseline.py
```

Actual result: **162 passed in 0.57 seconds**,
`build/performance-streaming-integration-tests.log`. These are controlled-clock,
synthetic provider/keyboard and offscreen checks, not cloud or desktop acceptance.
They cover early output, focus changes between fragments, repeated Unicode,
matching overlap, final suffix, conflicting final, CRLF split boundaries, empty
results, output bounds, producer backpressure, keyboard/provider failure,
explicit stream-off, old settings, cancellation within a fragment, expiry,
replacement and cancellation-resistant late deltas. The fixed-schema first-send
timestamp is observed before polishing completion in the streaming fixture.
Changed Python files passed Ruff lint/format and `git diff --check`.

Compare synchronous and incremental output under the same synthetic generation
and per-character delays:

```sh
PYTHONPATH=src .venv/bin/python scripts/validation/performance_baseline.py \
  --compare-streaming > build/performance-synthetic-comparison.json
```

Both branches use the same artificial generation iterator: 10 characters over
100 ms total, an artificial 150 ms ASR delay and 120 ms per character. The
synchronous branch accumulates all generated characters before output; the
streaming branch forwards each generated character to the queue. Each branch
ran three samples. Actual medians, milliseconds:

| Observation | Synchronous fixture | Streaming fixture |
| --- | ---: | ---: |
| Stop to first simulated press | 292.302 | 201.852 |
| First simulated press to output completion | 1163.829 | 1165.461 |
| Stop to output completion | 1456.131 | 1367.123 |

The artificial pipeline overlaps generation and output, with a 90.450 ms earlier
first press and 89.008 ms earlier completion in this run. Output duration itself
was not reduced; its 1.632 ms difference is ordinary scheduling variation. This
validates orchestration under the stated controlled delays and demonstrates no
real cloud, keyboard-speed or Ubuntu 24.04 performance improvement. The JSON
explicitly labels both branches `synthetic_headless`, with desktop and cloud
validation false. The script also supports `--streaming` for one branch and
retains a synchronous default. Historical stage 1 baseline results remain
separately recorded in [performance-timing-validation.md](performance-timing-validation.md).

### Remaining acceptance

Provider SSE protocol/TLS evidence is recorded separately in
[performance-polish-stream-validation.md](performance-polish-stream-validation.md). The
synthetic comparison is not an authenticated voice-input benchmark. Real owned
desktop fields, real cloud generation and Ubuntu 24.04 must be measured and
labelled separately. This module changes no keyboard pacing and makes no new
platform claim. No push, release or deployment was performed.
