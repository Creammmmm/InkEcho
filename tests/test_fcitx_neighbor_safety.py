"""Synthetic protocol4 task boundaries; no desktop or provider calls."""

import asyncio
import time

import pytest
from conftest import qt_app as qt_app
from test_application_streaming import Client
from test_application_streaming import sessions as sessions
from test_fcitx5 import FakeCapability, reply
from test_neighbor_protocol import Bus
from test_output_router import Keyboard

from inkecho.core import State
from inkecho.platform.fcitx5 import Fcitx5Bridge, FcitxOutputError
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.providers import Result, Usage


@pytest.mark.parametrize("action", ["cancel", "expire", "replace"])
def test_retained_first_scalar_late_provider_never_crosses_task(sessions, action):
    async def run():
        entered = asyncio.Event()
        release = asyncio.Event()
        ready = asyncio.Event()
        late = asyncio.Event()
        cancellation_seen = asyncio.Event()
        producer_tasks = []
        buses = []
        bridges = []

        class Producer(Client):
            async def polish_stream(self, *a):
                producer_tasks.append(asyncio.current_task())
                await a[-1]("甲")
                entered.set()
                # A provider may ignore repeated cancellation, including one
                # caused by replacement preparation after explicit cancellation.
                while not release.is_set():
                    try:
                        await release.wait()
                    except asyncio.CancelledError:
                        cancellation_seen.set()
                        continue
                late.set()
                await a[-1]("迟到")
                return Result("甲迟到", Usage(), 0)

        async def state():
            return "absent"

        async def detect():
            return ("fcitx", ":1.42")

        def factory():
            bus = Bus()
            buses.append(bus)
            client = Fcitx5Bridge(
                bus_factory=lambda: bus, capability_factory=FakeCapability
            )
            bridges.append(client)
            return client

        router = DefaultAutoOutputRouter(
            Keyboard(),
            bridge_factory=factory,
            state_probe=state,
            system_detector=detect,
        )
        prepare = router.prepare_stream

        async def prepared(*args, **kwargs):
            enabled = await prepare(*args, **kwargs)
            assert enabled is True
            ready.set()
            return enabled

        router.prepare_stream = prepared
        session = sessions(Producer())
        session.inputs = router
        out = []
        session.finished.connect(out.append)
        try:
            await session.toggle()
            session.stop_recording()
            await asyncio.wait_for(entered.wait(), 1)
            await asyncio.wait_for(ready.wait(), 1)
            assert not [m for b in buses for m in b.calls if m.member == "CommitBatch"]
            if action == "expire":
                session.controller.task.deadline = time.monotonic() - 1
                session.controller.tick()
            else:
                session.cancel()
            if action == "replace":
                await asyncio.wait_for(cancellation_seen.wait(), 1)
                # Make the replacement cancellation wave deterministic instead
                # of depending on cleanup task scheduling under the full suite.
                producer_tasks[0].cancel()
                await asyncio.sleep(0)
                session.last_toggle = 0
                await session.toggle()
                newid = session.controller.task.id
            release.set()
            await asyncio.wait_for(late.wait(), 1)
            for _ in range(100):
                if bridges[0]._closed and buses[0].disconnected:
                    break
                await asyncio.sleep(0)
            assert not [m for b in buses for m in b.calls if m.member == "CommitBatch"]
            assert (
                out[0]["characters"] == 0
                and bridges[0]._closed
                and buses[0].disconnected
            )
            if action == "replace":
                assert (
                    session.controller.task.id == newid
                    and session.controller.state == State.RECORDING
                )
        finally:
            release.set()
            await session.close()

    asyncio.run(run())


@pytest.mark.parametrize("replykind", ["accepted", "unknown"])
def test_cancel_inflight_batch_never_starts_second_request(replykind):
    async def run():
        bus = Bus()
        entered = asyncio.Event()
        release = asyncio.Event()
        original = bus.call
        active = True

        async def call(m):
            if m.member == "CommitBatch":
                bus.calls.append(m)
                entered.set()
                await release.wait()
                r = reply([1 if replykind == "accepted" else 2])
                r.signature = "u"
                return r
            return await original(m)

        bus.call = call
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        task = asyncio.create_task(client.insert("\n甲乙", lambda: active))
        await asyncio.wait_for(entered.wait(), 1)
        active = False
        release.set()
        with pytest.raises(FcitxOutputError) as caught:
            await task
        assert caught.value.accepted == (2 if replykind == "accepted" else 0)
        assert caught.value.code == (
            "cancelled" if replykind == "accepted" else "delivery_unknown"
        )
        assert (
            not caught.value.safe_to_fallback
            and len([m for m in bus.calls if m.member == "CommitBatch"]) == 1
        )
        await client.aclose()
        assert bus.disconnected

    asyncio.run(run())
