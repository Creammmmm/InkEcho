# Provider protocol mismatch repair

Date: 2026-10-13, Asia/Shanghai.

## Observed mismatch

The configured `qwen3-asr-flash-realtime` model was being sent to the Qwen
OpenAI-compatible HTTP `/chat/completions` endpoint. Alibaba documents distinct
protocols: `qwen3-asr-flash` supports this HTTP request format, the realtime family
uses WebSocket sessions, and Filetrans uses an asynchronous DashScope API.
See the [official non-realtime reference](https://help.aliyun.com/en/model-studio/qwen-asr-api-reference)
and [official realtime connection guide](https://help.aliyun.com/en/model-studio/qwen-asr-realtime-interaction-process),
checked during this repair. A visible model in a listing is not evidence of
compatibility with InkEcho's implemented HTTP adapter.

## Provider change

The public synchronous `validate_provider_protocol(provider)` helper rejects known
Qwen/Fun-ASR transcription family names containing `realtime`, `streaming` or `filetrans`
components with the fixed `protocol` error code. It does not inspect or require a
key. The adapter applies it before audio parsing/base64 encoding/network requests;
capability testing applies it before requiring an audio sample. The UI uses the
same check to avoid capturing microphone audio for a known protocol mismatch.

HTTP models remain configurable. This is a small explicit incompatibility guard,
not an allowlist claiming that every other model is supported. Normal service
capability testing remains necessary, and model discovery remains independently
available. No user model is silently substituted by this validator.

## Local provider verification

```sh
.venv/bin/python -m pytest -q tests/test_providers.py
.venv/bin/ruff check src/inkecho/providers.py tests/test_providers.py
.venv/bin/ruff format --check src/inkecho/providers.py tests/test_providers.py
```

Result: **60 passed** against real local HTTPS servers with disposable fake keys.
Ruff checks passed. New regression cases cover realtime/versioned realtime,
streaming, Filetrans/versioned Filetrans and case/whitespace variations; all reject
before encoding or sending audio. Both the documented HTTP example and an arbitrary
future model ID reach the local HTTP endpoint with their exact configured IDs.
Discovery can return realtime models without marking their capability verified.

The new synchronous DashScope adapter also passed same-origin/prefix preservation,
exact data-URI/header/body checks, top-level and nested text parsing, accurate
reported token parsing, malformed/empty output rejection and unsafe/ambiguous URL
rejection. A malformed WAV with a zero sample rate is rejected before duration
calculation or network activity.

These tests do not contact Alibaba or DeepSeek. They do not access the user's keys
or record microphone input. Real vendor, account/region access and recognition
results remain separate from this local validation.

## Synchronous models and authenticated verification

The account's authenticated model discovery succeeded but did not offer
`qwen3-asr-flash`. Its ASR list included `qwen-audio-3.0-asr-flash`,
`fun-asr-flash-2026-06-15` and the incompatible realtime model. The repair therefore
adds the documented DashScope synchronous request format for the available Qwen
Audio/Fun-ASR-Flash families; it does not send them as OpenAI chat completions.
The [official HTTP reference](https://help.aliyun.com/en/model-studio/fun-asr-flash-recorded-speech-recognition-http-api)
explicitly supports WAV base64 data URIs and describes the distinct response fields.

The root agent then made **one successful authenticated ASR POST** through the
production `ProviderClient`, using the existing configured workspace hostname and
key reference, with the model replaced in memory by `qwen-audio-3.0-asr-flash`.
The fixed [public vendor audio fixture](https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/sensevoice/rich_text_example_1.wav)
was 17.645 seconds, mono, 16-bit, 16 kHz. The call returned **203 characters in
2.75 seconds**. The request was not retried. The transcript, raw response and key
were not printed or logged; no microphone capture or target insertion occurred.

This is authenticated evidence of the actual configured provider's request and
response path, separate from the earlier successful discovery GET and the local
HTTPS simulations. It does not prove real microphone recognition quality, DeepSeek
polishing, or final desktop insertion. The provider implementation agent made no
authenticated vendor requests; this result was independently reported by the root
agent. User configuration persistence and UI/package checks are separate release
steps.
