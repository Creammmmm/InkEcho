# Realtime ASR transport validation

Current result (2026-10-16): the official TLS/Bearer-authenticated generated-silence
exchange has passed through session finish; authenticated speech recognition and
accuracy remain unverified. The final optional-metadata policy and cloud result
are recorded at the end of this chronological report.

Initial checkpoint: 2026-10-15. Scope: independent Python transport, before
application/audio integration. This is not a new Ubuntu 24.04 desktop or
microphone acceptance.
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
`stream=true` substitution is used. Authenticated cloud speech recognition and
accuracy remain pending; the later official generated-silence protocol result is
recorded below. A local fixture is not a cloud model capability check.

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

Session/update IDs and model are checked; one manual commit belongs to this
connection. Result item IDs and content index follow the final optional-metadata
policy below; initial mandatory-field assumptions were superseded. Conflicting
provided IDs, conflicting final results, duplicate
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
Its installed BSD-3-Clause license is retained verbatim in
`assets/licenses/websockets-LICENSE.txt` and identified in
`THIRD_PARTY_NOTICES.md`. The existing `scripts/packaging/bundle.py` walks runtime
dependency distribution files (including wheel metadata/license files), and
`build_appimage.py` also copies `assets/licenses`; a newly built artifact must
still verify its generated inventory. This does not claim an existing AppImage
already includes websockets.

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

## Initial public-speech cloud fixture: blocked, not passed

The initially proposed public-speech fixture was the existing public WAV
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

## Remaining acceptance at the initial transport checkpoint

At this initial checkpoint, application/recorder integration, protocol UI,
final-result task guards, microphone streaming and packaging needed separate
evidence. Later application/UI tests and source microphone/local-server results
are recorded in [performance validation](performance-validation.md) and
[package validation](performance-package-validation.md). Those local results do
not establish authenticated cloud speech recognition, cloud latency or Ubuntu
24.04 desktop behavior. This transport report does not claim lower end-to-end
latency from a simulated server. A deployed older AppImage does not acquire new
dependencies automatically; the package report identifies the actual artifact
under test.

## Official manual-mode acknowledgement regression (2026-10-16)

The historical public-WAV approval rejection above was not retried. The parent
agent separately obtained approval for a different data transfer: a single
connection using only one second of all-zero PCM generated in probe source, no
microphone, WAV/local-audio file, user text or prompt. That attempt established a
real official session but failed during configuration, before sending any audio.
`build/performance-realtime-silence-live.json` is preserved: `response`, created
true, updated false, zero frames, 96.050 ms, configuration unchanged. It is failed
evidence, not realtime ASR support or recognized speech.

Primary server-event documentation describes `session.updated` as the confirmed
configuration, but its examples do not reliably describe this service's exact
manual-mode echo (one example even names an unrelated model). Documentation alone
did not justify relaxing validation. The parent agent then obtained approval for
one separate **handshake-only**, no-audio diagnostic. The probe's test observer
classified fields before validation into fixed booleans and whitelisted event
kinds; it did not retain or print raw bodies, IDs, model values, credentials or
free-form service errors. Its send layer refuses append, commit and finish in
this mode.

The retained `build/performance-realtime-handshake-diagnostic.json` isolates the
failure: a `session.updated` event had a unique valid event ID, matching model
and session, PCM encoding and integer 16000 sampling rate. Our explicit update
had been sent. The `turn_detection` field was **absent**, rather than explicitly
null. The operation therefore failed under the old `get(..., {})` check in
81.926 ms; it sent zero frames and left configuration unchanged.

The production fix is deliberately narrow. After successfully sending our own
explicit `turn_detection: null` update, the acknowledgement may omit the field
or return null. A dedicated `_manual_update_sent` flag prevents accepting an
omitted field without that request first being sent. Any non-null value,
including an object or an empty object, is still refused. Model/session/event-ID,
encoding/rate, timeout, cancellation and expiry validation remain in place.
The outgoing request and audio protocol were not changed to match a guess.

Reproduce the focused local regression with loopback permission:

```bash
.venv/bin/ruff check src/inkecho/realtime.py tests/test_realtime.py
.venv/bin/ruff format --check src/inkecho/realtime.py tests/test_realtime.py
.venv/bin/python -m pytest tests/test_realtime.py \
  tests/test_realtime_silence_probe.py tests/test_provider_capability.py \
  tests/test_application_realtime.py -q --tb=short
```

