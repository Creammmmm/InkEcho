# Configuration comparison preparation — 2026-10-16

This is local preparation for the remaining real-speech end-to-end comparison.
**No cloud execution path exists in this tool yet.** It does not access keyring,
user configuration, microphone, desktop focus, clipboard or input methods.
The earlier rejected public-WAV request has not been retried.

## Proposed comparison and fixed plan

`scripts/validation/performance_cloud_comparison.py` defaults to a read-only
standard-library plan. The configurations use the same a13 product, public WAV,
public prompt, 128-token polishing limit and production keyboard pacing:

| Configuration | Transcription | Polishing |
| --- | --- | --- |
| A | HTTP `qwen3-asr-flash`, after recording stops | `deepseek-flash`, buffered response |
| B | WSS `qwen3-asr-flash-realtime`, paced PCM during recording | `deepseek-flash`, SSE |

These are **configuration A/B**, not old/new product versions or an assertion
that the user's existing streaming setting was false. A future measured
difference would combine changes in ASR model/protocol and polishing delivery;
it cannot establish the contribution of either change independently.

The intended live budget is one ASR and one polishing call per configuration,
four calls total; no discovery, warm-up, automatic retry or transcript cache.
The plan prints the exact two ASR destinations and
`https://api.deepseek.com/chat/completions`, model identifiers and fixed public
prompt. The HTTP origin is the previously audited Beijing workspace origin;
this preparation does not establish that it accepts either authenticated model.
Production profile validation, without network access, checks the derived WSS
URL and the verified DeepSeek origin's default `thinking: {type: disabled}` for
both request modes. The loopback network fixture itself uses local origins and
does not claim to validate vendor-origin handling over the network.

The existing file `/tmp/inkecho-public-asr-fixture.wav` is verified by SHA-256
`0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf`:
571456 bytes, mono PCM16, 16000 Hz, 282322 frames, 17.645125 seconds. The file
was only read locally for hash/header/completeness checks, never played or sent.
Its previously recorded public source is
<https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/sensevoice/rich_text_example_1.wav>;
this task made no new download.

The selected artifact is a13, product
`eeb2d0ce8f8c5a6690b0ab54e0196da4254eb767`, 108907000 bytes, SHA-256
`8dce4eedee71373a27e0e6507592b1240617412a8a6f114230b9a53f4d286a89`.
The extracted inventory SHA-256 is
`38aa4ea34ac4f136c11a8fb15720c5e952bd8e577ff311b3952197095a6262cb`.
Plan generation verifies that pinned inventory, all 3958 listed files and 1048
symlinks; it rejects changed/escaped package contents. Both new executable
modules' hashes are included in the canonical plan fingerprint. Offline
execution requires that exact fingerprint and repeats preflight in the worker.
No production files or user JSON are changed.

## Reproduce the local validation

From the repository, using the existing extracted a13 package:

```sh
.venv/bin/python scripts/validation/performance_cloud_comparison.py \
  --package-root build/performance-a13-extracted-iwmzy2mn/squashfs-root/packages \
  > build/performance-cloud-comparison-plan.json
```

Review `plan_sha256` and the complete plan. Then pass its literal fingerprint:

```sh
.venv/bin/python scripts/validation/performance_cloud_comparison.py \
  --package-root build/performance-a13-extracted-iwmzy2mn/squashfs-root/packages \
  --offline --scenario all \
  --accept-plan-sha 4aab800d5768f23f0982ef6c606dffec5575ded608320ad5b6504218f0782f3d \
  > build/performance-cloud-comparison-offline.json
.venv/bin/python -m pytest -q tests/test_performance_cloud_comparison.py --tb=short
```

The literal above binds the measured source snapshot; changing either module
requires generating and reviewing a new fingerprint. `--live` is rejected by
argument parsing before reading files. There is no credential-reading branch.

The worker uses shipped Python, AppRun-equivalent `PYTHONHOME`, Qt plugin and
library paths, and verifies seven actual module origins/hashes: Session,
TaskTiming, HTTP providers, realtime, SSE parsing, streaming output and keyboard.
HOME, all XDG directories and TMPDIR are private temporary directories;
user-site imports and bytecode writes are disabled. Qt uses `offscreen` and no
display/session-bus variables are inherited. The bundled interpreter's existing
runtime is exercised, not a new package build.
The harness uses `asyncio.run` with offscreen Qt, not ManagedQtEventLoop in an
actual desktop session. It does not establish real Qt/desktop event-loop,
shortcut, microphone or window lifecycle behavior.

