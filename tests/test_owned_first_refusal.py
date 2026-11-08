import asyncio
import time

import pytest
from test_explicit_owned import router_for
from test_owned_bounded_protocol import Bus, xml

from inkecho.platform.output_router import OutputRouterError


@pytest.mark.parametrize(
    "mode", ["plain", "cancel", "expired", "cleanup", "cancel-cleanup", "task-cancel"]
)
def test_owned_zero_refusal(mode):
    async def run():
        class Reject(Bus):
            async def call(self, m):
                reply = await super().call(m)
                if m.member == "CommitBounded":
                    reply.body = ["no_service"]
                return reply

        router, bus, k, _ = router_for(bus=Reject(xml()))

        async def detector():
            return None

        router._legacy_detector = detector

        async def owned_detector():
            return ("ibus", ":1.23")

        router._system_detector = owned_detector
        factory = router._owned_factory
        active = [True]
        deadline = [time.monotonic() + 30]
        closes = []

        def wrapped():
            bridge = factory()
            close = bridge.close_after_no_service

            async def checked_close():
                closes.append(True)
                await close()
                if mode in {"cancel", "cancel-cleanup"}:
                    active[0] = False
                if mode == "expired":
                    deadline[0] = time.monotonic() - 1
                if mode == "task-cancel":
                    raise asyncio.CancelledError
                if mode in {"cleanup", "cancel-cleanup"}:
                    raise OSError("synthetic")

            bridge.close_after_no_service = checked_close
            return bridge

        router._owned_factory = wrapped
        # A mutable clock exposes expiry arriving during close without sleeps.
        original = router._check_task
        router._check_task = lambda predicate, end: original(predicate, deadline[0])
        await router.prepare_task("auto")
        expected = {
            "plain": "input_capability_unknown",
            "cancel": "input_cancelled",
            "expired": "expired",
            "cleanup": "ibus_cleanup_failed",
            "cancel-cleanup": "input_cancelled",
        }
        if mode == "task-cancel":
            with pytest.raises(asyncio.CancelledError):
                async with router.output_session():
                    await router.insert("甲", lambda: active[0])
        else:
            with pytest.raises(
                OutputRouterError, match="^" + expected[mode] + "$"
            ) as e:
                async with router.output_session():
                    await router.insert("甲", lambda: active[0])
            assert e.value.acknowledged_attempts == 0
        assert closes == [True] and bus.disconnected and router.selected is None
        assert not k.sent and k.connects == 0
        assert len([x for x in bus.calls if x[0] == "CommitBounded"]) == 1

    asyncio.run(run())


def test_initial_absent_still_keyboard():
    async def run():
        router, bus, k, _ = router_for(state="absent")

        async def detector():
            return None

        router._legacy_detector = detector

        async def owned_detector():
            return ("ibus", ":1.23")

        router._system_detector = owned_detector
        await router.prepare_task("auto")
        async with router.output_session():
            await router.insert("甲", lambda: True)
        assert k.sent == ["甲"] and not bus.calls

    asyncio.run(run())


def test_successful_consecutive_fragments_remain_on_owned():
    async def run():
        router, bus, k, _ = router_for()

        async def detector():
            return None

        router._legacy_detector = detector

        async def owned_detector():
            return ("ibus", ":1.23")

        router._system_detector = owned_detector
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown"):
            async with router.output_session():
                await router.insert("甲", lambda: True)
                # Accepted replies remain valid; the fake bus does not model focus.
                await router.insert("乙", lambda: True)
        assert [x[2][1] for x in bus.calls if x[0] == "CommitBounded"] == ["甲", "乙"]
        assert not k.sent and k.connects == 0

    asyncio.run(run())
