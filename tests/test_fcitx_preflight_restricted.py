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


def test_failed_stream_preflight_cannot_resume_with_keyboard():
    async def run():
        keyboard = Keyboard()
        keyboard.authorized = True  # Previously authorized session remains live.
        bridge = Bridge("unavailable")

        async def state_probe():
            return "unknown"

        async def detector():
            return ("fcitx", ":1.8")

        router = DefaultAutoOutputRouter(
            keyboard,
            state_probe=state_probe,
            system_detector=detector,
            bridge_factory=lambda: bridge,
        )
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="output_failed"):
            async with router.output_session():
                with pytest.raises(OutputRouterError, match="input_capability_unknown"):
                    await router.prepare_stream(lambda: True)
                with pytest.raises(OutputRouterError, match="output_failed"):
                    await router.insert("甲", lambda: True)
        assert bridge.closed and bridge.sent == []
        assert keyboard.connects == keyboard.authorizations == 0
        assert keyboard.sent == []

    asyncio.run(run())


@pytest.mark.parametrize("stop", ["predicate", "async_cancel"])
def test_cancelled_stream_preflight_cannot_resume_but_next_task_can(stop):
    async def run():
        keyboard = Keyboard()
        keyboard.authorized = True
        active = [stop != "predicate"]

        async def state_probe():
            raise asyncio.CancelledError

        router = DefaultAutoOutputRouter(keyboard, state_probe=state_probe)
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="output_failed"):
            async with router.output_session():
                expected = (
                    OutputRouterError if stop == "predicate" else asyncio.CancelledError
                )
                with pytest.raises(expected):
                    await router.prepare_stream(lambda: active[0])
                active[0] = True
                with pytest.raises(OutputRouterError, match="output_failed"):
                    await router.insert("甲", lambda: active[0])
        assert keyboard.sent == []
        await router.prepare_task("keyboard")
        async with router.output_session():
            assert await router.insert("乙", lambda: True) == 1
        assert keyboard.sent == ["乙"]

    asyncio.run(run())


@pytest.mark.parametrize("stop", ["task_cancel", "deadline", "cancel_cleanup"])
def test_stream_preflight_real_async_stop_poison_scope(stop):
    import time

    async def run():
        keyboard = Keyboard()
        keyboard.authorized = True
        started = asyncio.Event()
        release = asyncio.Event()

        class Tracked(Bridge):
            async def connect(self, **kwargs):
                if stop == "cancel_cleanup":
                    raise RuntimeError("unavailable")

            async def abort_preflight(self):
                self.closed = True
                if stop == "cancel_cleanup":
                    started.set()
                    await release.wait()

        bridge = Tracked()

        async def state_probe():
            return "unknown"

        async def detector():
            if stop != "cancel_cleanup":
                started.set()
                await release.wait()
            return ("fcitx", ":1.8")

        router = DefaultAutoOutputRouter(
            keyboard,
            state_probe=state_probe,
            system_detector=detector,
            bridge_factory=lambda: bridge,
        )
        await router.prepare_task("auto")

        async def output():
            with pytest.raises(OutputRouterError, match="output_failed"):
                async with router.output_session():
                    deadline = time.monotonic() + 0.1 if stop == "deadline" else None
                    expected = (
                        OutputRouterError
                        if stop == "deadline"
                        else asyncio.CancelledError
                    )
                    with pytest.raises(expected) as caught:
                        await router.prepare_stream(lambda: True, deadline=deadline)
                    if stop == "deadline":
                        assert caught.value.code == "expired"
                    with pytest.raises(OutputRouterError, match="output_failed"):
                        await router.insert("甲", lambda: True)

        task = asyncio.create_task(output())
        await asyncio.wait_for(started.wait(), 1)
        if stop != "deadline":
            task.cancel()
        await asyncio.wait_for(task, 1)
        assert bridge.sent == keyboard.sent == []
        assert keyboard.connects == keyboard.authorizations == 0
        await router.prepare_task("keyboard")
        async with router.output_session():
            assert await router.insert("乙", lambda: True) == 1
        assert keyboard.sent == ["乙"]

    asyncio.run(run())
