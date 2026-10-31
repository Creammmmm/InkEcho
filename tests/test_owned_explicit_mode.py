"""The separately selected IBus V2 mode never inherits bounded-auto claims."""

import asyncio

import pytest
from PySide6.QtWidgets import QLabel
from test_output_router import Bridge, Keyboard
from test_ui import window as window

from inkecho.platform.ibus import IBusBridge
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.output_router import OutputRouterError


def test_explicit_ibus_factory_remains_existing_v2_bridge():
    router = DefaultAutoOutputRouter(Keyboard())
    assert router._ibus_factory is IBusBridge


def test_default_router_explicit_ibus_never_probes_owned_or_uses_neighbor_delay():
    async def run():
        keyboard, legacy = Keyboard(), Bridge()

        async def forbidden():
            raise AssertionError("Explicit IBus must not probe automatic owned route")

        def forbidden_factory():
            raise AssertionError("Explicit IBus must keep separate V2 bridge")

        router = DefaultAutoOutputRouter(
            keyboard,
            legacy_factory=lambda: legacy,
            state_probe=forbidden,
            owned_probe=forbidden,
            owned_factory=forbidden_factory,
        )
        assert await router.prepare_task("ibus") == "ibus"
        with pytest.raises(OutputRouterError, match="ibus_delivery_unknown"):
            async with router.output_session():
                assert not router.neighbor_batches_enabled
                assert await router.insert("甲", lambda: True) == 1
                assert legacy.sent == ["甲"]
        assert keyboard.sent == [] and legacy.closed

    asyncio.run(run())


def test_help_scopes_bounded_upgrade_to_automatic_owned_extension(window):
    labels = [x.text() for x in window.settings_page.compatibility.findChildren(QLabel)]
    bounded = next(text for text in labels if "带服务端期限的新协议" in text)
    assert "显式 IBus 的旧 V2" in bounded
    assert "先停用并卸载" in bounded and "重新登录" in bounded
    assert "旧客户端不具备新版保护" in bounded and "无法确认目标是否收到" in bounded
    legacy = next(text for text in labels if "不会自动覆盖旧扩展" in text)
    assert "带服务端期限" not in legacy and "新版扩展拒绝旧协议" not in legacy
