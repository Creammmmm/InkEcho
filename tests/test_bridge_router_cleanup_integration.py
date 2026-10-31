import asyncio
import time
from types import SimpleNamespace

from dbus_next import MessageType
from test_fcitx_owned_handoff import Keyboard

from inkecho.platform.ibus_owned import Client, IBusBridge
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.output_router import OutputRouterError


class Cap:
    name = "cap"
    token = "token"

    def close(self):
        pass


class Bus:
    async def connect(self):
        pass

    def add_message_handler(self, _):
        pass

    def disconnect(self):
        pass


class FaultClient(Client):
    def __init__(self, cap, *, scenario, **kw):
        super().__init__(cap, bus_factory=Bus, owner_verifier=self.verify, **kw)
        self.scenario = scenario
        self.enter = asyncio.Event()
        self.release = asyncio.Event()
        self.cleanup_enter = asyncio.Event()
        self.n = 0
        self.remote = False

    async def verify(self, _):
        return True

    async def _call(self, m, _):
        return SimpleNamespace(
            message_type=MessageType.METHOD_RETURN,
            body=[":1.2"] if m.member == "GetNameOwner" else [],
        )

    async def _negotiate_batch(self):
        return 2

    async def _request(self, method, *args):
        if method.startswith("Begin"):
            self.enter.set()
            if self.scenario == "lost":
                raise TimeoutError()
            if self.scenario == "denied":
                return SimpleNamespace(
                    signature="b", message_type=MessageType.METHOD_RETURN, body=[False]
                )
            if self.scenario == "malformed":
                return SimpleNamespace(
                    signature="s", message_type=MessageType.METHOD_RETURN, body=["no"]
                )
            await self.release.wait()
            self.remote = True
            return SimpleNamespace(
                signature="b", message_type=MessageType.METHOD_RETURN, body=[True]
            )
        self.n += 1
        if self.scenario == "repeat_cancel" and self.n == 2:
            self.cleanup_enter.set()
            await asyncio.Event().wait()
        was = self.remote
        self.remote = False
        return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=[was])


async def env(scenario):
    items = []
    bridges = []
    reports = []

    async def state():
        return "enabled"

    async def detector():
        return None

    async def probe():
        return ("ibus", ":1.2")

    def client(cap, **kw):
        c = FaultClient(cap, scenario=scenario, **kw)
        items.append(c)
        return c

    def factory():
        b = IBusBridge(
            runtime_dir="/tmp",
            capability_factory=lambda _: Cap(),
            client_factory=client,
        )
        bridges.append(b)
        return b

    router = DefaultAutoOutputRouter(
        Keyboard(),
        state_probe=state,
        system_detector=detector,
        owned_probe=probe,
        owned_factory=factory,
    )
    router.set_diagnostic_handler(reports.append)
    await router.prepare_task("auto")

    async def insert():
        async with router.output_session():
            await router.insert("甲", lambda: True, deadline=time.monotonic() + 10)

    return router, insert, items, bridges, reports


def test_begin_reply_lost_forbids_keyboard():
    async def run():
        router, insert, items, bridges, reports = await env("lost")
        try:
            await insert()
            raise AssertionError("expected failure")
        except OutputRouterError as e:
            assert e.code == "ibus_cleanup_failed"
        assert items[0].cleanup_failed and bridges[0].preflight_cleanup_failed

    asyncio.run(run())


def test_cancel_again_during_compensation_forbids_keyboard():
    async def run():
        router, insert, items, bridges, reports = await env("repeat_cancel")
        task = asyncio.create_task(insert())
        while not items:
            await asyncio.sleep(0.001)
        c = items[0]
        await c.enter.wait()
        await c.cancel()
        c.release.set()
        await c.cleanup_enter.wait()
        task.cancel()
        try:
            await task
            raise AssertionError("expected cancellation")
        except asyncio.CancelledError:
            pass
        assert c.cleanup_failed and bridges[0].preflight_cleanup_failed

    asyncio.run(run())


def test_begin_refusal_surfaces_precise_diagnostic_without_keyboard():
    async def run():
        router, insert, items, bridges, reports = await env("denied")
        try:
            await insert()
            raise AssertionError("expected refusal")
        except OutputRouterError as error:
            assert error.code == "ibus_authorization_failed"
        assert not items[0].cleanup_failed
        assert not bridges[0].preflight_cleanup_failed

    asyncio.run(run())


def test_malformed_begin_is_cleanup_unknown_not_refusal():
    async def run():
        router, insert, items, bridges, reports = await env("malformed")
        try:
            await insert()
            raise AssertionError("expected failure")
        except OutputRouterError as error:
            assert error.code == "ibus_cleanup_failed"
        assert items[0].cleanup_failed and bridges[0].preflight_cleanup_failed

    asyncio.run(run())
