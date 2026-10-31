"""Synthetic transport faults with real IBus bridges and capabilities."""

import asyncio
import os

import pytest
from test_output_router import Keyboard

from inkecho.platform import ibus, ibus_lifecycle, ibus_owned
from inkecho.platform.keyboard import KeyboardError
from inkecho.platform.output_router import OutputRouter, OutputRouterError
from inkecho.providers import ProviderError


@pytest.mark.parametrize("module", [ibus, ibus_owned], ids=["legacy", "owned"])
@pytest.mark.parametrize("body", ["provider_error", "sent", "cancelled", "expired"])
def test_ibus_scope_cleanup_does_not_mask_stop_or_allow_replay(
    tmp_path, monkeypatch, module, body
):
    async def run():
        clients = []
        reports = []

        class Client:
            def __init__(self, cap, **_kwargs):
                self.cap = cap
                self._sequence = 0
                self._attempted_characters = 0
                self.cancel_calls = 0
                clients.append(self)

            async def begin(self, **_kwargs):
                pass

            async def cancel(self):
                self.cancel_calls += 1

            async def close(self):
                self.cap.close()

            async def insert(self, text, active, **_kwargs):
                assert active()
                self._sequence += len(text)
                self._attempted_characters += len(text)
                return len(text)

        keyboard = Keyboard()
        bridge = module.IBusBridge(runtime_dir=str(tmp_path), client_factory=Client)
        await bridge.connect()
        router = OutputRouter(keyboard)
        router._selected, router._kind = bridge, "ibus"
        router.set_diagnostic_handler(reports.append)
        original = os.unlink

        def fail_cap(path, **kwargs):
            if str(path).startswith("cap-"):
                raise OSError("private data must not leak")
            return original(path, **kwargs)

        monkeypatch.setattr(ibus_lifecycle.os, "unlink", fail_cap)
        expected = asyncio.CancelledError if body == "cancelled" else OutputRouterError
        with pytest.raises(expected) as caught:
            async with router.output_session():
                if body == "provider_error":
                    raise ProviderError("network")
                if body == "cancelled":
                    raise asyncio.CancelledError
                if body == "expired":
                    raise OutputRouterError("expired")
                assert await router.insert("甲乙", lambda: True) == 2
        assert reports == ["input_cleanup_failed"]
        assert clients[0].cancel_calls == 1
        assert clients[0].cap._fd is None
        assert (
            keyboard.connects == 0
            and keyboard.authorizations == 0
            and keyboard.sent == []
        )
        assert router.selected is None
        if body == "provider_error":
            assert isinstance(caught.value, KeyboardError)
            assert caught.value.code == "input_cleanup_failed"
            assert "private" not in str(caught.value)
        elif body == "sent":
            assert caught.value.code == "ibus_delivery_unknown"
            assert caught.value.acknowledged_attempts == 2
            assert caught.value.dispatch_complete
        elif body == "expired":
            assert caught.value.code == "expired"
        monkeypatch.setattr(ibus_lifecycle.os, "unlink", original)
        for p in tmp_path.glob("cap-*"):
            p.unlink()

    asyncio.run(run())


@pytest.mark.parametrize("no_service", [False, True])
def test_new_prepare_during_owned_cleanup_fault_keeps_old_scope_semantics(no_service):
    from test_explicit_owned import router_for
    from test_owned_bounded_protocol import Bus, xml

    async def run():
        class ReplyBus(Bus):
            async def call(self, message):
                reply = await super().call(message)
                if no_service and message.member == "CommitBounded":
                    reply.body = ["no_service"]
                return reply

        router, bus, keyboard, _ = router_for(bus=ReplyBus(xml()))
        factory = router._owned_factory
        reports = []
        router.set_diagnostic_handler(reports.append)

        def wrapped_factory():
            bridge = factory()
            close = bridge.aclose

            async def fail_after_new_prepare():
                await close()
                await router.prepare_task("auto")
                raise OSError("private cleanup error")

            bridge.aclose = fail_after_new_prepare
            return bridge

        router._owned_factory = wrapped_factory
        await router.prepare_task("ibus-owned")
        expected = "ibus_cleanup_failed" if no_service else "ibus_delivery_unknown"
        with pytest.raises(OutputRouterError, match="^" + expected + "$") as caught:
            async with router.output_session():
                await router.insert("X", lambda: True)
        assert caught.value.acknowledged_attempts == (0 if no_service else 1)
        assert not caught.value.dispatch_complete
        assert reports == ["input_cleanup_failed"]
        assert bus.disconnected and not keyboard.sent
        assert router.selected == "keyboard"
        await router.discard_task()

    asyncio.run(run())
