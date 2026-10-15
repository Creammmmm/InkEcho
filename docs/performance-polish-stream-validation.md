# Streamed polishing provider validation

Date: 2026-10-15. This stage adds provider-level Chat Completions SSE and its
awaited delta callback. Application queue/input acceptance is a separate stage;
this report does not establish real Ubuntu 24.04 desktop latency improvements.

## Contract and bounds

`ProviderClient.polish_stream(provider, key, text, prompt, on_delta)` shares the
existing HTTP lifecycle and `polishing_request_body(..., stream=True)` builder.
It performs one authenticated POST, with no redirect, environment proxy
inheritance, retry or reconnection. It requires `text/event-stream` and parses
only `choices[0].delta.content` as incremental final-answer text. Reasoning
content, empty role chunks and usage events do not emit text. Leading whitespace
is buffered until the first nonblank text, then preserved; an entirely blank
answer emits nothing and fails as empty.

`on_delta` is an async callback. Each callback is awaited before reading the next
event; a bounded application queue can apply backpressure through that await.
The whole-operation timeout includes network work and callback waits. A task
cancellation wakes blocked network or callback waits; a cancellation checkpoint
also precedes callbacks that might otherwise finish without yielding.
The callback/consumer must still enforce task ID, epoch and expiry before actual
input. The provider does not inspect or lock focus, use the clipboard, or submit
text through an input method.

The returned `Result.text` is the assembled answer for accounting, not an
instruction to inject it again. The provider never falls back, repeats a POST,
replays a prefix, or makes a partial delivery successful automatically. The
application must prohibit whole-text fallback after any input has been attempted.
Transport deltas are already incremental: two consecutive `哈` chunks mean `哈哈`.
Repeated chunk IDs identify a request, not unique delta events. Provided IDs are
checked for consistency; they are not used to delete repeated text. Any local
application event deduplication must use an explicit Unicode offset contract.

The parser accepts split UTF-8 code points, CR/LF/CRLF line endings, a leading
UTF-8 BOM, SSE comments and multiline data events. UTF-8 decoding is strict,
including ignored comment/field lines; unpaired JSON surrogate escapes are
rejected before callbacks. The wire body is limited to 2,000,000 decoded HTTP
bytes, an SSE line/event to 262,144 bytes, and assembled text to 200,000 Unicode
code points. All limit failures use sanitized `response` errors.

Completion requires `finish_reason: stop` and `data: [DONE]`. Length truncation,
tool calls, malformed data, a conflicting stream ID, or EOF without completion
fail explicitly. Usage may arrive on the final stop chunk or a separate trailing
usage-only chunk. Missing/invalid token counters remain unknown. `[DONE]`
terminates processing immediately, including when the peer keeps its HTTP
response open; bytes after it are not emitted. Closing an unexhausted response
may discard that socket from the pool, while preserving the shared client.

Protocol references inspected on 2026-10-15:

- [DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)
  documents incremental SSE content, the DONE terminator, stop reasons and final
  usage. The current service may attach usage to its stop chunk.
- [HTTPX async streaming](https://www.python-httpx.org/async/) documents streaming
  response contexts and explicit closure. Connection ownership remains described
  in [provider lifecycle validation](performance-provider-validation.md).

The local OpenLess `63be178b` source was reviewed in `polish.rs` and
`streaming_insert.rs`. Its 12 ms queue flush interval is not a per-character
speed guarantee. This Python parser and tests were independently implemented;
no AGPL source/comments, clipboard fallback or recording-start focus policy was
copied.

## Local evidence and reproduction

```bash
.venv/bin/ruff check src/inkecho/providers.py src/inkecho/polish_stream.py \
  scripts/validation/polish_stream_probe.py tests/test_polish_stream.py \
  tests/test_polish_stream_probe.py
.venv/bin/ruff format --check src/inkecho/providers.py src/inkecho/polish_stream.py \
  scripts/validation/polish_stream_probe.py tests/test_polish_stream.py \
  tests/test_polish_stream_probe.py
.venv/bin/python -m pytest tests/test_providers.py tests/test_polish_stream.py \
  tests/test_polish_stream_probe.py -q --tb=short
```

Provider/SSE tests use a real ephemeral HTTP/1.1 TLS listener on loopback with a
temporary test certificate and fixed synthetic payloads. They do not use vendor
credentials, microphone audio, user documents or desktop input. Probe guard tests
use a fake credential backend and fake transport. The test environment must allow
loopback listeners and asyncio/thread wakeup sockets; an initial sandbox-denied
listener run and a stalled restricted-environment probe test are not passing
evidence. The final checks ran with those local test capabilities enabled.

Observed provider/SSE result before probe guard tests: **149 passed in 6.77 s**.
Probe guard tests separately passed **5 tests**. Final combined result:
**154 passed in 6.99 s**, with Ruff lint and formatting checks passing for all
five changed/new Python files. Raw ephemeral logs:
`/tmp/inkecho-sse-tests.log` and `/tmp/inkecho-sse-probe-tests.log`.

- Actual HTTPS chunks delivered the first nonempty answer before a deliberately
  delayed final chunk, preserving `哈哈🙂é尾` exactly and excluding simulated
  reasoning. This proves incremental local delivery, not real-cloud speed.
- A blocked first callback prevented the next delta from being accepted until
  release; a short total timeout also bounded that callback wait.
- Cancellation while waiting for the next network chunk and while blocked in a
  callback delivered no later text and made no second POST. Callback failure
  stopped at the first attempted delta without replay.
- A peer sending DONE then keeping its HTTP body open returned before that body
  ended; late text was not emitted. The shared client remained usable for three
  successive SSE calls.
- Truncated/tool-call finishes, bad JSON/UTF-8, empty answers, wrong Content-Type,
  HTTP errors, redirects, untrusted TLS and invalid credentials failed with no
  fallback/retry. Pure framing tests split every byte across BOM/Chinese/emoji,
  multiline JSON and each newline convention. Limits, ID consistency, legitimate
  repeated content, usage variants and leading whitespace were exercised.

## Live probe and remaining acceptance

`scripts/validation/polish_stream_probe.py` is an independently reviewable,
explicitly opted-in probe. Running without `--live` returns `not_run` before
reading configuration, the system keyring or making a request:

```bash
PYTHONPATH=src .venv/bin/python scripts/validation/polish_stream_probe.py
```

The live path permits only the currently selected polishing provider at
`api.deepseek.com`, standard HTTPS port, empty or `/v1` path, exact model
`deepseek-flash`. It sends exactly one SSE request with a short public sentence
and fixed prompt defined in its source, not audio, a local file's body, user text
or a user prompt. It sets `max_tokens=64` and uses the verified thinking-disabled
builder without changing saved provider parameters. Credentials are fetched from
SecretStore into memory solely for that official API request. Current-schema
settings/provider files are read without initialization, migration or backup.
Output is limited to fixed error codes, counters, booleans and timing; neither
response text, keys, free-form exceptions nor request dumps are printed.

No live request was made during this module's initial local validation. A future
operator may use the `--live` path only with authorization/approval for that
fixed public-text destination. This probe does not authorize a rejected audio
upload. It also does not measure a provider's internal thinking process or prove
audio transcription, streamed keyboard delivery, package acceptance or Ubuntu
24.04 end-to-end speed.
