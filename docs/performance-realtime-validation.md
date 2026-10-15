# Realtime ASR transport validation

Date: 2026-10-15. Scope: independent Python transport, before application/audio
integration. This is not a new Ubuntu 24.04 desktop or microphone acceptance.
Existing input feasibility evidence stays in `native-wayland-parent-validation.md`
and `current-cursor-input-validation.md`; this transport never captures focus,
uses a clipboard, talks to an input method, or dispatches desktop input.

## Protocol feasibility gate

Reviewed the actual local OpenLess checkout, commit `63be178b`:
`openless-all/app/crates/openless-core/src/asr/qwen_realtime.rs` and
`dictation_engine.rs`, including its pre-connection buffering and cancellation.
The implementation below is independently written from the official protocol;
OpenLess source/comments were not copied (its root license is AGPL).
Its unbounded audio queue and partial-result-on-error behavior were not adopted.

Official primary sources checked on 2026-10-15:

- [Connection guide](https://help.aliyun.com/en/model-studio/qwen-asr-realtime-interaction-process):
  WSS, Bearer authentication, model query, official workspace endpoints, and manual
  push-to-talk lifecycle. Existing public DashScope domains remain documented.
- [Client events](https://help.aliyun.com/en/model-studio/qwen-asr-realtime-client-events):
  `session.update` with PCM, 16 kHz and `turn_detection: null`; Base64 audio append;
  manual commit, then session finish. A completed recognition and session finished
  are distinct events. Silence can finish without a transcript.
- [Server events](https://help.aliyun.com/en/model-studio/qwen-asr-realtime-server-events):
  connection session IDs, committed item IDs, content index, final transcript and
  errors. Interim text is not substituted for a completed transcript.
- [Official sample code](https://help.aliyun.com/en/model-studio/real-time-speech-recognition-user-guide):
  Qwen's WebSocket example sends audio at 100 ms intervals. At the chosen 16 kHz,
  mono signed PCM16 little-endian format, this implementation calculates 3,200
  bytes per 100 ms. It sends PCM bytes, not a WAV container.

Result: a dedicated WebSocket adapter is technically implementable. No HTTP
`stream=true` substitution is used. Actual authenticated cloud acceptance remains
pending as described below; a protocol fixture is not a model capability check.

## Interface and constraints

`RealtimeConfig.from_provider(provider, sample_rate=16000)` requires an explicit
`parameters.asr_protocol: qwen_realtime`. The only other accepted parameter is
`realtime_url`, a complete WSS endpoint. Unknown parameters fail configuration
instead of being silently ignored. Official DashScope/workspace hosts can derive
`/api-ws/v1/realtime` from their HTTPS base. A custom HTTP gateway must provide its
WSS URL explicitly; model discovery does not prove its WebSocket capabilities.
URLs reject user information, fragments and non-model query fields. TLS peer and
hostname verification cannot be disabled, and HTTP redirects are not followed.

`QwenRealtimeSession(config, key, timeout_seconds=30, deadline=..., active=...)`:

1. Create the object on the application's event loop; key stays in memory only.
2. Run `start()` as a task while recording begins. `feed_nowait(bytes)` can already
   queue bounded PCM during connection setup, without awaiting a Qt slot.
3. `feed_nowait` permits at most 20 queued 3,200-byte blocks plus one sub-block
   tail (and one sender-owned block once connected). One call is capped at 32,000
   bytes. A full queue terminates the session; audio is never silently dropped.
   Async `feed` instead provides bounded-time backpressure.
4. At stop, call `finish()`. It seals input, flushes the short final block, sends
   commit followed by finish, and awaits the final transcript and session finished.
5. Always call `aclose()` on task cancellation/replacement or application exit.
   No retry, reconnect, partial transcript fallback or text replay is attempted.

The adapter supports only 16 kHz mono PCM16LE. Other configured sample rates are
rejected rather than silently changed. The recorder owns format correctness;
interleaved stereo or compressed bytes cannot be detected from untyped raw PCM.
No language/context option is claimed in this first slice.

Session/update IDs and model are checked; one manually committed item belongs to
this connection. Item/result mismatches, conflicting final results, duplicate
server event IDs, unsolicited session completion, malformed events and errors
fail closed. Repeated identical final text for the same item with distinct event
IDs is deduplicated. No interim text reaches the caller. Active-task checks run at
async boundaries and before audio sends, with a 50 ms watchdog to interrupt idle
waits. Already handed-off network bytes cannot be retracted. Text injection must
still apply its own task/epoch checks after this adapter returns.

## Reproducible local results

Environment: repository `.venv`, Python 3.13.15, websockets 15.0.1, OpenSSL-generated
one-day loopback certificate. Dependencies changed only to add
`websockets>=15,<16`, locked at 15.0.1; no existing locked version was upgraded.

Run with loopback socket permission:

```sh
.venv/bin/ruff check src/inkecho/realtime.py tests/test_realtime.py scripts/validation/realtime_cloud_probe.py
.venv/bin/ruff format --check src/inkecho/realtime.py tests/test_realtime.py scripts/validation/realtime_cloud_probe.py
.venv/bin/pytest -q tests/test_realtime.py --tb=short
```

Actual result: **40 passed in 0.75 s**; Ruff lint and format passed. The first run
without socket permission could not bind loopback; the same test suite passed
with the necessary execution permission. This is not a skipped test result.

Real loopback WSS fixture checks (not vendor/cloud recognition): authenticated
upgrade, upload before stop, exact 100 ms PCM chunking plus short tail, ordered
commit/finish, final-only Unicode result, duplicate/conflicting finals, stale item
and session rejection, start/final timeout, malformed/error bodies with sanitized
exceptions, silence/empty input, explicit cancellation, expired active callback,
absolute deadline, and cancellation at connection-completion ownership transfer.
TLS tests reject an untrusted certificate and prove a 302 redirect does not
forward credentials. All connection background tasks finish during cleanup.
Separate queue unit checks cover terminal overflow, bounded backpressure timeout,
invalid sample bytes and pre-connection buffering. They do not measure network
backpressure from Alibaba Cloud or microphone callback timing.

## Authenticated cloud evidence: blocked, not passed

The only proposed cloud fixture was the existing public WAV
`/tmp/inkecho-public-asr-fixture.wav`, SHA-256
`0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf`.
Local checks confirmed mono PCM16, 16 kHz, 282,322 frames. No private microphone
recording was selected. A guarded, non-default live probe is retained at
`scripts/validation/realtime_cloud_probe.py`: fixed fixture hash/format, one
connection, paced frames, in-memory system credential, copied model/protocol
settings, no configuration writes, fixed metadata output, no desktop injection.
Without `--live` it prints only `live_flag_required` and exits before reading a
credential or sending network data.

Automatic approval review rejected the proposed `--live` command **before process
execution**, stating that the current human instruction did not explicitly
approve sending this particular local WAV to this particular external service
with the stored credential. Therefore this attempt read no credential, opened no
cloud connection and uploaded no audio. It was not retried or routed through
another tool. No authentic model transcript, cloud latency or accuracy claim is
made. Explicit authorization and approval of that data transfer are required
before a future live run. The probe itself has not been cloud-validated.

## Remaining acceptance

Application and recorder integration, model/protocol UI, final-result task guards,
real microphone streaming, actual configured model access, cloud latency, Ubuntu
24.04 desktop behavior and a rebuilt/running AppImage require their own evidence.
This report does not claim lower end-to-end latency from a simulated server.
The old deployed AppImage does not acquire this new dependency automatically.
