import asyncio
import time

import pytest
from test_fcitx_owned_handoff import Keyboard

from inkecho.platform.ibus import IBusBridgeError
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.output_router import OutputRouterError


class Bridge:
    def __init__(self, code, cleanup=False):
        self.code = code
        self.preflight_cleanup_failed = cleanup

    async def connect(self, **_):
        raise IBusBridgeError(self.code)

    async def aclose(self):
        pass


@pytest.mark.parametrize(
    "code,cleanup,expected",
    [
        ("authorization_failed", False, "ibus_authorization_failed"),
        ("authorization_failed", True, "ibus_cleanup_failed"),
        ("unavailable", False, "input_capability_unknown"),
        ("upgrade_required", False, "ibus_upgrade_required"),
    ],
)
def test_auto_owned_no_fallback(code, cleanup, expected):
    async def go():
        async def state():
            return "enabled"

        async def legacy():
            return None

        async def owned():
            return ("ibus", ":1.42")

        bridge = Bridge(code, cleanup)
        router = DefaultAutoOutputRouter(
            Keyboard(),
            state_probe=state,
            system_detector=legacy,
            owned_probe=owned,
            owned_factory=lambda: bridge,
        )
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError, match="^" + expected + "$"):
            async with router.output_session():
                await router.insert("甲", lambda: True, deadline=time.monotonic() + 3)

    asyncio.run(go())
