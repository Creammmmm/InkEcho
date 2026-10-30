import asyncio
from dataclasses import replace

import pytest
from conftest import qt_app as qt_app
from test_application_streaming import Client
from test_application_streaming import sessions as sessions
from test_output_router import Keyboard
from test_owned_bounded_protocol import Bus, Cap, async_true, xml

from inkecho.core import State
from inkecho.platform.ibus_owned import Client as OwnedClient
from inkecho.platform.ibus_owned import IBusBridge
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.providers import ProviderError, Result, Usage


@pytest.mark.parametrize(
    "mode",
    [
        "synchronous",
        "original-fallback",
        "stream",
        "buffered-fallback",
        "buffered-cancel",
        "partial-provider-failure",
    ],
)
def test_explicit_bounded_session_preserves_all_output_paths(sessions, mode):
    async def run():
        sample = "甲乙\n\n\n丙\n"

        class Producer(Client):
            async def transcribe(self, *a):
                return Result(sample, Usage(), 0)

            async def polish(self, *a):
                return Result(sample, Usage(), 0)

            async def polish_stream(self, *a):
                if mode == "original-fallback":
                    raise ProviderError("network")
                if mode in {
                    "buffered-fallback",
                    "buffered-cancel",
                    "partial-provider-failure",
                }:
                    await a[-1]("甲乙" if mode == "partial-provider-failure" else "甲")
                    await asyncio.sleep(0.01)
                    if mode == "buffered-cancel":
                        s.cancel()
                    raise ProviderError("network")
                for c in sample:
                    await a[-1](c)
                    await asyncio.sleep(0)
                return Result(sample, Usage(), 0)

        async def state():
            return "enabled"

        async def detector():
            return None

        async def owned_probe():
            return ("ibus", ":1.23")

        bus = Bus(xml())
        bridges = []

        def factory():
            b = IBusBridge(
                runtime_dir="/unused-private-fixture",
                capability_factory=lambda _: Cap(),
                client_factory=lambda cap, **options: OwnedClient(
                    cap,
                    bus_factory=lambda: bus,
                    owner_verifier=lambda _: async_true(),
                    **options,
                ),
            )
            bridges.append(b)
            return b

        r = DefaultAutoOutputRouter(
            Keyboard(),
            owned_factory=factory,
            owned_probe=lambda: owned_probe(),
            state_probe=state,
            system_detector=detector,
        )
        s = sessions(Producer())
        s.inputs = r
        s.store.save_settings(
            replace(
                s.settings,
                output_method="ibus-owned",
                polishing_streaming=mode != "synchronous",
                polishing_fallback=True,
            )
        )
        out = []
        s.finished.connect(out.append)
        try:
            await s.toggle()
            s.stop_recording()

            async def done():
                while s.pending:
                    await asyncio.sleep(0.001)

            await asyncio.wait_for(done(), 3)
            units = [
                body[1] for member, _, body in bus.calls if member == "CommitBounded"
            ]
            if mode == "buffered-cancel":
                assert units == [] and s.controller.outcome == State.CANCELLED
                assert out[-1]["characters"] == 0 and len(bridges) <= 1
            elif mode == "partial-provider-failure":
                assert units == ["甲"] and s.controller.outcome == State.FAILED
                assert out[-1]["characters"] == 1 and len(bridges) == 1
            else:
                assert "".join(units) == sample, (mode, s.controller.outcome, units)
                assert all(u != "\n" and len(u) <= 3 for u in units)
                # Producer completion is deliberately not a target receipt.
                assert s.controller.outcome == State.UNCONFIRMED
                assert out[-1]["characters"] == len(sample)
                if mode == "buffered-fallback":
                    assert len(bridges) == 2
                    assert bridges[0]._client is None
        finally:
            await s.close()

    asyncio.run(run())