The independent `performance_comparison_fixture.py` binds HTTPS and WSS only to
`127.0.0.1`, using a generated trusted test certificate. Each arm uses a real
production Session, production HTTP/WSS/SSE parsing and production KeyboardInput.
The recorder and low-level display driver are synthetic: both arms receive the
same generated 200 ms PCM timeline, not the public speech WAV. Audio/results are
not reused between requests. The fixture enforces one ASR/one polishing request
per arm and checks that each actual ASR result reaches its polishing request.
All five scenarios therefore make 18 local fixture calls, not four cloud calls.

There is no focus read during recording/feed. The simulated cursor is selected
after recording and can switch after two emitted characters. KeyboardInput keeps
its real mapping waits, release handling and R8 output-session lifecycle. The
first-character milestone is accepted only when it agrees with the simulated
driver's successful press time within 5 ms; it is not an insert-call timestamp
or a claim about a rendered glyph.

## Observed results and scope

The corrected source checks passed **23 tests in 8.69 seconds**; Ruff lint and
format checks passed for the three new Python files. The original sandbox run
could not bind loopback sockets; the permitted loopback-only rerun passed.
Source tests report `source_protocol_synthetic_display`. An unaudited runner
cannot obtain the package label by default.

The separate actual-a13 worker naturally exited **0**, reporting
`package_protocol_synthetic_display`, seven verified package origins and all ten
arm/scenario combinations accepted:

| Local scenario | A | B |
| --- | --- | --- |
| Normal | 6 exact characters; succeeded | 6 exact characters; succeeded |
| Cursor switch | exact `[2, 4]` split | exact `[2, 4]` split |
| Cancel after two presses | 2, matched release, no tail | 2, matched release, no tail |
| Expire after two presses | 2, failed, no tail | 2, failed, no tail |
| Delayed ASR after cancel | 0, late response attempted | 0, late response attempted |

Each scenario also rejects stale post-terminal callbacks, observes 300 ms with
no additional text, verifies mapping/driver cleanup, and prevents whole
final-text replay. This new WSS fixture does not send preview events; preview
is covered separately in the earlier a13 package evidence. Repeated Unicode
and CRLF across SSE boundaries survive
the actual normalization path. The CLI itself enforces the normal A/B ordering
and late-response attempt checks; these are not merely pytest assertions.

The one synthetic normal pair measured stop-to-first 297.371/29.404 ms and
stop-to-output-completed 651.798/402.442 ms (A/B). Its fixed server delays and
generated results explain those numbers. **They are not cloud speed evidence,
a desktop rendering measurement, real speech recognition or a distribution.**
Cancelled/expired samples retain missing completion timings as null.

Reports persist only fixed metadata, counts, equality flags, hashes and timings.
The fixture's text, audio, response bodies and fake credential remain in RAM;
only its temporary self-signed TLS certificate/key are created and removed.
The fixed public prompt is intentionally present in the plan; no private prompt
is loaded. Logs are local `build/performance-cloud-comparison-{plan,offline}.json`
and `build/performance-cloud-comparison-tests.log`.

## Still required before the original goal is complete

The next implementation slice is a new owned GTK target with anonymous-socket
readback and in-memory text comparison. The older OwnedTarget writes full text
to JSON and must not be used for live data. A delivery-time fixture guard must
protect only owned windows, without product focus capture during recording/ASR.
Target closure must follow the producer's actual terminal state and cleanup;
an observation timeout must preserve the same PID/start handle, not kill or
restart its producer.

The live branch can be implemented and reviewed locally after that slice and
offline regression, without cloud calls. Actual cloud execution separately
requires explicit human authorization and review of the complete execution
arguments. The branch must validate
snapshot/package/WAV/endpoints/models/budget before touching credentials, enforce
the four-call budget at outgoing request boundaries, pace the full identical
public-WAV timeline for each arm, and execute both genuine Session pipelines.
No live speech, live stop-to-first comparison, owned GTK memory readback or
real desktop support is established by this preparation. Existing real-desktop
reports remain separate evidence; this report does not replace them.
