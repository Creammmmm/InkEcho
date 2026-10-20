# Qwen live preview and server VAD validation

2026-10-20. Source-level protocol repair, after audio startup commit d096f6d and
UI readiness commit be191f6. This report does not establish packaged dual-system
support, physical microphone performance, or real-cloud recognition accuracy.

## Confirmed cause and behavior

The previous Qwen realtime implementation explicitly sent `turn_detection: null`.
It streamed PCM during recording but committed that audio only when the user
stopped. Alibaba's documented manual interaction sends transcription events after
the client's commit. Therefore a local test server that emits an early draft did
not prove that the real manual-mode service would preview during recording.

Official Qwen realtime endpoints, whether derived from platform configuration
or explicitly saved in older configurations, now use
server VAD with threshold 0.0 and 400 ms silence. This applies to existing normal
Qwen configurations without entering credentials again. Speech turns can produce
replaceable preview text and confirmed segment snapshots while recording.
A 400 ms silence boundary is not a promise of per-character instantaneous output.

Explicit custom `realtime_url` configurations retain manual mode for compatibility.
The automatic VAD classification requires an allowlisted official hostname, WSS,
standard `/api-ws/v1/realtime` path and port 443 (or omitted). Nonstandard paths
or ports retain manual compatibility. An explicit manual-mode selection is never
overridden. This prevents older explicit official URLs on another machine from
silently using a different recognition path.
The finite configuration field `turn_detection` accepts only `manual` or
`server_vad`; it is not arbitrary request JSON. Standalone `RealtimeConfig(...)`
continues to default to manual for existing explicit callers and fixtures.

The VAD adapter never sends `input_audio_buffer.commit`, which the official VAD
protocol prohibits. Stop sends `session.finish`; the service documents completing
the last detected speech, then sending completed and finished. All committed
items must have a final transcript before the aggregate can succeed. No-speech
finish results in the existing explicit empty-result error, not invented text.

Recognition previews and confirmed segment snapshots remain bounded RAM data.
They do not type into the user's application. Final output continues to require
stop, successful finish, the same task's input authorization, and cancellation/
expiry checks. This preserves the user's no-clipboard, no-system-IME requirement.

## Ordering, limits and cleanup

The adapter binds every turn to a bounded nonempty item ID. Commit ordering and
previous-item IDs determine final concatenation, even if finals arrive out of
order. Identical repeated finals do not duplicate text; conflicting finals,
missing commit/final, unknown event types, wrong content index, and inconsistent
session confirmations fail closed. Drafts with an invalid content index are
ignored. Session confirmation checks the requested VAD threshold and duration,
including rejecting booleans in numeric fields.

Limits are 1,000 items, 100,000 text characters in the aggregate preview/final,
and the inherited bounded event-ID and PCM queues. End, cancellation or failure
closes the owned transport and clears item drafts, finals and callbacks. No
ambiguous partial text is replayed.

