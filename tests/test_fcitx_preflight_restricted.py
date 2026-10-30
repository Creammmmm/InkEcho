# Restricted auto routing must stop before opening keyboard fallback.

import asyncio

import pytest
from test_output_router import Bridge, Keyboard

from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.output_router import OutputRouterError


@pytest.mark.parametrize("state", ["enabled", "unknown"])
def test_failed_fcitx_preflight_does_not_open_forbidden_keyboard(state):
    async def run():
        keyboard = Keyboard()
        bridge = Bridge("unavailable")

        async def state_probe():
            return state

        async def detector():
            return ("fcitx", ":1.8")

        router = DefaultAutoOutputRouter(
            keyboard,
            state_probe=state_probe,
            system_detector=detector,
            bridge_factory=lambda: bridge,
        )
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="input_capability_unknown"):
            async with router.output_session():
                await router.insert("甲", lambda: True)
        assert bridge.closed and bridge.sent == []
        assert keyboard.connects == keyboard.authorizations == 0
        assert keyboard.sent == [] and router.acknowledged_attempts == 0

    asyncio.run(run())


@pytest.mark.parametrize("state", ["absent", "disabled"])
def test_failed_fcitx_preflight_still_falls_back_when_allowed(state):
    async def run():
        keyboard = Keyboard()
        bridge = Bridge("unavailable")

        async def state_probe():
            return state

        async def detector():
            return ("fcitx", ":1.8")

        router = DefaultAutoOutputRouter(
            keyboard,
            state_probe=state_probe,
            system_detector=detector,
            bridge_factory=lambda: bridge,
        )
        await router.prepare_task("auto")
        async with router.output_session():
            assert await router.insert("甲", lambda: True) == 1
        assert bridge.closed and bridge.sent == []
        assert keyboard.connects == keyboard.authorizations == 1
        assert keyboard.sent == ["甲"]

    asyncio.run(run())


@pytest.mark.parametrize(
    "reason",
    ["owner_changed", "cleanup_error", "cleanup_flag", "cancel_cleanup", "success"],
)
def test_restricted_preflight_rechecks_and_cleans_without_keyboard(reason):
    async def run():
        keyboard = Keyboard()
        active = [True]
        diagnostics = []
        cleanup_started = asyncio.Event()
        cleanup_continue = asyncio.Event()
        calls = 0

        class Tracked(Bridge):
            def __init__(self):
                super().__init__()
                self.aborts = 0
                self.preflight_cleanup_failed = False

            async def connect(self, **kwargs):
                assert kwargs == {"expected_owner": ":1.8"}
                if reason in {"cleanup_error", "cleanup_flag", "cancel_cleanup"}:
                    raise RuntimeError("unavailable")

            async def abort_preflight(self):
                self.aborts += 1
                if reason == "cleanup_error":
                    raise RuntimeError("cleanup")
                if reason == "cleanup_flag":
                    self.preflight_cleanup_failed = True
                if reason == "cancel_cleanup":
                    cleanup_started.set()
                    await cleanup_continue.wait()

        bridge = Tracked()

        async def state_probe():
            return "unknown"

        async def detector():
            nonlocal calls
            calls += 1
            # Initial pinned detection, checked detection, then refreshed owner.
            if reason == "owner_changed" and calls == 3:
                return ("fcitx", ":1.9")
            return ("fcitx", ":1.8")

        router = DefaultAutoOutputRouter(
            keyboard,
            state_probe=state_probe,
            system_detector=detector,
            bridge_factory=lambda: bridge,
        )
        router._diagnostic_handler = diagnostics.append
        await router.prepare_task("auto")
        if reason == "success":
            async with router.output_session():
                assert await router.insert("甲", lambda: active[0]) == 1
            assert bridge.aborts == 0 and bridge.sent == ["甲"]
        else:
            expected = {
                "owner_changed": "input_capability_unknown",
                "cleanup_error": "fcitx_cleanup_failed",
                "cleanup_flag": "fcitx_cleanup_failed",
                "cancel_cleanup": "input_cancelled",
            }[reason]

            async def insert():
                async with router.output_session():
                    await router.insert("甲", lambda: active[0])

            task = asyncio.create_task(insert())
            if reason == "cancel_cleanup":
                await asyncio.wait_for(cleanup_started.wait(), 1)
                active[0] = False
                cleanup_continue.set()
            with pytest.raises(OutputRouterError, match="^" + expected + "$"):
                await asyncio.wait_for(task, 1)
            assert bridge.aborts == 1 and bridge.sent == []
            assert router.acknowledged_attempts == 0
        assert keyboard.connects == keyboard.authorizations == 0
        assert keyboard.sent == []
        assert diagnostics == (
            ["input_cleanup_failed"]
            if reason in {"cleanup_error", "cleanup_flag"}
            else []
        )

    asyncio.run(run())
