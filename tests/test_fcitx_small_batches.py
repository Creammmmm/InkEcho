"""V4 batching preserves ordered neighbor units and conservative delivery."""

import asyncio
import time

import pytest
from test_fcitx5 import FakeCapability, reply
from test_neighbor_protocol import Bus

from inkecho.platform import fcitx5
from inkecho.platform.fcitx5 import Fcitx5Bridge, FcitxOutputError
from inkecho.streaming_output import StreamingOutput, TextDelta


def commits(bus):
    return [m.body[2] for m in bus.calls if m.member == "CommitBatch"]


@pytest.mark.parametrize(
    "text",
    ["甲乙丙丁戊己庚", "甲\n乙丙丁\n戊", "Ae\u0301👩\u200d💻🇨🇳😀末", "甲\n\n乙\n丙"],
)
def test_v4_batches_preserve_unicode_and_newline_units(monkeypatch, text):
    monkeypatch.setattr(fcitx5, "COMMIT_INTERVAL_SECONDS", 0)

    async def run():
        bus = Bus()
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await bridge.connect()
        assert await bridge.insert(text, lambda: True) == len(text)
        parts = commits(bus)
        assert "".join(parts) == text
        assert all(
            0 < len(x) <= 4 and len(x.encode()) <= 32 and x != "\n" for x in parts
        )
        assert len(parts[0]) <= 2
        await bridge.aclose()

    asyncio.run(run())


def test_stream_emits_first_ready_unit_without_waiting_for_batch(monkeypatch):
    monkeypatch.setattr(fcitx5, "COMMIT_INTERVAL_SECONDS", 0.04)

    async def run():
        bus = Bus()
        first = asyncio.Event()
        original = bus.call

        async def call(message):
            result = await original(message)
            if message.member == "CommitBatch":
                first.set()
            return result

        bus.call = call
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
        await stream.append(TextDelta(0, "甲乙"))
        await asyncio.wait_for(first.wait(), 0.5)
        assert commits(bus) == ["甲"]
        for index, char in enumerate("丙丁戊己庚辛", start=2):
            await stream.append(TextDelta(index, char))
        await stream.finish("甲乙丙丁戊己庚辛")
        assert await asyncio.wait_for(worker, 2) == 8
        parts = commits(bus)
        assert "".join(parts) == "甲乙丙丁戊己庚辛"
        assert any(len(x) > 1 for x in parts[1:])
        await bridge.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["unknown", "timeout"])
def test_uncertain_batch_never_replayed(monkeypatch, kind):
    monkeypatch.setattr(fcitx5, "COMMIT_INTERVAL_SECONDS", 0)

    async def run():
        bus = Bus()
        original = bus.call
        calls = 0

        async def call(message):
            nonlocal calls
            if message.member == "CommitBatch":
                calls += 1
                if calls == 2:
                    bus.calls.append(message)
                    if kind == "timeout":
                        await asyncio.sleep(0.2)
                    result = reply([2])
                    result.signature = "u"
                    return result
            return await original(message)

        bus.call = call
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability, timeout=0.05
        )
        await bridge.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await bridge.insert(
                "甲乙丙丁戊己", lambda: True, deadline=time.monotonic() + 1
            )
        assert caught.value.code == "delivery_unknown" and caught.value.uncertain
        assert caught.value.accepted == 1 and commits(bus) == ["甲", "乙丙丁戊"]
        with pytest.raises(FcitxOutputError, match="session_failed"):
            await bridge.insert("己", lambda: True)
        assert len(commits(bus)) == 2
        await bridge.aclose()

    asyncio.run(run())
