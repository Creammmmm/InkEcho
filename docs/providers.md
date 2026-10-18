# Cloud provider adapters

`inkecho.providers.ProviderClient` exposes async `transcribe`, `polish`, `models`,
`check_connection`, streamed `polish_stream` and explicit `test_capability`
methods. It consumes the
separate `config.Provider` record and a key fetched by the caller from
`FileCredentialStore`; it never persists keys. `Result` contains text, duration and
optional supplier token counts. Text is excluded from its representation.

## Supported protocols and configuration

The `qwen` transcription adapter implements Alibaba's documented synchronous
OpenAI-compatible Qwen-ASR request: `POST /chat/completions`, a user content item
of type `input_audio`, and a WAV data URI under `input_audio.data`. Optional
`asr_options` are passed separately. This is **not** a generic text-chat request
or multipart `/audio/transcriptions` upload. Filetrans and realtime models use
different protocols. `ProviderClient.transcribe` remains HTTP-only and refuses
known realtime/streaming/filetrans families and explicit realtime settings before
encoding/upload. Models remain editable configuration; the adapter does not
hardcode one model ID. Arbitrary future HTTP model IDs remain configurable.
Discovery may list models that the selected protocol cannot invoke; availability
is not capability proof.
[Official Qwen-ASR reference](https://help.aliyun.com/en/model-studio/qwen-asr-api-reference).
The realtime family uses a separate WebSocket session protocol, described in the
[official realtime guide](https://help.aliyun.com/en/model-studio/qwen-asr-realtime-interaction-process).

### Explicit Qwen realtime selection

The transcription page now offers completed-recording HTTP upload or explicit
Qwen realtime WebSocket. Selecting realtime stores
`parameters.asr_protocol = "qwen_realtime"`; a custom WSS address is stored as
`parameters.realtime_url`. These are local adapter-selection fields, not HTTP
request-body parameters. The advanced JSON editor and controls stay synchronized;
switching protocol preserves unrelated JSON fields, malformed JSON is never
silently replaced, and selecting an option does not save configuration, change
the model, or change the recording rate automatically.

For the recognized official Beijing/Singapore shared or workspace hosts,
`RealtimeConfig` derives `/api-ws/v1/realtime` using `wss://` and appends the chosen
model. A custom HTTP gateway must supply an explicit WSS address implementing the
Qwen realtime protocol; changing `stream=true` or guessing its HTTP-to-WebSocket
path is not supported. The current adapter requires 16 kHz mono PCM16. Choose
16 kHz manually in recording settings before testing or recording; no automatic
resampling or settings rewrite is claimed.

`validate_provider_protocol` validates this explicit configuration and rejects
known HTTP, filetrans or unrelated streaming models paired with realtime. The
same validation runs before the main recorder, credential lookup and connection
creation. The UI additionally checks the saved sample rate. Unknown future model
IDs still need capability verification rather than being assumed compatible.

During recording, bounded 100 ms PCM frames are sent over one authenticated WSS
session. On stop the adapter commits the buffered audio and requests session
completion; only a final correlated transcript is accepted. No reconnect, HTTP
fallback, clipboard or system-input-method fallback is made. The implemented
protocol has real local TLS/WSS fixture evidence; authenticated vendor audio and
Ubuntu 24.04 end-to-end acceptance remain separate pending work. See
[realtime validation](performance-realtime-validation.md).

The explicit capability test still records a completed three-second WAV, checks
16 kHz mono uncompressed PCM16 including truncated/odd samples before connecting,
then feeds its PCM through the actual WSS adapter with bounded backpressure. It
waits for final session completion and closes the connection on success, failure,
timeout or cancellation. It does not inject the result, and it does not pretend
that replaying a completed sample proves live-microphone streaming timing.

The same `qwen` adapter also implements the synchronous DashScope route for
`qwen-audio-3.x-asr-flash` and `fun-asr-flash` (including dated revisions). It sends
WAV base64 audio with `X-DashScope-SSE: disable`, derives the actual sample rate
from the WAV, and parses `output.text` or the nested sentence text. The configured
origin and any proxy path prefix are preserved: only `/compatible-mode/v1` becomes
`/api/v1`; an existing `/api/v1` is accepted. Unknown API prefixes fail explicitly.
The original provider configuration is not mutated. Optional DashScope parameters
are `language_hints`, `vocabulary`, `vocabulary_id`, `speaker_diarization_enabled`
and `keep_dialect`; format and sample rate always describe the actual recording.
[Official synchronous HTTP reference](https://help.aliyun.com/en/model-studio/fun-asr-flash-recorded-speech-recognition-http-api).

The `openai` polishing adapter sends system/user text messages to
`POST /chat/completions`, matching DeepSeek's documented API. The DeepSeek base
URL is `https://api.deepseek.com`. Optional sampling/token parameters are
allowlisted; they cannot replace messages, authentication or streaming behavior.
[DeepSeek chat API](https://api-docs.deepseek.com/api/create-chat-completion/).

The polishing page's `边润色边输入` checkbox controls
`Settings.polishing_streaming` (default true; an older current-schema settings
file can supply this default without being rewritten merely by reading it).
When enabled, final-answer SSE deltas feed one serialized, bounded output queue;
reasoning chunks are never sent as input. Content remains incremental, legitimate
repeated words are preserved, and cancellation/expiry/replacement stop unsent
text. Once output has been attempted, later failure stops the remainder rather
than replaying the full answer or falling back to the whole original transcript.
Before any output attempt the existing configured fallback policy still applies.
See [streamed polishing](performance-polish-stream-validation.md) and
[streamed input](performance-pipeline-validation.md).

Polishing capability tests use the **saved** streaming setting captured before
credential lookup: an SSE-selected configuration is tested with actual SSE, not
only synchronous chat. No result from this test is typed into another window.
Changing protocol, WSS address, advanced JSON or the streaming checkbox invalidates
late UI results. Save preferences first so the capability mode matches the desired
application behavior.

Verified official origin/model combinations default to documented thinking-off
controls; generic OpenAI-compatible gateways receive no speculative parameter.
Explicit supported thinking opt-ins remain possible. The exact narrow capability
table and shared-client ownership are recorded in
[provider performance validation](performance-provider-validation.md).

Both roles use `GET /models` for discovery where available. Discovery verifies
that endpoint only; its result explicitly has `capability_verified=False`.
Models that lack discovery remain manually configurable. The explicit
`test_capability` operation makes a potentially billable request with supplied
test audio or a small text probe; the UI must explain this and never run it
automatically. A successful model listing never marks ASR/text capability as
verified. [DeepSeek models API](https://api-docs.deepseek.com/api/list-models/).

These official pages were inspected on 2026-10-12. Region-specific URLs and
model availability must be checked against the user's account. A cloud account
key and model ID must be configured before real use. The initial development
validation did not make authenticated vendor requests. Subsequent repair evidence,
including the distinction between simulated and authenticated calls, is tracked in
[provider repair validation](provider-repair-validation.md).

## Request safety and lifecycle

- Production requests verify TLS certificates, disable environment proxy
  inheritance and reject redirects. Provider configuration only permits HTTPS
  URLs without embedded credentials, queries or fragments.
- One application-lifecycle HTTP client retains its connection pool; role
  policies borrow it with independent deadlines. Shutdown closes owned resources,
  and caller-injected HTTP clients remain caller-owned. Response cookies are not
  retained as implicit API authentication.
- A whole-request asyncio deadline defaults to 30 seconds and is configurable
  within 0.05–120 seconds. Cancellation propagates without a late result.
- Transcription/polishing POSTs are never automatically retried. Idempotent
  discovery retries at most once for selected transient statuses, inside the
  same deadline. This avoids duplicating billable requests.
- Response bodies are bounded to 2 MB. WAV headers, channels, sample width,
  nonempty complete frames and encoded input size are checked before upload.
- Failures use fixed categories/messages. Provider error bodies, raw HTTP
  exceptions, credentials and transcript text are never included in errors or
  logged. Missing/invalid token usage stays unknown, never fabricated as exact.
- Provider code does not choose a target or inject text; task ID/focus checks
  remain the controller and backend's responsibility.

Audio and text are transmitted to the configured cloud service when these
methods are invoked. The caller should release its audio/text payload after
the bounded task; no local history is kept here. Keyring availability, recording
and polishing fallback policy belong to separate modules.

## Local verification

```sh
uv run pytest -q tests/test_providers.py
```

Tests create a real local HTTPS server, a temporary self-signed certificate and
fake credentials. Only the test client trusts that certificate. Production
certificate validation is independently tested to reject it. The host must
provide `openssl` and permission to bind loopback sockets. Restricted agent
sandboxes that deny local sockets require the normal authorized host test
environment; no external provider endpoint is used.

The local server simulates ASR, polishing, models, malformed/empty responses,
authentication/rate/model/server failures, delayed replies, redirects and
oversized bodies. Tests inspect the actual transmitted authorization header,
editable model ID, WAV data URI and separate polishing system/user messages.
They also check exact and missing usage, bounded retries, whole-request timeout,
cancel propagation, unsupported configuration and rejected/truncated audio.
These are **real local transport tests with simulated service behavior**, not
authenticated vendor tests or speech-recognition quality evidence.

Measured on 2026-10-12: all 33 provider tests passed in the authorized local
test environment. Ruff lint/format and whitespace checks also passed.

The same test transport can support desktop integration tests: create a
`ProviderClient(http=trusted_local_https_client)` and use the fixture's HTTPS
base URL. The production client default remains unchanged; do not disable TLS
globally or store a test CA in user application settings.

## Historical HTTP protocol mismatch regression (2026-10-13)

The user selected `qwen3-asr-flash-realtime` with an HTTP compatible-mode endpoint.
That model requires WebSocket; changing only a key cannot make this HTTP request
format compatible. The HTTP adapter accepts the documented `qwen3-asr-flash` model
as one example, subject to the account's actual access and region. The application
does not replace the selected model silently.

All **60 local HTTPS provider tests passed** after adding protocol preflight and
the synchronous DashScope route. Tests
prove rejected families generate no HTTP request or base64 audio copy, rejected
capability tests do not require audio first, a future arbitrary HTTP model still
reaches the configured endpoint, and discovery remains distinct from capability.
A separate root-agent authenticated call using the configured workspace and
`qwen-audio-3.0-asr-flash` succeeded with a public audio fixture; see the linked
repair validation for its precise scope.
