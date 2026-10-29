"""Protocol/preedit safety tests; no actual desktop acceptance is implied."""

import asyncio

import pytest
from test_fcitx5 import FakeBus, FakeCapability, reply
from test_output_router import Keyboard

from inkecho.platform.fcitx5 import Fcitx5Bridge, FcitxOutputError
from inkecho.platform.output_router import OutputRouter, OutputRouterError


class V3Bus(FakeBus):
    async def call(self, message):
        if message.member == "Begin3":
            self.calls.append(message)
            assert message.signature == "su" and message.body[1] == 3
            return reply([True])
        result = await super().call(message)
        if message.member == "Introspect":
            result.body = [
                result.body[0].replace(
                    "</interface>", '<method name="Begin3"/></interface>'
                )
            ]
        return result


def client_for(bus):
    return Fcitx5Bridge(bus_factory=lambda: bus, capability_factory=FakeCapability)


@pytest.mark.parametrize("prefix", [0, 1])
def test_composition_blocks_tail_without_retry_or_reuse(prefix):
    async def run():
        bus = V3Bus([reply([1])] * prefix + [reply([5])])
        client = client_for(bus)
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲乙丙", lambda: True)
        error = caught.value
        assert error.code == "composition_active"
        assert error.accepted == prefix and error.unsent_offset == prefix
        assert not error.uncertain and not error.safe_to_fallback
        assert len([x for x in bus.calls if x.member == "Commit"]) == prefix + 1
        with pytest.raises(FcitxOutputError, match="session_failed"):
            await client.insert("丁", lambda: True)
        await client.aclose()
        assert bus.disconnected
        assert len([x for x in bus.calls if x.member == "Cancel"]) == 1
        assert len([x for x in bus.calls if x.member == "Begin3"]) == 1

    asyncio.run(run())


@pytest.mark.parametrize("prefix", [0, 1])
@pytest.mark.parametrize("allow_keyboard", [False, True])
def test_auto_never_hands_off_or_replays_composition(prefix, allow_keyboard):
    async def run():
        keyboard = Keyboard()
        handoffs = []
        bus = V3Bus([reply([1])] * prefix + [reply([5])])
        client = client_for(bus)
        await client.connect()
        router = OutputRouter(keyboard, bridge_factory=lambda: client)
        router._selected, router._kind = client, "fcitx"
        router._auto_task = True
        router._fcitx_keyboard_fallback_allowed = allow_keyboard

        async def handoff(*args):
            handoffs.append(args)
            raise AssertionError("composition cannot hand off")

        router._handoff_unsent_fcitx = handoff
        with pytest.raises(OutputRouterError) as caught:
            await router.insert("甲乙丙", lambda: True)
        assert caught.value.code == (
            "partial_input_failed" if prefix else "fcitx_composition_active"
        )
        assert caught.value.acknowledged_attempts == prefix
        assert keyboard.sent == [] and handoffs == []
        await router.aclose()

    asyncio.run(run())


def test_v3_still_uses_current_focus_gap_retry():
    async def run():
        bus = V3Bus([reply([3]), reply([1]), reply([4]), reply([1])])
        client = client_for(bus)
        await client.connect()
        assert await client.insert("甲乙", lambda: True) == 2
        assert [m.body[1] for m in bus.calls if m.member == "Commit"] == [0, 0, 1, 1]
        await client.aclose()

    asyncio.run(run())


def test_cancel_at_composition_reply_stops_without_retry():
    async def run():
        active = True

        class StopBus(V3Bus):
            async def call(self, message):
                nonlocal active
                result = await super().call(message)
                if message.member == "Commit":
                    active = False
                return result

        bus = StopBus([reply([5])])
        client = client_for(bus)
        await client.connect()
        with pytest.raises(FcitxOutputError, match="cancelled"):
            await client.insert("甲乙", lambda: active)
        assert len([m for m in bus.calls if m.member == "Commit"]) == 1
        await client.aclose()

    asyncio.run(run())


def test_expiry_at_composition_reply_stops_without_retry(monkeypatch):
    from types import SimpleNamespace

    from inkecho.platform import fcitx5

    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(fcitx5, "time", SimpleNamespace(monotonic=lambda: clock.now))

    async def run():
        class StopBus(V3Bus):
            async def call(self, message):
                result = await super().call(message)
                if message.member == "Commit":
                    clock.now = 2000.0
                return result

        bus = StopBus([reply([5])])
        client = client_for(bus)
        await client.connect()
        with pytest.raises(FcitxOutputError, match="expired"):
            await client.insert("甲乙", lambda: True, deadline=1010.0)
        assert len([m for m in bus.calls if m.member == "Commit"]) == 1
        await client.aclose()

    asyncio.run(run())