Observed **119 passed in 2.39 s**, including the 33 handshake/silence probe guard
cases. Ruff lint and format checks passed. Actual local TLS/WSS cases cover the
omitted-field acknowledgement through final transcription, cancellation, stale
activity and expired deadlines; invalid model/session/encoding/rate and a VAD
object still fail at startup. Pure boundary cases reject non-null objects,
booleans, strings and lists and refuse omission before our update is sent.
The WSS fixture permits only expected connection closure and fails on any other
server error, rather than silently accepting unexpected test exceptions.
Raw ephemeral result: `/tmp/inkecho-realtime-manual-omission-tests.log`.

No new live request was made by the implementing agent during diagnosis or this
fix. A later separately approved generated-silence run may verify the corrected
official handshake and commit/finish path; it still cannot establish speech
recognition accuracy, microphone workflow quality or Ubuntu 24.04 performance.

## Non-authoritative item notifications (2026-10-16)

The parent agent subsequently obtained separate approval for a generated-silence
retest of the acknowledgement fix. The official handshake passed, but a later
notification exposed a second mismatch with our assumed event order. The retained
`build/performance-realtime-silence-after-fix.json` records created and updated
true, five frames sent, `conversation.item.created`, `response`, 603.046 ms, no
commit or finish, and unchanged configuration. This was another failed protocol
attempt, not a successful complete recognition exchange.

A separately approved, bounded generated-silence diagnostic added only fixed
item classifications to the test observer. The retained
`build/performance-realtime-item-diagnostic.json` records the same notification
after five frames, before commit/finishing, at 595.357 ms. Its item was an object
with type message, but had no nonempty string item ID and did not classify as
role user; there was also no valid top-level item ID. No item content, raw role
value, identifier or service body was retained. This evidence does not establish
whether individual absent values were omitted, null or another type. We do not
need that distinction because these notifications never supply a final result.

