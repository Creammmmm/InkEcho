"""Offline session policy; no real desktop compatibility claim."""

import asyncio

import pytest
from test_output_router import Bridge, Keyboard

from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.output_router import OutputRouterError


@pytest.mark.parametrize("framework", [None, ("fcitx", ":1.8")])
@pytest.mark.parametrize("cancel", [False, True])
def test_xorg_skips_irrelevant_extension(framework, cancel):
    async def go():
        k, bridge = Keyboard(), Bridge()

        async def forbidden():
            raise AssertionError("irrelevant owned extension probe")

        async def detector():
            return framework

        r = DefaultAutoOutputRouter(
            k,
            desktop_environ={"XDG_SESSION_TYPE": "x11"},
            state_probe=forbidden,
            owned_probe=forbidden,
            system_detector=detector,
            bridge_factory=lambda: bridge,
        )
        await r.prepare_task("auto")
        if cancel:
            with pytest.raises(OutputRouterError, match="input_cancelled"):
                async with r.output_session():
                    await r.insert("甲", lambda: False)
            assert not k.sent and not bridge.sent and k.connects == 0
        else:
            async with r.output_session():
                await r.insert("甲", lambda: True)
            assert (bridge.sent if framework else k.sent) == ["甲"]
            assert not (k.sent if framework else bridge.sent)

    asyncio.run(go())


@pytest.mark.parametrize(
    "env",
    [
        {"XDG_SESSION_TYPE": "wayland"},
        {"XDG_SESSION_TYPE": "x11", "WAYLAND_DISPLAY": "wayland-0"},
        {},
    ],
)
def test_other_sessions_preserve_extension_guard(env):
    async def go():
        calls = []

        async def state():
            calls.append(True)
            raise OutputRouterError("input_capability_unknown")

        async def detector():
            return None

        k = Keyboard()
        r = DefaultAutoOutputRouter(
            k, desktop_environ=env, state_probe=state, system_detector=detector
        )
        await r.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="input_capability_unknown"):
            async with r.output_session():
                await r.insert("甲", lambda: True)
        assert calls == [True] and not k.sent and k.connects == 0

    asyncio.run(go())


@pytest.mark.parametrize("mode", ["ibus", "ibus-owned"])
def test_xorg_explicit_ibus_keeps_selected_route(mode):
    async def go():
        k, bridge = Keyboard(), Bridge()
        calls = []

        async def state():
            calls.append(True)
            return "absent"

        r = DefaultAutoOutputRouter(
            k,
            desktop_environ={"XDG_SESSION_TYPE": "x11"},
            state_probe=state,
            legacy_factory=lambda: bridge,
        )
        await r.prepare_task(mode)
        if mode == "ibus-owned":
            with pytest.raises(OutputRouterError, match="ibus_unavailable"):
                async with r.output_session():
                    await r.insert("甲", lambda: True)
            assert calls == [True]
        else:
            assert r.selected == "ibus"
            await r.discard_task()
        assert k.connects == 0 and not k.sent

    asyncio.run(go())
