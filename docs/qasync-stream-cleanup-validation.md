# Qt streaming cleanup regression

Date: 2026-10-15. Environment: CPython 3.13.15, qasync 0.28.0, HTTPX 0.28.x,
actual Qt event loop with an offscreen windowing backend and temporary loopback
TLS/WSS services. No cloud, user credentials, real microphone or desktop input
was used in this regression.

## Failure and cause

The first full synthetic source workflow returned functionally correct text but
printed `HTTP11ConnectionByteStream.__aiter__: async generator ignored
GeneratorExit` and asynchronous `aclose` cleanup after its event loop had stopped.
The original failing log is retained at
`build/performance-package-source-synthetic.log`. A correct JSON result alone
was not accepted while these cleanup failures remained.

Inspection of the installed qasync `run_forever` showed that it overrides the
CPython event-loop implementation without installing asynchronous-generator
first-iteration/finalizer hooks. Its inherited `shutdown_asyncgens` therefore
does not own all generators. HTTPX's nested generators can be synchronously
finalized even though HTTPcore's exception cleanup needs to await resource
release. Calling `shutdown_asyncgens` without first registering generators did
not fix the real Qt failure. Plain `asyncio.run` tests had hidden the difference.

## Fix

`ManagedQtEventLoop` in `inkecho.runtime` installs this loop's standard CPython
async-generator hooks while `run_forever` runs and restores the previous
thread-local hooks in `finally`. Context exit shuts down registered async
generators before closing Qt's loop, including application exceptions. The two
CPython private hook methods are confined to this small compatibility adapter;
HTTP requests do not change global hooks independently. The normal application
entry point and package workflow probe use the same adapter.

The SSE reader also explicitly closes its outer byte iterator using
`contextlib.aclosing`. DONE still terminates the protocol immediately, without
waiting for an HTTP peer's EOF. Cancellation, partial-output refusal and the
no-replay policy remain unchanged. No warning filter or ignored-exception
workaround was introduced.

Reference: Python's documented
[async-generator hooks](https://docs.python.org/3.13/library/sys.html#sys.set_asyncgen_hooks).
The implementation was checked against the actual installed qasync 0.28.0 and
CPython 3.13 `asyncio/base_events.py`, rather than assuming that Qt uses
`asyncio.run` lifecycle behavior.

## Reproduce and observed results

```bash
.venv/bin/ruff check src/inkecho/runtime.py src/inkecho/__main__.py \
  src/inkecho/polish_stream.py tests/test_runtime.py tests/test_runtime_streaming.py
.venv/bin/ruff format --check src/inkecho/runtime.py src/inkecho/__main__.py \
  src/inkecho/polish_stream.py tests/test_runtime.py tests/test_runtime_streaming.py
.venv/bin/python -m pytest tests/test_runtime.py tests/test_runtime_streaming.py \
  tests/test_polish_stream.py \
  -q --tb=short
QT_QPA_PLATFORM=offscreen .venv/bin/python \
  scripts/validation/performance_package_probe.py --package-root src \
  --output build/performance-package-source-cleanup-fixed.json
```

The local tests require loopback listener and asyncio/thread wakeup capability.
Observed: **53 passed in 2.73 s**, with Ruff lint and formatting passing.
Checks include actual Qt + HTTPS early-DONE and callback cancellation, async
cleanup completion on normal/exception exit, restoring preexisting hooks,
nested Qt contexts, another thread's independent hooks, and unchanged standard
`asyncio.run` behavior. The Qt HTTP test records unraisable and event-loop errors
and requires both lists to remain empty; it does not suppress them.

The complete source workflow also passed using synthetic audio/current-cursor
input with actual local TLS/WSS and Qt scheduling. Its new output is
`build/performance-package-source-cleanup-fixed.json`; its accompanying `.log`
contains a normal metadata report and no GeneratorExit, unawaited cleanup or
no-running-loop failure. The workflow verified incremental audio before stop,
early streamed output, exact final input, partial-output cancellation without a
tail, and shared HTTP reuse. These are controlled source/runtime facts, not
real-cloud or real-desktop acceptance and not a speed claim for Ubuntu 24.04.

Packaged-runtime and actual microphone/desktop runs remain separate acceptance
work. Future Python/qasync upgrades should rerun this regression because the
adapter intentionally delegates to the loop's CPython generator hooks.
