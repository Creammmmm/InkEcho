"""Opt-in research auto router; never wired to the application by this patch."""

import asyncio

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus

from inkecho.platform.framework_detection import detect_system_framework
from inkecho.platform.ibus import IBusBridge as LegacyIBusBridge
from inkecho.platform.ibus_owned import INTERFACE, PATH, SERVICE, Client, IBusBridge
from inkecho.platform.output_router import OutputRouter, OutputRouterError


async def probe_owned(*, bus_factory=MessageBus, verifier=None):
    """Return pinned Shell owner only for a fresh owned ready/blocked scope.

    This is target identity evidence, never a delivery receipt. No capability is
    consumed and no Commit/Begin is sent during detection.
    """
    bus = bus_factory()
    try:
        await asyncio.wait_for(bus.connect(), 1)
        client = Client(None)
        client._bus = bus

        async def owner():
            reply = await client._call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="GetNameOwner",
                    signature="s",
                    body=[SERVICE],
                ),
                "org.freedesktop.DBus",
            )
            if (
                reply.message_type != MessageType.METHOD_RETURN
                or reply.signature != "s"
                or len(reply.body) != 1
                or not isinstance(reply.body[0], str)
                or not reply.body[0].startswith(":")
            ):
                return None
            return reply.body[0]

        pinned = await owner()
        if pinned is None or not await (verifier or client._verify_shell_owner)(pinned):
            raise OutputRouterError("input_capability_unknown")
        reply = await client._call(
            Message(destination=pinned, path=PATH, interface=INTERFACE, member="Probe"),
            pinned,
        )
        if (
            reply.message_type != MessageType.METHOD_RETURN
            or reply.signature != "s"
            or reply.body not in (["ready"], ["blocked"], ["none"])
            or await owner() != pinned
        ):
            raise OutputRouterError("input_capability_unknown")
        return None if reply.body == ["none"] else ("ibus", pinned)
    except asyncio.CancelledError:
        raise
    except Exception:
        raise OutputRouterError("input_capability_unknown") from None
    finally:
        bus.disconnect()


class OwnedAutoOutputRouter(OutputRouter):
    """Explicit harness injection enables this candidate, default app unchanged.

    Explicit IBus mode still uses the original V2 bridge. Automatic selection
    happens inside output_session at first insert, never during recording.
    """

    def __init__(
        self,
        keyboard,
        *,
        owned_probe=probe_owned,
        owned_factory=IBusBridge,
        legacy_factory=LegacyIBusBridge,
        system_detector=detect_system_framework,
        **kwargs,
    ):
        super().__init__(keyboard, ibus_factory=legacy_factory, **kwargs)
        self._owned_probe = owned_probe
        self._owned_factory = owned_factory
        self._owned_auto_candidate = True

        async def detect():
            existing = await system_detector()
            return (
                existing if existing and existing[0] == "fcitx" else await owned_probe()
            )

        self._system_detector = detect

    async def _choose_auto(self, can_continue=lambda: True, deadline=None):
        legacy = self._ibus_factory
        self._ibus_factory = self._owned_factory
        try:
            result = await super()._choose_auto(can_continue, deadline)
            self._owned_auto_scope = self._kind == "ibus"
            return result
        finally:
            self._ibus_factory = legacy