The [official server-event reference](https://www.alibabacloud.com/help/en/model-studio/qwen-asr-realtime-server-events)
identifies committed.item_id as the associated user item after manual commit,
and completed.transcript as the final recognition result. A created notification
is therefore not used to authenticate a result. The adapter now checks only that
created.item is a message object and ignores it, without reading its content,
role or ID and without storing any provisional identity. Official `.text`
previews are likewise ignored completely. These branches remain subject to the
existing ready-state, event-ID, event-count, WebSocket-frame and task guards.

At this intermediate checkpoint, a committed acknowledgement still required a
nonempty string ID of at most 200 characters, and completed/failed required that
identity and an integer-zero index. **Those mandatory metadata assumptions were
later superseded by the final optional-metadata policy below.** The retained
guards still reject conflicting supplied IDs, invalid supplied indexes, unknown
transcription kinds and early results. Final text is returned only after
session.finished; preview content and created-item contents cannot supply it.
Explicit cancellation, expiry and replaced-task checks remain unchanged, with no
automatic audio retry or partial-result fallback.

Re-running the focused command above gave **145 passed in 2.64 s**, including
41 standalone probe guard cases. Ruff lint and formatting passed. Actual local
TLS/WSS cases include placeholder creation and unrelated preview before manual
commit, subsequent acknowledged final completion, early acknowledgement/final
rejection, conflicting acknowledgement IDs, boolean content indexes, unknown
transcription events, and cancellation/stale/deadline after a pre-commit frame.
Boundary tests cover invalid/oversized acknowledgement IDs and malformed created
objects. Cancellation cases retain the already-sent fixture frame but send no
remaining audio or commit. Raw result:
`/tmp/inkecho-realtime-placeholder-tests.log`.

All four historical failed/diagnostic receipts above remain preserved. The
implementing agent made no live request for this fix. A later separately approved
generated-silence request can test the complete official commit/finish exchange;
it will still not measure speech accuracy or desktop/microphone performance.

## Empty manual-commit acknowledgement (2026-10-16)

The next separately approved full generated-silence test passed the handshake and
placeholder-notification handling, sent all ten source-generated frames, then
sent commit and finish. The retained
`build/performance-realtime-silence-final.json` is still a failed result:
`input_audio_buffer.committed` carried no valid nonempty string item ID, which
the adapter required. It ended with `response` after 1113.328 ms; configuration
was unchanged. The existing classification does not establish whether that field
was omitted, null, empty or another type. This is not cloud-speech evidence.

The initial additional compatibility boundary was restricted to an empty
result (superseded by the final metadata policy below). A distinct acknowledgement
flag records a committed event only after
our own manual commit. A missing or null item ID may acknowledge that commit,
without binding any result identity. Empty strings, oversized IDs and other
types remain errors. A subsequent session.finished additionally requires both
the acknowledgement and our own finish, so silence can complete with an empty
result. Completed/failed events still require a valid ID bound by the commit
acknowledgement, strict ID matching and integer-zero content index. They cannot
introduce a new identity when the acknowledgement omitted one. A final can arrive
after acknowledged commit and before finish is sent, but is not returned until
the valid session.finished event. Missing IDs never erase an already-known ID.

The observer now distinguishes missing/null/empty/invalid top-level item IDs using
fixed booleans, without retaining values. Focused local TLS/WSS and application
regressions gave **157 passed in 2.67 s**, including 47 probe guards; Ruff lint and
formatting passed. These tests exercise missing/null acknowledgement through
empty finish, rejection of any completed result without a bound identity,
finish without acknowledgement, invalid IDs, and final arrival before finish.
Raw result: `/tmp/inkecho-realtime-empty-ack-tests.log`.

No live request was made by the implementing agent. A successful future
generated-silence exchange would validate only its observed protocol path, not
the identity schema of nonempty speech results or speech recognition accuracy.

## Single-commit association with optional metadata (2026-10-16)

The next separately approved generated-silence run passed that acknowledgement
boundary and reached completed. The preserved
`build/performance-realtime-silence-ack-final.json` records ten frames, valid
handshake, acknowledgement received, finish requested and unchanged configuration.
It still failed with `response` at 1198.117 ms: the completed event omitted
item_id (`event_item_id_missing` true, invalid false). Its result body was not
retained, so this failure establishes the metadata omission, not a speech result
or recognition quality.

Rather than infer a different schema one field at a time, the final adapter
policy binds a result to its own isolated WebSocket session and its single
manual commit. Completed/failed events require our commit and its acknowledged
receipt. Optional item IDs may be absent or null; a supplied ID must be a nonempty
string of at most 200 characters. The first supplied ID in an acknowledgement or
final binds the identity, and all later supplied IDs must agree. Missing fields
never erase that identity. This is the same policy for empty and nonempty text.
Content index may be omitted because this session sends exactly one audio input;
if present it must be integer zero. Null, booleans, strings and other indexes are
refused. An otherwise valid failed event remains a failure, not an empty result.

Only completed.transcript can populate the bounded final text; contradictory
completed bodies still fail. Returning a result still requires the local finish
and acknowledged session.finished, so earlier final text cannot escape early.
Created message objects and previews remain non-authoritative and ignored;
unknown transcription event types remain errors. Each session owns one fresh
connection, no redirects/reconnects/replays, and its own audio/response state.
Existing local task ownership, active/deadline checks, cancellation and cleanup
are unchanged. Optional vendor metadata does not replace those isolation guards.

The observer adds only transcript-string/nonempty and missing/int-zero/invalid
content-index booleans, never text or raw service values. Focused local TLS/WSS,
capability and application validation gave **205 passed in 2.71 s**, including
63 probe guard cases. Ruff lint and formatting passed. Local encrypted fixtures
cover optional acknowledgement/final IDs and omitted index independently and
together, Unicode final text, ID binding first at final, retained/conflicting
identities, early result rejection, empty/invalid/oversized IDs, strict provided
indexes for both completed and failed, and unchanged cancellation/stale/deadline
tests. Raw result: `/tmp/inkecho-realtime-optional-metadata-tests.log`.

All six failed/diagnostic receipts remain preserved and are not successful
protocol claims. No live request was made by the implementing agent.

## Final official generated-silence protocol result

The parent agent obtained approval for the final single generated-silence request
after reviewing the optional-metadata policy. The preserved
`build/performance-realtime-silence-optional-metadata.json` records
`protocol_finished_without_speech`, with null error code. Session created,
updated, commit acknowledged, commit sent, finish requested and session finished
are all true; all ten source-generated frames were sent. Completion took
**1241.349 ms**. Transcript nonempty is false and configuration unchanged is true.

This is an actual TLS/Bearer-authenticated official-service result for one second
of generated all-zero PCM, confirming the complete observed manual-mode protocol
path. It does not establish recognized speech, accuracy, every nonempty speech
response schema, microphone-to-cloud behavior, lower desktop latency or Ubuntu
24.04 support. No WAV, microphone recording, local audio, user text or prompt was
used. The earlier rejected public-speech fixture was not retried. Cloud testing
has stopped; there are no further requests in this validation task.