## Reproduce and actual results

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_qwen_vad.py tests/test_realtime.py tests/test_application_realtime.py tests/test_workspace.py
.venv/bin/ruff check src/inkecho/qwen_vad.py src/inkecho/realtime.py src/inkecho/asr_streaming.py tests/test_qwen_vad.py
```

Actual implementer result: 162 passed in 3.18 seconds, including the workspace
preparing/cancel test, with permission for local
loopback sockets. These tests use generated PCM and actual local TLS WebSockets;
no live cloud endpoint or physical microphone is accessed.

The production Session integration selects QwenVadSession automatically for an
official configuration, with only its socket redirected to the private TLS test
server. It receives a first confirmed segment during recording and shows its
RAM preview while keyboard input remains empty. Stop flushes a second final tail
segment. Delayed desktop consent still blocks output after the server finishes;
consent then permits exactly one concatenated result. The test also verifies
that no manual commit was sent. Standalone protocol tests cover out-of-order
finals, conflicting/missing items, duplicate finals, no speech, cancellation and
bounds. Existing manual-mode protocol and application tests remain passing.

## Standalone package-runtime fixture

`scripts/validation/qwen_vad_package_probe.py` accepts a selected
`--package-root APPDIR/packages` and requires execution by that AppDir's
interpreter under `APPDIR/usr`. It verifies the actual origins of the application,
Session, manual transport, VAD adapter and streaming factory. Full inventory and
all-module origin checks remain the separate artifact-scope gate.

The fixture creates only temporary local TLS keys, private test configuration,
synthetic PCM and memory-only input stubs. Two connections cover exact-once
normal two-segment output after finish plus consent, and zero output after
cancellation. It does not access a microphone, real keyboard, user credentials
or live cloud. Its source-mode run passed with explicit source scope/version
0.5.4; that source result does not establish package acceptance. Early fixture
runs checked pending-task removal before done callbacks had executed. The tool
now yields one event-loop turn after close before asserting that no pending
resources remain; no product check was removed or weakened.

The package helper has not itself been declared accepted here: each selected
AppImage must execute it and bind the result to its own version/hash and actual
Ubuntu session before packaging can complete.

## One authorized real-cloud synthetic-speech check

The root reviewer separately approved and inspected the exact private probe
(`build/qwen-vad-cloud-r1/probe.py`, SHA-256
`ac2cd1e45df41be3093eadb64d1b442b10f45406dde334907e5e0520437edab1`).
It used an installed Flite library to synthesize two public English phrases in
RAM, separated by 800 ms of silence. No trailing silence was added after the
second phrase. It used only the currently selected Qwen credential through the
production credential loader. The tool made one connection, with no retry,
without a microphone, audio playback, saved audio, or saved transcript.

Actual result: passed, process exit 0. The 3.252-second input yielded two speech
starts, two stops, two commits, two completed transcripts, and 18 draft text
events. The normalized final contained both preselected phrase keyword sequences
(`Hello world` and `Voice input is ready`). A preview arrived while still feeding
audio. These are matched booleans; the service response text was not logged.

Observed relative times in this one request:

| Observation | Milliseconds |
| --- | ---: |
| Connection ready | 109.951 |
| First nonempty preview | 573.181 |
| Stop requested | 3387.567 |
| Finish completed | 3561.064 |
| Stop to finish | 173.497 |

Transport/item/callback/audio-queue cleanup passed. Metadata-only output
`build/qwen-vad-cloud-r1/result.json` has SHA-256
`c163596114b09828376c9e04ddc742dc61167ba4bacecbd731d56f66fa52efdc`.
This is a single synthetic English sample, not an accuracy benchmark or a
physical-device test. No cloud retry or manual-mode comparison was performed.

## Primary protocol references and limits

- [Alibaba manual and VAD interaction](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-interaction-process)
- [Client events, including session.finish and VAD parameters](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-client-events)
- [Server events, item IDs and previous-item ordering](https://www.alibabacloud.com/help/en/model-studio/qwen-asr-realtime-server-events)

The root reviewer checked those primary documents. No comparative production
latency, accuracy, or recognition improvement percentage is claimed here. The previous
startup fix removes the avoidable input-consent wait before capture; device
startup, credentials/configuration loading and network/model processing can still
contribute latency. Ubuntu 24.04 and 26.04 use the same protocol path, but their
physical device and compositor behavior still require their own actual package
acceptance before a new AppImage can be published.

The first root full-suite attempt reported 2069 passed, three skipped and one
failed workspace fixture: it still blocked input authorization while expecting
no recording task. Since consent now runs after capture starts, the fixture was
updated to block credential loading, which genuinely belongs to preparation.
All original preparation/cancel assertions remain unchanged; authorization-time
recording and cancellation have their own tests. Historical frozen package
evidence was not edited.

A compatibility follow-up adds nine endpoint-selection regressions: explicit
standard Beijing/international/workspace URLs use VAD, while an explicit manual
selection, custom gateways, nonstandard ports/paths and lookalike hostnames keep
manual mode. A metadata-only check of this machine confirmed that its current
Qwen selection has no explicit realtime URL; no saved configuration was changed.
