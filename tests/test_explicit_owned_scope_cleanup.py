"""Stop precedence after final selected-backend cleanup, not only preflight."""

import asyncio
import time

import pytest
from test_explicit_owned import router_for
from test_owned_bounded_protocol import Bus, xml

from inkecho.platform.output_router import OutputRouterError


@pytest.mark.parametrize("stop", ["cancel", "expire"])
@pytest.mark.parametrize("outcome", ["no_service", "attempted", "unknown"])
@pytest.mark.parametrize("outer_scope", [False, True])
def test_final_cleanup_stop_keeps_attempts_without_fallback(stop, outcome, outer_scope):
    async def run():
        class ReplyBus(Bus):
            async def call(self, message):
                reply = await super().call(message)
                if message.member == "CommitBounded":
                    reply.body = [outcome]
                return reply

        router, bus, keyboard, calls = router_for(bus=ReplyBus(xml()))
        active = True
        deadline = time.monotonic() + 1
        close_was_valid = []
        factory = router._owned_factory

        def wrapped_factory():
            bridge = factory()
            close = bridge.aclose

            async def stopped_during_close():
                nonlocal active
                close_was_valid.append(active and time.monotonic() < deadline)
                await close()
                if stop == "cancel":
                    active = False
                else:
                    await asyncio.sleep(max(0, deadline - time.monotonic()) + 0.01)

            bridge.aclose = stopped_during_close
            return bridge

        router._owned_factory = wrapped_factory
        await router.prepare_task("ibus-owned")
        expected = "input_cancelled" if stop == "cancel" else "expired"
        with pytest.raises(OutputRouterError, match="^" + expected + "$") as error:
            if outer_scope:
                async with router.output_session():
                    await router.insert("X", lambda: active, deadline=deadline)
            else:
                await router.insert("X", lambda: active, deadline=deadline)
        assert close_was_valid == [True]
        assert error.value.acknowledged_attempts == (1 if outcome == "attempted" else 0)
        assert not error.value.dispatch_complete
        assert bus.disconnected and calls.count("factory") == 1
        assert keyboard.connects == keyboard.authorizations == 0 and keyboard.sent == []
        assert sum(name == "CommitBounded" for name, _, _ in bus.calls) == 1
        with pytest.raises(OutputRouterError):
            await router.insert("X", lambda: True)
        assert sum(name == "CommitBounded" for name, _, _ in bus.calls) == 1

    asyncio.run(run())


def test_real_task_cancel_survives_cleanup_error_and_is_not_replayed():
    async def run():
        router, bus, keyboard, _ = router_for()
        factory = router._owned_factory
        diagnostics = []
        router.set_diagnostic_handler(diagnostics.append)

        def wrapped_factory():
            bridge = factory()
            close = bridge.aclose

            async def failed_cleanup():
                await close()
                raise OSError("synthetic cleanup failure")

            bridge.aclose = failed_cleanup
            return bridge

        router._owned_factory = wrapped_factory
        await router.prepare_task("ibus-owned")

        async def output():
            async with router.output_session():
                assert await router.insert("X", lambda: True) == 1
                asyncio.current_task().cancel()
                await asyncio.sleep(0)

        task = asyncio.create_task(output())
        with pytest.raises(asyncio.CancelledError):
            await task
        assert diagnostics == ["input_cleanup_failed"]
        assert bus.disconnected and not keyboard.sent
        assert sum(name == "CommitBounded" for name, _, _ in bus.calls) == 1

    asyncio.run(run())


def test_later_fragment_cannot_renew_scope_deadline_during_cleanup():
    async def run():
        router, bus, keyboard, _ = router_for()
        deadline = time.monotonic() + 1
        factory = router._owned_factory

        def wrapped_factory():
            bridge = factory()
            close = bridge.aclose

            async def late_cleanup():
                await close()
                await asyncio.sleep(max(0, deadline - time.monotonic()) + 0.01)

            bridge.aclose = late_cleanup
            return bridge

        router._owned_factory = wrapped_factory
        await router.prepare_task("ibus-owned")
        with pytest.raises(OutputRouterError, match="^expired$") as error:
            async with router.output_session():
                assert await router.insert("A", lambda: True, deadline=deadline) == 1
                assert await router.insert("B", lambda: True, deadline=None) == 1
        assert error.value.acknowledged_attempts == 2
        assert bus.disconnected and not keyboard.sent

    asyncio.run(run())


@pytest.mark.parametrize("body_error", [False, True])
def test_cleanup_fault_preserves_structured_unknown_and_attempt_count(body_error):
    async def run():
        router, bus, keyboard, _ = router_for()
        diagnostics = []
        router.set_diagnostic_handler(diagnostics.append)
        factory = router._owned_factory

        def wrapped_factory():
            bridge = factory()
            close = bridge.aclose

            async def fail():
                await close()
                raise OSError("controlled cleanup fault")

            bridge.aclose = fail
            return bridge

        router._owned_factory = wrapped_factory
        await router.prepare_task("ibus-owned")
        with pytest.raises(OutputRouterError, match="^ibus_delivery_unknown$") as error:
            async with router.output_session():
                assert await router.insert("X", lambda: True) == 1
                if body_error:
                    raise OutputRouterError(
                        "ibus_delivery_unknown", acknowledged_attempts=1
                    )
        assert error.value.acknowledged_attempts == 1
        assert not error.value.dispatch_complete
        assert diagnostics == ["input_cleanup_failed"]
        assert bus.disconnected and not keyboard.sent
        assert sum(name == "CommitBounded" for name, _, _ in bus.calls) == 1

    asyncio.run(run())


def test_new_prepare_during_cleanup_cannot_erase_old_scope_stop():
    async def run():
        router, bus, keyboard, _ = router_for()
        active = True
        factory = router._owned_factory

        def wrapped_factory():
            bridge = factory()
            close = bridge.aclose

            async def replaced_during_close():
                nonlocal active
                await close()
                active = False
                await router.prepare_task("auto")

            bridge.aclose = replaced_during_close
            return bridge

        router._owned_factory = wrapped_factory
        await router.prepare_task("ibus-owned")
        with pytest.raises(OutputRouterError, match="^input_cancelled$") as error:
            async with router.output_session():
                assert await router.insert("X", lambda: active) == 1
        assert error.value.acknowledged_attempts == 1
        assert not error.value.dispatch_complete
        assert bus.disconnected and not keyboard.sent
        assert not router._explicit_owned_task

    asyncio.run(run())


def test_zero_attempt_cleanup_fault_cannot_authorize_another_route():
    async def run():
        class ZeroBus(Bus):
            async def call(self, message):
                reply = await super().call(message)
                if message.member == "CommitBounded":
                    reply.body = ["no_service"]
                return reply

        router, bus, keyboard, _ = router_for(bus=ZeroBus(xml()))
        factory = router._owned_factory

        def wrapped_factory():
            bridge = factory()
            close = bridge.aclose

            async def fail():
                await close()
                raise OSError("controlled cleanup fault")

            bridge.aclose = fail
            return bridge

        router._owned_factory = wrapped_factory
        await router.prepare_task("ibus-owned")
        with pytest.raises(OutputRouterError, match="^ibus_cleanup_failed$") as error:
            async with router.output_session():
                await router.insert("X", lambda: True)
        assert error.value.acknowledged_attempts == 0
        assert not error.value.dispatch_complete
        assert bus.disconnected and not keyboard.sent
        assert keyboard.connects == keyboard.authorizations == 0

    asyncio.run(run())
