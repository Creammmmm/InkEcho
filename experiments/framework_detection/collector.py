"""Read-only framework owner probe, independent of the application.

Session configuration and service identity are system-level clues only; they do
not identify which input module the current widget uses. This prototype does
not connect a bridge, query focus, read surrounding text or produce input.
"""

import asyncio
import os
from pathlib import Path

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus

BUS = "org.freedesktop.DBus"
PATH = "/org/freedesktop/DBus"
KNOWN = {"ibus": "/usr/bin/ibus-daemon", "fcitx": "/usr/bin/fcitx5"}


async def owner_identity(
    bus, name, *, uid=None, proc_root=Path("/proc"), executable_owner=None
):
    """Pin and recheck a unique bus owner; return its recognized framework."""
    if uid is None:
        uid = os.getuid()
    if executable_owner is None:

        def executable_owner(path):
            return path.stat().st_uid

    async def call(member, value):
        reply = await asyncio.wait_for(
            bus.call(
                Message(
                    destination=BUS,
                    path=PATH,
                    interface=BUS,
                    member=member,
                    signature="s",
                    body=[value],
                )
            ),
            2,
        )
        if reply.message_type != MessageType.METHOD_RETURN or len(reply.body) != 1:
            raise ValueError("unavailable")
        return reply.body[0]

    try:
        owner = await call("GetNameOwner", name)
        if not isinstance(owner, str) or not owner.startswith(":"):
            return None
        actual_uid = await call("GetConnectionUnixUser", owner)
        pid = await call("GetConnectionUnixProcessID", owner)
        if (
            type(actual_uid) is not int
            or actual_uid != uid
            or type(pid) is not int
            or pid <= 0
        ):
            return None
        executable = (proc_root / str(pid) / "exe").resolve(strict=True)
        if executable_owner(executable) != 0:
            return None
        kind = next(
            (key for key, value in KNOWN.items() if str(executable) == value), None
        )
        if kind is None or await call("GetNameOwner", name) != owner:
            return None
        return kind
    except (TimeoutError, OSError, ValueError):
        return None


async def probe():
    bus = await MessageBus().connect()
    try:
        return {
            "ibus_service_owner": await owner_identity(bus, "org.freedesktop.IBus"),
            "fcitx_service_owner": await owner_identity(bus, "org.fcitx.Fcitx5"),
        }
    finally:
        bus.disconnect()
