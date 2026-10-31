"""Synthetic pacing checks; they do not establish client delivery."""

import asyncio
import time

import pytest
from test_fcitx5 import FakeBus, FakeCapability, reply
from test_neighbor_protocol import Bus

from inkecho.platform import fcitx5
from inkecho.platform.fcitx5 import Fcitx5Bridge, FcitxOutputError
from inkecho.streaming_output import StreamingOutput, TextDelta


class TimedBus(FakeBus):
    def __init__(self, outcomes):
        super().__init__(outcomes)
        self.commits = []
        self.first = asyncio.Event()

    async def call(self, message):
        if message.member == "Commit":
            self.commits.append((message.body[2], time.monotonic()))
            self.first.set()
        return await super().call(message)


def test_pacing_spans_stream_fragments_without_delay_after_last(monkeypatch):
    monkeypatch.setattr(fcitx5, "COMMIT_INTERVAL_SECONDS", 0.04)

    async def run():
        bus = TimedBus([reply([1]), reply([1])])
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await bridge.connect()
        assert await bridge.insert("甲", lambda: True) == 1
        assert await bridge.insert("乙", lambda: True) == 1
        assert [value for value, _ in bus.commits] == ["甲", "乙"]
        assert bus.commits[1][1] - bus.commits[0][1] >= 0.04
        await bridge.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("reason", ["cancel", "expired"])
def test_wait_never_sends_after_cancel_or_deadline(monkeypatch, reason):
    monkeypatch.setattr(fcitx5, "COMMIT_INTERVAL_SECONDS", 0.1)

    async def run():
        bus = TimedBus([reply([1]), reply([1])])
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await bridge.connect()
        active = True
        deadline = time.monotonic() + (0.03 if reason == "expired" else 2)
        task = asyncio.create_task(
            bridge.insert("甲乙", lambda: active, deadline=deadline)
        )
        await asyncio.wait_for(bus.first.wait(), 1)
        if reason == "cancel":
            await asyncio.sleep(0.015)
            active = False
        with pytest.raises(FcitxOutputError) as caught:
            await asyncio.wait_for(task, 1)
        assert caught.value.code == ("cancelled" if reason == "cancel" else "expired")
        assert caught.value.accepted == 1
        assert [value for value, _ in bus.commits] == ["甲"]
        await bridge.aclose()

    asyncio.run(run())


def test_unknown_reply_never_replayed_after_pacing():
    async def run():
        bus = TimedBus([reply([1]), reply([2]), reply([1])])
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await bridge.connect()
        with pytest.raises(FcitxOutputError, match="delivery_unknown"):
            await bridge.insert("甲乙丙", lambda: True)
        assert [value for value, _ in bus.commits] == ["甲", "乙"]
        with pytest.raises(FcitxOutputError, match="session_failed"):
            await bridge.insert("丙", lambda: True)
        assert [value for value, _ in bus.commits] == ["甲", "乙"]
        await bridge.aclose()

    asyncio.run(run())


def test_focus_can_change_during_interval(monkeypatch):
    monkeypatch.setattr(fcitx5, "COMMIT_INTERVAL_SECONDS", 0.04)

    class FocusBus(TimedBus):
        def __init__(self):
            super().__init__([reply([1]), reply([1])])
            self.focus = "first"
            self.targets = []

        async def call(self, message):
            if message.member == "Commit":
                self.targets.append((self.focus, message.body[2]))
            return await super().call(message)

    async def run():
        bus = FocusBus()
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await bridge.connect()
        task = asyncio.create_task(bridge.insert("甲乙", lambda: True))
        await asyncio.wait_for(bus.first.wait(), 1)
        bus.focus = "second"
        assert await task == 2
        assert bus.targets == [("first", "甲"), ("second", "乙")]
        await bridge.aclose()

    asyncio.run(run())


class TimedV4Bus(Bus):
    def __init__(self):
        super().__init__()
        self.commits = []
        self.first = asyncio.Event()

    async def call(self, message):
        if message.member == "CommitBatch":
            self.commits.append((message.body[2], time.monotonic()))
            self.first.set()
        return await super().call(message)


def test_v4_first_and_final_commit_do_not_wait_for_next_interval(monkeypatch):
    monkeypatch.setattr(fcitx5, "COMMIT_INTERVAL_SECONDS", 1.0)

    async def run():
        bus = TimedV4Bus()
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await bridge.connect()
        before = time.monotonic()
        assert await asyncio.wait_for(bridge.insert("甲", lambda: True), 0.25) == 1
        returned = time.monotonic()
        assert bus.commits[0][1] - before < 0.25
        assert returned - bus.commits[0][1] < 0.25
        await bridge.aclose()

    asyncio.run(run())


def test_v4_stream_fragment_and_newline_neighbor_spacing(monkeypatch):
    monkeypatch.setattr(fcitx5, "COMMIT_INTERVAL_SECONDS", 0.04)

    async def run():
        bus = TimedV4Bus()
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await bridge.connect()
        stream = StreamingOutput(
            lambda text: bridge.insert(text, lambda: True),
            lambda: True,
            batch_enabled=lambda: bridge.supports_neighbor_batch,
        )
        worker = asyncio.create_task(stream.run())
        await stream.append(TextDelta(0, "甲\n"))
        await asyncio.sleep(0)
        await stream.append(TextDelta(2, "乙丙"))
        await stream.finish("甲\n乙丙")
        assert await asyncio.wait_for(worker, 1) == 4
        assert [text for text, _ in bus.commits] == ["甲\n", "乙", "丙"]
        assert all(
            after[1] - before[1] >= 0.04
            for before, after in zip(bus.commits, bus.commits[1:], strict=False)
        )
        await bridge.aclose()

    asyncio.run(run())


def test_v4_cancel_during_pacing_never_emits_neighbor_unit(monkeypatch):
    monkeypatch.setattr(fcitx5, "COMMIT_INTERVAL_SECONDS", 0.1)

    async def run():
        bus = TimedV4Bus()
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await bridge.connect()
        active = True
        task = asyncio.create_task(bridge.insert("甲\n乙", lambda: active))
        await asyncio.wait_for(bus.first.wait(), 1)
        await asyncio.sleep(0.015)
        active = False
        with pytest.raises(FcitxOutputError, match="cancelled") as caught:
            await asyncio.wait_for(task, 1)
        assert caught.value.accepted == 1
        assert [text for text, _ in bus.commits] == ["甲"]
        await bridge.aclose()

    asyncio.run(run())
