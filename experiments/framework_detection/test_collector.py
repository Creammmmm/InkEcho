import asyncio
from pathlib import Path
from types import SimpleNamespace

from collector import owner_identity
from dbus_next import MessageType


class FakeBus:
    def __init__(self):
        self.owners = [":1.7", ":1.7"]
        self.uid = 1000
        self.pid = 42

    async def call(self, message):
        if message.member == "GetNameOwner":
            value = self.owners.pop(0)
        elif message.member == "GetConnectionUnixUser":
            value = self.uid
        else:
            value = self.pid
        return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=[value])


def setup_proc(root):
    directory = root / "42"
    directory.mkdir()
    (directory / "exe").symlink_to("/usr/bin/ibus-daemon")


def test_ibus_owner_checked_and_rechecked(tmp_path):
    if not Path("/usr/bin/ibus-daemon").exists():
        return
    setup_proc(tmp_path)
    bus = FakeBus()
    assert (
        asyncio.run(
            owner_identity(
                bus,
                "org.freedesktop.IBus",
                uid=1000,
                proc_root=tmp_path,
                executable_owner=lambda _: 0,
            )
        )
        == "ibus"
    )


def test_owner_replacement_and_wrong_uid_fail_closed(tmp_path):
    if not Path("/usr/bin/ibus-daemon").exists():
        return
    setup_proc(tmp_path)
    bus = FakeBus()
    bus.owners = [":1.7", ":1.8"]
    assert (
        asyncio.run(
            owner_identity(
                bus,
                "org.freedesktop.IBus",
                uid=1000,
                proc_root=tmp_path,
                executable_owner=lambda _: 0,
            )
        )
        is None
    )
    bus = FakeBus()
    bus.uid = 1001
    assert (
        asyncio.run(
            owner_identity(
                bus,
                "org.freedesktop.IBus",
                uid=1000,
                proc_root=tmp_path,
                executable_owner=lambda _: 0,
            )
        )
        is None
    )


def test_unknown_executable_is_not_assumed_to_be_an_input_method(tmp_path):
    directory = tmp_path / "42"
    directory.mkdir()
    (directory / "exe").symlink_to("/usr/bin/true")
    assert (
        asyncio.run(
            owner_identity(
                FakeBus(),
                "org.freedesktop.IBus",
                uid=1000,
                proc_root=tmp_path,
                executable_owner=lambda _: 0,
            )
        )
        is None
    )
