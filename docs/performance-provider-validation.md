# Provider connection reuse and thinking control

Date: 2026-10-15. This is the second performance module. It changes transport
ownership and request construction, not desktop keyboard pacing. Current-cursor
input semantics and existing platform limitations remain applicable. Stage 0
input evidence is recorded separately in `feasibility-report.md` and the later
`native-wayland-parent-validation.md`; this report adds no Ubuntu 24.04 support
claim.

## Implementation and ownership

One application-lifecycle `ProviderClient` lazily creates one `httpx.AsyncClient`.
`owner.with_timeout(seconds)` returns a borrower sharing that pool with an
independent whole-request and HTTP timeout. Transcription, polishing, model
discovery and capability tests can reuse connections to the same origin.
Different origins remain separate connections inside HTTPX's pool.

`await owner.aclose()` marks the lifecycle closed, including existing borrowers,
and closes its own HTTP client exactly once. Closing a borrower is a no-op. An
HTTP client supplied through `http=` remains caller-owned and is never closed by
this adapter. The application must cancel and await outstanding operations before
closing the owner. Closing an unused owner allocates no network resources.
Cleanup is shielded so cancellation of a closing caller does not cancel the
already-started HTTP cleanup task. Reopening a closed lifecycle is rejected.
Use the owner in one event loop; it is not a process-global pool.

Production TLS validation, `trust_env=False`, no redirects, bounded response
bodies and whole-request deadlines remain in force. POST requests still have
no automatic retries, including cancellation and timeouts. Bearer credentials
are attached to individual requests, never default client headers. A rejecting
cookie policy prevents response cookies creating an implicit shared API session.
The optional caller-owned HTTP client remains a trusted test/integration seam.

The application integration uses `with_timeout` for each role and closes the
owner during shutdown. The historical alpha6 live-cloud probe was minimally
updated to close its short-lived clients; its old targeted-input workflow is
still historical and was not run as current-desktop evidence.

## Verified thinking controls

`polishing_request_body(provider, text, prompt, stream=False)` is the single
request builder for buffered and future streaming polishing. It defaults to
disabling thinking only for the following documented host/path/model matches:

| Endpoint and exact models | Default body field | Explicit opt-in |
| --- | --- | --- |
| `api.deepseek.com`, path empty or `/v1`, standard HTTPS port; `deepseek-flash`, `deepseek-v4-pro`, documented legacy alias `deepseek-v4-flash` | `thinking: {type: disabled}` | `parameters.thinking: {type: enabled}` |
| Official DashScope Beijing/Singapore/Virginia shared hosts or a workspace subdomain under `cn-beijing.maas.aliyuncs.com` / `ap-southeast-1.maas.aliyuncs.com`; path `/compatible-mode/v1`; `qwen-plus`, `qwen-plus-latest`, `qwen-plus-2025-04-28`, `qwen-flash`, `qwen-flash-2025-07-28`, `qwen3.6-plus`, `qwen3.6-plus-2026-04-02` | `enable_thinking: false` | `parameters.enable_thinking: true` |

This intentionally small capability table is not a restriction on editable chat
model IDs. Other models and origins still use ordinary chat requests without
speculative controls. In particular, a custom provider named DeepSeek, an
arbitrary proxy serving a DeepSeek model, old `deepseek-chat` / `deepseek-reasoner`
aliases, unknown revisions and thinking-only models do not inherit an assumed
capability. Unknown thinking fields, wrong JSON types, conflicting
`reasoning_effort`, and attempted overrides of messages/stream fail before
network access. Explicit supported opt-ins take precedence over the low-latency
default. No prompt suffix or model substitution is used.

Official references inspected on 2026-10-15:

- [DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)
  and [thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/)
  document `thinking.type`; the current models default to thinking enabled.
- [DeepSeek models](https://api-docs.deepseek.com/quick_start/pricing/)
  names the two current models and the accepted `deepseek-v4-flash` alias.
- [Alibaba thinking mode](https://help.aliyun.com/zh/model-studio/deep-thinking)
  distinguishes hybrid models and models whose thinking cannot be disabled.
- [Alibaba endpoint table](https://help.aliyun.com/en/model-studio/base-url)
  documents the recognized official shared and workspace endpoint forms.

Model availability and actual cloud behavior are separate from this documented
capability table. This stage did not use a real cloud key or make authenticated
vendor calls. It proves request construction, not measured cloud latency or
successful capability access in every region/account.

## Reproduce the local functional evidence

From the repository with development dependencies installed:

```bash
.venv/bin/ruff check src/inkecho/providers.py tests/test_providers.py \
  scripts/validation/native_cloud_workflow_probe.py
.venv/bin/ruff format --check src/inkecho/providers.py tests/test_providers.py \
  scripts/validation/native_cloud_workflow_probe.py
.venv/bin/python -m pytest tests/test_providers.py -q --tb=short
```

The tests create an ephemeral local CA certificate with OpenSSL and an actual
HTTP/1.1 HTTPS listener on loopback. Production client construction is exercised
with only the CA trust root replaced for that listener; `verify=True`, no proxy
inheritance and redirect rejection are asserted. All request content and keys
are fixed synthetic fixtures. No real microphone, user text, cloud credentials,
desktop input, clipboard or system input method is used. A restricted sandbox
must allow a temporary loopback server for these checks.

Observed result: **103 passed in 4.48 seconds**. Raw local result is
`/tmp/inkecho-provider-http-tests.log` (ephemeral, not required for reproduction).

- The baseline of three independently closed request owners establishes three
  actual TLS connections. One lifecycle shared by two role policies makes three
  successful requests over **one** actual TLS connection. Server active sockets
  return to zero after owner close. This is a connection-count improvement; no
  wall-clock speedup is inferred from loopback server timing.
- Requests with three different fixture keys carry their own Authorization
  value; response cookies are not sent on the next request.
- A short-timeout borrower times out while a later longer-timeout operation
  succeeds through the same pool owner. Cancelling a request propagates
  `CancelledError`, has no late result, and does not close the shared client or
  prevent a subsequent request. Cancelled/partial connections may be replaced;
  no retry of their POST body is attempted.
- Owner/borrower/external ownership, idempotent close, cancellation of a closing
  caller, closed-lifecycle rejection, certificate rejection, redirect rejection,
  response limits, sanitized errors and existing GET-only retry tests pass.
- Pure request-construction cases cover supported defaults/opt-ins, wrong
  JSON types, conflicts, unknown hosts/models/paths/ports and misleading hostname
  suffixes. They do not simulate an authenticated official service response.

## Remaining acceptance

Real-vendor first-result and total timing, the complete microphone-to-input
pipeline, real Ubuntu 24.04 sessions, realtime ASR, streamed polishing and keyboard
pacing need their own subsequent evidence. No numerical user-visible latency
reduction is claimed by this stage. The changed module has not been published or
released as part of this work.

Reference review: the local OpenLess checkout at `63be178b` was read at
`openless-all/app/crates/openless-core/src/net.rs` and `polish.rs`. Its shared
client concept and vendor-specific control idea informed this review. The Python
implementation and tests were written independently against HTTPX and the
official protocol documents; no AGPL source or comments were copied.
