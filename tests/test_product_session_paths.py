import asyncio
from dataclasses import replace

import pytest
from conftest import qt_app as qt_app
from test_application_streaming import Client
from test_application_streaming import sessions as sessions
from test_fcitx5 import FakeCapability
from test_neighbor_protocol import Bus
from test_output_router import Keyboard

from inkecho.core import State
from inkecho.platform.fcitx5 import Fcitx5Bridge
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
def test_actual_session_routes_all_output_paths_with_batch_protocol(sessions, mode):
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
            return "absent"

        async def detector():
            return ("fcitx", ":1.42")

        bus = Bus()
        bridges = []

        def factory():
            b = Fcitx5Bridge(bus_factory=lambda: bus, capability_factory=FakeCapability)
            bridges.append(b)
            return b

        r = DefaultAutoOutputRouter(
            Keyboard(),
            bridge_factory=factory,
            state_probe=state,
            system_detector=detector,
        )
        s = sessions(Producer())
        s.inputs = r
        s.store.save_settings(
            replace(
                s.settings,
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
            units = [m.body[2] for m in bus.calls if m.member == "CommitBatch"]
            if mode == "buffered-cancel":
                assert units == [] and s.controller.outcome == State.CANCELLED
                assert out[-1]["characters"] == 0 and len(bridges) <= 1
            elif mode == "partial-provider-failure":
                assert units == ["甲"] and s.controller.outcome == State.FAILED
                assert out[-1]["characters"] == 1 and len(bridges) == 1
            else:
                assert "".join(units) == sample, (mode, s.controller.outcome, units)
                assert all(u != "\n" and len(u) <= 3 for u in units)
                assert s.controller.outcome == State.SUCCEEDED
                assert out[-1]["characters"] == len(sample)
                if mode == "buffered-fallback":
                    assert len(bridges) == 2
                    assert bridges[0]._accepted == 0
        finally:
            await s.close()

    asyncio.run(run())
