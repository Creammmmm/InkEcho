import asyncio
from types import SimpleNamespace

import pytest
from dbus_next import MessageType

from inkecho.platform.ibus_owned_auto import probe_owned
from inkecho.platform.output_router import OutputRouterError


def reply(body, signature="s", sender=":1.2", kind=MessageType.METHOD_RETURN):
    return SimpleNamespace(
        body=body, signature=signature, sender=sender, message_type=kind
    )


class Bus:
    def __init__(self, mode="ready"):
        self.mode = mode
        self.disconnected = False
        self.handler = None
        self.connected = asyncio.Event()

    async def connect(self):
        if self.mode == "connection_error":
            raise OSError("offline")
        self.connected.set()
        return self

    def add_message_handler(self, h):
        self.handler = h

    async def call(self, m):
        if m.member == "AddMatch":
            if self.mode == "match_hang":
                await asyncio.Event().wait()
            if self.mode == "match_error":
                return reply([], kind=MessageType.ERROR, sender="org.freedesktop.DBus")
            return reply([], signature="", sender="org.freedesktop.DBus")
        if m.member == "GetNameOwner":
            return reply([":1.2"], sender="org.freedesktop.DBus")
        if m.member == "Probe":
            if self.mode == "hang":
                await asyncio.Event().wait()
            return reply([self.mode])
        raise AssertionError(m.member)

    def disconnect(self):
        self.disconnected = True


async def verify(_):
    return True


@pytest.mark.parametrize(
    "mode,expected",
    [("ready", ("ibus", ":1.2")), ("blocked", ("ibus", ":1.2")), ("none", None)],
)
def test_probe_status(mode, expected):
    async def go():
        b = Bus(mode)
        assert await probe_owned(bus_factory=lambda: b, verifier=verify) == expected
        assert b.disconnected

    asyncio.run(go())


@pytest.mark.parametrize("mode", ["connection_error", "match_error", "match_hang"])
def test_probe_fail_closed_and_disconnect(mode):
    async def go():
        b = Bus(mode)
        with pytest.raises(OutputRouterError, match="input_capability_unknown"):
            await asyncio.wait_for(
                probe_owned(bus_factory=lambda: b, verifier=verify), 1.3
            )
        assert b.disconnected

    asyncio.run(go())


def test_cancel_disconnects():
    async def go():
        b = Bus("hang")
        t = asyncio.create_task(probe_owned(bus_factory=lambda: b, verifier=verify))
        await b.connected.wait()
        await asyncio.sleep(0.01)
        t.cancel()
        with pytest.raises(asyncio.CancelledError):
            await t
        assert b.disconnected

    asyncio.run(go())


def test_concurrent_independent_connections():
    async def go():
        a = Bus("ready")
        b = Bus("blocked")
        r = await asyncio.gather(
            probe_owned(bus_factory=lambda: a, verifier=verify),
            probe_owned(bus_factory=lambda: b, verifier=verify),
        )
        assert (
            r == [("ibus", ":1.2"), ("ibus", ":1.2")]
            and a.disconnected
            and b.disconnected
            and a.handler is not b.handler
        )

    asyncio.run(go())


def test_probe_rejects_owner_aba():
    from inkecho.platform.ibus_owned_auto import SERVICE

    class ABABus(Bus):
        async def call(self, m):
            if m.member == "Probe":
                for old, new in ((":1.2", ""), ("", ":1.2")):
                    self.handler(
                        SimpleNamespace(
                            message_type=MessageType.SIGNAL,
                            sender="org.freedesktop.DBus",
                            interface="org.freedesktop.DBus",
                            member="NameOwnerChanged",
                            signature="sss",
                            body=[SERVICE, old, new],
                        )
                    )
            return await super().call(m)

    async def go():
        b = ABABus()
        with pytest.raises(OutputRouterError, match="input_capability_unknown"):
            await probe_owned(bus_factory=lambda: b, verifier=verify)
        assert b.disconnected

    asyncio.run(go())


def test_probe_ignores_unrelated_owner_signal():
    class UnrelatedBus(Bus):
        async def call(self, m):
            if m.member == "Probe":
                self.handler(
                    SimpleNamespace(
                        message_type=MessageType.SIGNAL,
                        sender="org.freedesktop.DBus",
                        interface="org.freedesktop.DBus",
                        member="NameOwnerChanged",
                        signature="sss",
                        body=["org.example.Other", ":1.2", ""],
                    )
                )
            return await super().call(m)

    async def go():
        b = UnrelatedBus()
        assert await probe_owned(bus_factory=lambda: b, verifier=verify) == (
            "ibus",
            ":1.2",
        )
        assert b.disconnected

    asyncio.run(go())