def test_native_composition_guard_is_read_only(tmp_path):
    import shutil
    import subprocess
    from pathlib import Path

    compiler = shutil.which("c++")
    if compiler is None:
        pytest.skip("C++ compiler unavailable")
    source = Path(__file__).parent / "native/test_fcitx5_composition.cpp"
    binary = tmp_path / "composition-guard"
    subprocess.run(
        [
            compiler,
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(source),
            "-o",
            str(binary),
        ],
        check=True,
    )
    subprocess.run([str(binary)], check=True)


class LegacyBus(FakeBus):
    def __init__(self, version):
        super().__init__()
        self.version = version

    async def call(self, message):
        result = await super().call(message)
        if message.member == "Introspect":
            xml = result.body[0].replace('<method name="Begin3"/>', "")
            if self.version == 2:
                xml = xml.replace("</interface>", '<method name="Begin2"/></interface>')
            result.body = [xml]
        return result


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_addon_rejected_before_capability_or_begin(version):
    async def run():
        bus = LegacyBus(version)
        created = []

        def capability(_runtime):
            created.append(True)
            raise AssertionError("legacy addon must not consume a capability")

        client = Fcitx5Bridge(bus_factory=lambda: bus, capability_factory=capability)
        with pytest.raises(FcitxOutputError) as caught:
            await client.connect()
        assert caught.value.code == "composition_guard_unavailable"
        assert not caught.value.safe_to_fallback and not caught.value.uncertain
        assert created == [] and bus.disconnected
        assert not any(
            m.member in {"Begin", "Begin2", "Begin3", "Commit"} for m in bus.calls
        )
        await client.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("state", ["absent", "disabled", "enabled", "unknown"])
def test_default_auto_legacy_never_uses_keyboard_or_owned(version, state):
    from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter

    async def run():
        bus = LegacyBus(version)
        keyboard = Keyboard()
        owned = []

        async def detect():
            return "fcitx", ":1.42"

        async def probe():
            return state

        def owned_factory():
            owned.append(True)
            raise AssertionError("legacy guard cannot authorize handoff")

        router = DefaultAutoOutputRouter(
            keyboard,
            state_probe=probe,
            system_detector=detect,
            bridge_factory=lambda: client_for(bus),
            owned_factory=owned_factory,
        )
        await router.prepare_task("auto")
        with pytest.raises(
            OutputRouterError, match="fcitx_composition_guard_unavailable"
        ):
            async with router.output_session():
                await router.insert("甲乙", lambda: True)
        assert keyboard.connects == 0 and keyboard.sent == [] and owned == []
        assert bus.disconnected
        assert not any(
            m.member in {"Begin", "Begin2", "Begin3", "Commit"} for m in bus.calls
        )
        await router.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("version", [1, 2])
def test_explicit_legacy_keeps_actionable_guard_diagnostic(version):
    async def run():
        bus = LegacyBus(version)
        keyboard = Keyboard()
        router = OutputRouter(keyboard, bridge_factory=lambda: client_for(bus))

        async def detect():
            return ":1.42"

        router._explicit_fcitx_detector = detect
        with pytest.raises(
            OutputRouterError, match="fcitx_composition_guard_unavailable"
        ):
            await router.prepare_task("fcitx")
        assert keyboard.sent == [] and keyboard.connects == 0 and bus.disconnected
        await router.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("failure", [False, "transport", "unknown-method"])
def test_advertised_guard_failure_does_not_downgrade_or_fallback(failure):
    async def run():
        class BrokenBus(FakeBus):
            async def call(self, message):
                if message.member == "Begin3":
                    self.calls.append(message)
                    if failure == "transport":
                        raise TimeoutError("private raw transport description")
                    if failure == "unknown-method":
                        from dbus_next import MessageType

                        return reply([], kind=MessageType.ERROR)
                    return reply([False])
                return await super().call(message)

        bus = BrokenBus()
        keyboard = Keyboard()
        router = OutputRouter(keyboard, bridge_factory=lambda: client_for(bus))

        async def detect():
            return "fcitx", ":1.42"

        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="fcitx_authorization_failed"):
            async with router.output_session():
                await router.insert("甲乙", lambda: True)
        assert keyboard.sent == [] and keyboard.connects == 0 and bus.disconnected
        assert [m.member for m in bus.calls if m.member.startswith("Begin")] == [
            "Begin3"
        ]
        assert not any(m.member == "Commit" for m in bus.calls)
        await router.aclose()

    asyncio.run(run())
