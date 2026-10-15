# Provider protocol and capability UI validation

Implemented on 2026-10-15; final local validation completed on 2026-10-16.
This stage exposes the implemented HTTP/realtime ASR and buffered/streamed
polishing routes without modifying existing model choices, sample rates or
persisted user files automatically.

## Behavior and implementation

The transcription page offers completed-recording HTTP upload or explicit Qwen
realtime WebSocket. A separate optional field accepts the actual WSS endpoint
for a custom gateway; recognized official endpoints can derive it. The controls
and advanced JSON synchronize through `asr_protocol` / `realtime_url`. Changing
protocol preserves unrelated JSON fields. Invalid JSON, an unknown protocol or
an invalid endpoint value is not silently replaced. Fields change the form only
until the user saves, and neither model nor recording rate is changed for them.

The UI and task startup use `validate_provider_protocol`: explicit realtime
configuration must pass `RealtimeConfig`, while known HTTP/filetrans/unrelated
streaming models cannot be paired with realtime. `ProviderClient.transcribe`
retains a separate HTTP-only guard, even when the same provider would be valid
through the realtime adapter. UI and task startup check 16 kHz before key lookup,
recording or opening a realtime session. Users must select that rate themselves.

`ProviderClient.test_capability` routes an explicitly selected realtime provider
to `provider_capability.realtime_capability`. The helper validates a completed
WAV before opening a socket: bytes only, size/duration limits, mono,
uncompressed PCM16, exactly 16 kHz, nonempty samples, complete declared frames
and no incomplete trailing sample. It sends PCM through the production WSS
adapter with bounded backpressure, commits, waits for the final correlated
result, and closes on success, failure, cancellation or timeout. It does not
inject text, send a WAV through HTTP, or pretend this completed-sample test is
live-microphone acceptance. A closed provider lifecycle cannot reopen WSS.

The polishing page adds `边润色边输入` bound to
`Settings.polishing_streaming`. The page explains that failure after input has
been attempted stops the remainder and does not replay the whole original text.
Capability tests snapshot the **saved** setting before credential lookup and
test the selected SSE or buffered route accordingly; save first to change the
mode used for that test. Protocol, WSS address, advanced JSON and the streaming
checkbox all update the form revision, so late success/failure cannot overwrite
a newly edited form. Save also captures preferences before an awaited keyring
write.

The unrelated Qt/HTTP async-generator cleanup discovered during full pipeline
verification was fixed and committed separately; see
[Qt cleanup regression](qasync-stream-cleanup-validation.md).

## Reproduce the local checks

```bash
.venv/bin/ruff check src/inkecho/app.py src/inkecho/providers.py \
  src/inkecho/provider_capability.py src/inkecho/ui/providers.py \
  tests/test_application_realtime.py tests/test_provider_capability.py \
  tests/test_ui.py tests/test_providers.py tests/test_polish_stream.py
.venv/bin/ruff format --check src/inkecho/app.py src/inkecho/providers.py \
  src/inkecho/provider_capability.py src/inkecho/ui/providers.py \
  tests/test_application_realtime.py tests/test_provider_capability.py \
  tests/test_ui.py tests/test_providers.py tests/test_polish_stream.py
.venv/bin/python -m pytest tests/test_ui.py tests/test_providers.py \
  tests/test_provider_capability.py tests/test_polish_stream.py \
  tests/test_application_realtime.py tests/test_runtime.py \
  tests/test_runtime_streaming.py -q --tb=short
```

Tests use temporary configuration and key fixtures, a real offscreen Qt UI,
actual loopback HTTPS and WSS with trusted ephemeral test certificates, and
synthetic PCM bytes. No real microphone, cloud service, user document, clipboard,
system-input-method delivery or actual desktop keyboard injection is used.
Loopback and asyncio/thread wakeup sockets must be permitted in the test runtime.

