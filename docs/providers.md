# Cloud provider adapters

`inkecho.providers.ProviderClient` exposes async `transcribe`, `polish`, `models`,
`check_connection` and explicit `test_capability` methods. It consumes the
separate `config.Provider` record and a key fetched by the caller from
`SecretStore`; it never persists keys. `Result` contains text, duration and
optional supplier token counts. Text is excluded from its representation.

## Supported protocols and configuration

The `qwen` transcription adapter implements Alibaba's documented synchronous
OpenAI-compatible Qwen-ASR request: `POST /chat/completions`, a user content item
of type `input_audio`, and a WAV data URI under `input_audio.data`. Optional
`asr_options` are passed separately. This is **not** a generic text-chat request
or multipart `/audio/transcriptions` upload. Filetrans and realtime models use
different protocols and are not supported by this adapter. Models remain
editable configuration; the adapter does not hardcode one model ID.
`validate_provider_protocol(provider)` rejects known Qwen/Fun-ASR model names containing
`realtime`, `streaming`, or `filetrans` protocol components before recording in the
UI and before encoding/upload in the adapter. The fixed `protocol` error explains
the mismatch. Discovery may still list these models; list availability does not
mean this HTTP adapter can invoke them. Arbitrary future HTTP model IDs remain
configurable rather than being restricted to a hardcoded supported-model list.
[Official Qwen-ASR reference](https://help.aliyun.com/en/model-studio/qwen-asr-api-reference).
The realtime family uses a separate WebSocket session protocol, described in the
[official realtime guide](https://help.aliyun.com/en/model-studio/qwen-asr-realtime-interaction-process).

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

## Protocol mismatch regression (2026-10-13)

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
