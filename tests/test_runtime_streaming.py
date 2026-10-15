"""Real Qt + HTTPS early-DONE/cancel cleanup, using existing TLS fixtures."""

import asyncio
import gc
import sys

import httpx
import pytest
from test_polish_stream import DONE, STOP, event
from test_polish_stream import certificate as certificate
from test_polish_stream import server as server

from inkecho.providers import ProviderClient
from inkecho.runtime import ManagedQtEventLoop


def test_real_qasync_early_done_and_cancel_close_nested_http_generators(
    server, qt_app, monkeypatch
):
    errors, unraisable = [], []
    monkeypatch.setattr(
        sys,
        "unraisablehook",
        lambda value: unraisable.append(type(value.exc_value).__name__),
    )
    server.replies.extend(
        [
            {"steps": [(0, event("a") + STOP + DONE), (0.25, event("late"))]},
            {"steps": [(0, event("b")), (0.25, event("cancelled-tail") + STOP + DONE)]},
        ]
    )

    async def execute():
        async with httpx.AsyncClient(verify=server.context, trust_env=False) as http:
            async with ProviderClient(http=http, timeout_seconds=1) as client:
                deltas = []

                async def receive(delta):
                    deltas.append(delta)

                result = await client.polish_stream(
                    server.provider, "key", "d", "p", receive
                )
                assert result.text == "a" and deltas == ["a"]
                first = asyncio.Event()

                async def cancel_after_prefix(delta):
                    deltas.append(delta)
                    first.set()
                    await asyncio.Event().wait()

                task = asyncio.create_task(
                    client.polish_stream(
                        server.provider, "key", "d", "p", cancel_after_prefix
                    )
                )
                await first.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert deltas == ["a", "b"]
                gc.collect()
                await asyncio.sleep(0.02)

    previous = sys.get_asyncgen_hooks()
    with ManagedQtEventLoop(qt_app) as loop:
        loop.set_exception_handler(
            lambda _loop, context: errors.append(context.get("message", "unknown"))
        )
        loop.run_until_complete(execute())
    gc.collect()
    assert sys.get_asyncgen_hooks() == previous
    assert errors == [] and unraisable == []
