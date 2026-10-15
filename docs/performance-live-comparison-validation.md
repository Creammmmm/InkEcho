# Bounded public-audio comparison core — 2026-10-16

The independent `scripts/validation/performance_live_comparison.py` now prepares
a complete configuration A/B comparison through the actual a13 Session,
ProviderClient, HTTP/WSS parsers, polishing/SSE and KeyboardInput. Preparation
and local protocol checks are complete; **no real cloud comparison has run**.
The Ubuntu 24.04 desktop adapter is still required before this core can execute
the target-platform comparison. It must not substitute Ubuntu 26.04 evidence.

## Comparison and execution gates

Both arms use the same a13 artifact, not different product versions:

| Configuration | ASR | Polishing |
| --- | --- | --- |
| A | HTTP `qwen3-asr-flash` | Buffered `deepseek-flash` |
| B | WSS `qwen3-asr-flash-realtime` | SSE `deepseek-flash` |

This is a combined configuration comparison; a difference cannot be attributed
to one optimization. The saved user's absent streaming setting defaults to true;
configuration A is an explicit test condition, not a claimed original setting.
Each arm creates a fresh cold HTTP client. There is no discovery, warmup,
automatic retry, reconnection or transcript reuse. The send boundary reserves
at most one ASR and one polishing operation per arm, four in total, before any
transport send or realtime start. Reserved counts are persisted immediately;
failure does not refund them or permit another request.

The fixed public input is `/tmp/inkecho-public-asr-fixture.wav`, SHA-256
`0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf`:
571456 bytes, mono PCM16/16000 Hz, 282322 frames, 17.645125 seconds.
Its recorded public source is
<https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/sensevoice/rich_text_example_1.wav>.
Only local bytes/header/hash inspection occurred here; this phase neither
downloaded, played nor uploaded it. A emits the exact pinned WAV bytes after
the full recording timeline. B feeds the decoded original PCM on that timeline,
177 chunks, at most 3200 bytes each, with a 1444-byte final chunk. A pure clock
test verifies the full timeline and original-byte preservation without playback.

The planned destinations are exactly:

- A: `https://ws-viafqlzm0ma8r2at.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions`.
- B: `wss://ws-viafqlzm0ma8r2at.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime?model=qwen3-asr-flash-realtime`.
- Both polishing calls: `https://api.deepseek.com/chat/completions`.

Polishing uses a fixed public instruction to preserve meaning/language and
return at most 80 Unicode characters, `max_tokens=128` and thinking disabled.
Strict request checks reject additional fields, changed models, URLs, methods,
audio bytes or budget. Production no-redirect behavior remains in use.

The default CLI is a stdlib-only plan: it audits the full artifact inventory,
WAV, six script fingerprints and the three saved JSON files without importing
Qt, HTTP clients, the application or keyring. Metadata hashes bind the same raw
bytes that were parsed. Provider role/origin/model and canonical credential
references must match; arbitrary names, private prompts and free-form refs
are not emitted. Credential-shaped ordinary JSON fields are rejected.
`--plan-live` is only a pure planning flag and conflicts with either execution
flag. Neither an execution flag nor a plan fingerprint grants human consent.

Only the explicit live branch, after an exact accepted fingerprint and complete
revalidation, can lazily initialize SecretStore. The same full checks run again
before each credential access. Offline mode returns fake credentials and tests
forbid initializing SecretStore. No live branch, real keyring, microphone or
cloud endpoint was used in this phase. The earlier automatic approval rejection
of public-WAV upload remains in force; this implementation does not retry it.

## Output, diagnostics and lifecycle

Production normalization and successful insert counts build the expected text
in RAM. Any partial or uncertain insert prevents further expected-text replay.
The owned GTK target uses the existing anonymous-socket memory protocol, not a
body file. A fixture-only delivery guard checks owned PID/start/toplevel and
the production current focused child before each press; releases remain allowed.
Recording/feed reads no focus. Activation is placed before the recording clock.
These controls do not bind product output to a recording-time target.

The stop-to-first dispatch comes from production TaskTiming and must agree
exactly with its separately reported field. Normal acceptance requires equal
nonzero confirmed, dispatched and readback lengths, RAM-exact output, no Session
diagnostics, and both valid dispatch and first-buffer timings. Acceptance also
requires a finite output-completed duration at or after the first dispatch.
The same coroutine polls readback every 20 ms after stop. Its first nonempty
buffer observation is not glyph rendering, has polling/roundtrip overhead and is not comparable with
older reports that did not make this observation.

Only fixed-schema flags, finite timings, lengths, call counts, safe diagnostic
codes and source/process identities are persisted. Unknown exceptions never
print their message or traceback. The first failure phase/code and reserved
counts survive later cleanup. Offline results use the same strict safe schema.
Cancellation/expiry fixtures must show exactly two dispatched/readback characters
and an unconfirmed partial insert; late response must show zero output, no
polishing call and an actual late-response attempt. CLI acceptance itself rejects
tampered full replay, missing timing or inconsistent counts.