An initial **215 passed** run still emitted test-server thread tracebacks. Its
log is preserved at `/tmp/inkecho-ui-protocol-tests.log`. A strict fixture
diagnostic identified an expected `BrokenPipeError` (errno 32) while a test
client rejected a 429 response and closed its socket. The diagnostic log is
`/tmp/inkecho-provider-fixture-diagnosis.log`. The HTTP/SSE fixtures now precisely
handle expected broken-pipe/reset/TLS disconnects, join their handler threads,
and collect any other error as a failing fixture assertion. The WSS capability
fixture similarly permits connection closure and fails on any unexpected server
exception. No broad exception or warning suppression is used to pass acceptance.

The final clean combined run passed **221 tests in 11.35 s**, with no
server tracebacks, unraisable exceptions or loop errors. The final strict-WSS
rerun is recorded at `/tmp/inkecho-ui-protocol-clean-tests.log`. Ruff lint and
format checks passed for the changed Python files.

Actual local observations:

- The WSS capability helper sent the exact synthetic PCM payload in bounded
  frames through the production adapter, with one commit/finish sequence and
  final text only. It made no HTTP upload. Cancel during handshake/final wait
  and the whole-operation timeout closed the connection without replay.
- Invalid bytes, compressed/wrong-rate/wrong-channel/wrong-width WAVs,
  empty/truncated/odd samples failed before connection construction. The
  HTTP-only transcribe guard and a closed lifecycle also refused WSS before
  sending. Explicit realtime plus a known HTTP model failed task preflight
  before keys, microphone, desktop authorization or network creation.
- Actual HTTPS polishing capability used `stream=true` and the SSE parser when
  requested; offscreen UI tests verified the saved checkbox selects the mode.
- UI tests verified JSON preservation, malformed JSON refusing save, official
  endpoint derivation, custom-endpoint preflight, 16 kHz refusal without settings
  edits, streaming checkbox persistence, keyring-wait preference snapshots and
  late-result revision checks for each new control.

## Visual inspection and live scope

Source UI screenshots use a temporary synthetic configuration and offscreen Qt:
`build/provider-ui-realtime.png` and `build/provider-ui-polish.png`. Both were
visually inspected by the implementing and root agents at 1220×1060: protocol,
optional endpoint, JSON, checkbox, error/fallback explanation and action buttons
are readable without overlapping content. This is a source/offscreen visual
check, not packaged-native display evidence.

The parent agent separately approved and ran exactly one fixed-public-text SSE
request to official DeepSeek, recorded in
[SSE validation](performance-polish-stream-validation.md). No further live
request, audio upload or credential access was performed for this UI stage.
Realtime vendor audio capability, packaged voice workflow, actual Ubuntu 24.04
desktops and numerical end-to-end latency gains retain their separate acceptance
requirements; local fixture success does not establish those claims.

## Saving realtime URLs safely (2026-10-16)

Review found that rejecting a credential-bearing WSS URL only at startup was
too late: the string could first be saved inside provider JSON. The save action
now validates an explicit realtime protocol and every `realtime_url` value before
reading/clearing the key field, writing the keyring or saving any configuration.
An unselected advanced-JSON URL is also checked, so removing the protocol flag
cannot make a credential URL saveable. Ordinary HTTP drafts without a model
remain saveable.

Reproduction: `.venv/bin/python -m pytest tests/test_ui.py -q --tb=short`.
Observed **43 passed in 3.93 s**, with Ruff lint and format checks passing.
Eight isolated cases cover selected/unselected realtime URLs containing fake
userinfo, API-key/token queries or fragments. Each preserves all original JSON
file bytes and the form's malformed URL, leaves the unsaved fake key in its
input field, and proves zero keyring-save calls. The HTTP blank-model draft
regression also passes. Only temporary fixture configuration and fake secret
strings are used; no user configuration, real keyring, cloud service or audio
is accessed. Raw ephemeral result: `/tmp/inkecho-ui-url-save-tests.log`.
