"""Offline protocol negotiation; this is not target delivery acceptance."""

import asyncio

import pytest
from test_fcitx5 import FakeBus, FakeCapability, reply
from test_output_router import Bridge, Keyboard

from inkecho.platform import fcitx5
from inkecho.platform.fcitx5 import Fcitx5Bridge, FcitxOutputError
from inkecho.platform.output_router import OutputRouter, OutputRouterError


class V2Bus(FakeBus):
    async def call(self, message):
        if message.member == "Begin2":
            self.calls.append(message)
            assert message.signature == "su" and message.body[1] == 2
            return reply([True])
        result = await super().call(message)
        if message.member == "Introspect":
            result.body = [
                result.body[0].replace(
                    "</interface>", '<method name="Begin2"/></interface>'
                )
            ]
        return result


def bridge(bus):
    return Fcitx5Bridge(bus_factory=lambda: bus, capability_factory=FakeCapability)


def test_v2_zero_prefix_ambiguity_is_definitely_unsent(monkeypatch):
    monkeypatch.setattr(fcitx5, "FOCUS_WAIT_SECONDS", 0)

    async def run():
        bus = V2Bus([reply([4])])
        client = bridge(bus)
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: True)
        assert caught.value.code == "ambiguous_target"
        assert caught.value.accepted == 0 and caught.value.unsent_offset == 0
        assert not caught.value.uncertain
        assert [x.member for x in bus.calls].count("Begin2") == 1
        await client.aclose()

    asyncio.run(run())


def test_v1_unnegotiated_4_remains_uncertain_not_safe_fallback():
    async def run():
        bus = FakeBus([reply([4])])
        client = bridge(bus)
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: True)
        assert caught.value.code == "delivery_unknown" and caught.value.uncertain
        assert caught.value.unsent_offset is None
        assert not any(x.member == "Begin2" for x in bus.calls)
        await client.aclose()

    asyncio.run(run())


def test_v2_mid_prefix_ambiguity_resumes_only_same_unsent_sequence():
    async def run():
        bus = V2Bus([reply([1]), reply([4]), reply([1])])
        client = bridge(bus)
        await client.connect()
        assert await client.insert("甲乙", lambda: True) == 2
        assert [x.body[1] for x in bus.calls if x.member == "Commit"] == [0, 1, 1]
        assert client._accepted == 2
        await client.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("body", [[True], ["4"], [5]])
def test_v2_malformed_replies_never_become_unsent(body):
    async def run():
        bus = V2Bus([reply(body)])
        client = bridge(bus)
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: True)
        assert caught.value.code == "delivery_unknown" and caught.value.uncertain
        await client.aclose()

    asyncio.run(run())


def test_auto_v2_ambiguity_fallback_preserves_auto_selection():
    async def run():
        keyboard = Keyboard()

        class Ambiguous(Bridge):
            async def insert(self, text, can_continue, **kwargs):
                raise FcitxOutputError("ambiguous_target", unsent_offset=0)

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=Ambiguous)
        router._system_detector = detect
        await router.prepare_task("auto")
        assert await router.insert("甲乙", lambda: True) == 2
        assert keyboard.sent == ["甲乙"]

    asyncio.run(run())


def test_partial_v2_ambiguity_cannot_fallback_or_replay():
    async def run():
        keyboard = Keyboard()

        class Ambiguous(Bridge):
            async def insert(self, text, can_continue, **kwargs):
                raise FcitxOutputError("ambiguous_target", accepted=1, unsent_offset=1)

        async def detect():
            return ("fcitx", ":1.42")

        router = OutputRouter(keyboard, bridge_factory=Ambiguous)
        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="partial_input_failed"):
            await router.insert("甲乙", lambda: True)
        assert keyboard.sent == []

    asyncio.run(run())


def test_v2_cancel_during_ambiguous_focus_does_not_retry_tail():
    async def run():
        active = True

        class CancelBus(V2Bus):
            async def call(self, message):
                nonlocal active
                result = await super().call(message)
                if message.member == "Commit":
                    active = False
                return result

        bus = CancelBus([reply([4])])
        client = bridge(bus)
        await client.connect()
        with pytest.raises(FcitxOutputError, match="cancelled"):
            await client.insert("甲乙", lambda: active)
        assert [x.member for x in bus.calls].count("Commit") == 1
        assert client._accepted == 0
        await client.aclose()

    asyncio.run(run())