Worker SIGINT/SIGTERM routes through Session.cancel and normal cleanup. An
interrupted observer does not cancel the independently sessioned worker. Its
exclusive 0700 HOME/XDG/TMP profile persists beside the handle, so observation
interruption cannot remove a producer's runtime files. Session producers and
Session.close precede target close; only the original Popen owner records an
exit. An observation timeout retains the same handle/operation without killing,
restarting or beginning the next arm. The live lifecycle was not exercised here.

## Reproduction and completed checks

The exact artifact is `dist/InkEcho-0.1.0a13-x86_64.AppImage`, 108907000 bytes,
SHA-256 `8dce4eedee71373a27e0e6507592b1240617412a8a6f114230b9a53f4d286a89`,
product commit `eeb2d0ce8f8c5a6690b0ab54e0196da4254eb767`.
The full inventory has 3958 files, 1048 symlinks and 43 application sources.
Existing phase-one/two plans, raw results and audit-source copies were preserved;
this phase uses its own fingerprint and evidence directory.

```sh
.venv/bin/ruff check scripts/validation/performance_live_comparison.py \
  tests/test_performance_live_comparison.py
.venv/bin/ruff format --check scripts/validation/performance_live_comparison.py \
  tests/test_performance_live_comparison.py
.venv/bin/python -m pytest -q tests/test_performance_live_comparison.py --tb=short
.venv/bin/python scripts/validation/performance_live_comparison.py \
  --package-root /home/lth/github/InkEcho/build/performance-a13-extracted-iwmzy2mn/squashfs-root/packages \
  --config-root /home/lth/.config/inkecho
```

Ruff checks passed; the focused suite passed **57 tests in 6.79 seconds**.
Evidence: `build/performance-live-comparison-core-r3/tests.log`.
Tests include exact budget reservations before failures, same-byte config hashes,
credential gates, unknown-error redaction, original-WAV timeline, partial-output
isolation, explicit signal cancellation, and both real local TLS parser paths.
Source tests are labelled `source_protocol_synthetic_display`.

The final read-only plan is
`build/performance-live-comparison-core-r3/plan.json`, fingerprint
`f2ac077ebf67fc67616fa9eeb6f320801c33763a9e411c9b4323d210d9e0fa99`.
The separate r1/r2 plans and outputs remain historical pre-final snapshots.
To reproduce a headless package scenario, append to the plan command:

```sh
  --offline --scenario normal \
  --accept-plan-sha f2ac077ebf67fc67616fa9eeb6f320801c33763a9e411c9b4323d210d9e0fa99
```

Repeat with `cancel`, `expire` and `late`, keeping results separate. This launcher
uses the actual a13 shipped Python with isolated offscreen Qt and `asyncio.run`,
not ManagedQt or a real desktop. The package audit includes nine actual module
origins, including `inkecho.security`; importing that module is not credential
backend initialization. The local TLS fixture uses approximately 200 ms of
generated PCM and fixed responses, **not the public WAV**. Thinking/body checks
here prove request construction, not cloud behavior or recognition accuracy.

The four final actual-package scenario outputs and stderr files are under
`build/performance-live-comparison-core-r3/offline-{normal,cancel,expire,late}.*`.
All four CLI scenarios naturally exited zero, each verifying nine package
origins; all four stderr files were empty. Each contains two accepted arm rows.

| Local synthetic scenario | A | B |
| --- | --- | --- |
| Normal | 6 exact / 6 confirmed / 6 dispatched | 6 exact / 6 confirmed / 6 dispatched |
| Cancel after two presses | 2 readback / 0 confirmed / 2 dispatched | 2 readback / 1 confirmed / 2 dispatched |
| Expire after two presses | Same counts as cancel, `task_timed_out` | Same counts as cancel, `task_timed_out` |
| Cancel before late ASR response | 0 output, ASR1 / polishing0 | 0 output, ASR1 / polishing0 |

All normal/cancel/expire rows used ASR1/polishing1. Normal A's dispatch,
first-buffer observation and output-completed durations were respectively
294.880 / 309.092 / 639.916 ms; B's were 34.901 / 41.080 / 400.982 ms.
These are single local-fixture observations, not cloud performance gains.
Both normal rows had no Session diagnostics. Cancellation and expiry retained
the expected partial uncertainty, stopped without tail/replay and restored the
synthetic keyboard; the late fixture actually attempted its delayed response.
The differing confirmed counts reflect A's interrupted whole insert versus
B's already completed first fragment; no uncertain text is counted as confirmed.

## Remaining acceptance

Ubuntu 24.04 GNOME46/Xorg controls need a small separately reviewed adapter that
injects verified native controller and GTK-child paths into the existing parent
helper. The default Noble live route deliberately rejects unprepared controls;
it does not fall back to the host. No guest network change or secret bridge is
implemented or authorized here. A later local-TLS owned-GTK run must use the
real ManagedQt loop and have its complete argv/plan reviewed before the sole
desktop agent executes it.

After implementation/review of that route, any actual public-audio cloud run
still requires explicit human authorization for the WAV, destinations and stored
credentials. A prepared source branch is not that authorization. Neither these
headless checks nor the earlier local GTK comparison establishes real-speech
accuracy or a cloud stop-to-first/total-output improvement on Ubuntu 24.04.
