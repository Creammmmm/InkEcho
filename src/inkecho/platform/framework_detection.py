"""Conservative, read-only system input-framework detection.

Session configuration and service identity are system-level clues only; they do
not identify which input module the current widget uses. Bridge handshake is
performed separately by the output router.
"""

import ast
import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus

BUS = "org.freedesktop.DBus"
PATH = "/org/freedesktop/DBus"
KNOWN = {"ibus": "/usr/bin/ibus-daemon", "fcitx": "/usr/bin/fcitx5"}


async def owner_identity(
    bus,
    name,
    *,
    uid=None,
    proc_root=Path("/proc"),
    executable_owner=None,
    include_owner=False,
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
        if (
            reply.sender != BUS
            or reply.message_type != MessageType.METHOD_RETURN
            or len(reply.body) != 1
        ):
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
        return (kind, owner) if include_owner else kind
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


@dataclass(frozen=True)
class Evidence:
    # Values read from the actual graphical session, not the caller's guesses.
    xmodifiers: str | None
    gtk: str | None
    qt: str | None
    # Verified unique-owner process identity for the framework's live service.
    fcitx_owner: bool | None
    ibus_owner: bool | None
    # Authenticated bridge handshake, performed without sending text.
    fcitx_bridge: bool | None
    ibus_bridge: bool | None
    # GNOME settings readable and syntactically valid; NOT the stale current key.
    source_configuration_readable: bool


def choose(evidence: Evidence) -> str | None:
    if not evidence.source_configuration_readable:
        return None
    x = (evidence.xmodifiers or "").lower()
    gtk = (evidence.gtk or "").lower()
    qt = (evidence.qt or "").lower()
    # Explicit XIM, GTK and Qt overrides such as simple/xim/wayland do not prove
    # agreement. Require XMODIFIERS plus at least one matching toolkit hint.
    if x not in ("@im=fcitx", "@im=ibus"):
        return None
    selected = x.removeprefix("@im=")
    if gtk not in ("", selected) or qt not in ("", selected):
        return None
    if selected not in (gtk, qt):
        return None
    if selected == "fcitx":
        return (
            "fcitx"
            if evidence.fcitx_owner is True and evidence.fcitx_bridge is True
            else None
        )
    return (
        "ibus" if evidence.ibus_owner is True and evidence.ibus_bridge is True else None
    )


async def _command(*arguments):
    env = os.environ.copy()
    for key in ("LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH"):
        env.pop(key, None)
    env["LC_ALL"] = "C"
    process = await asyncio.create_subprocess_exec(
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=env,
    )
    try:
        data, _ = await asyncio.wait_for(process.communicate(), 2)
        if process.returncode or len(data) > 1024 * 1024:
            raise ValueError("unavailable")
        return data.decode("utf8")
    except BaseException:
        if process.returncode is None:
            process.kill()
            await process.wait()
        raise


async def collect_system_framework():
    """Collect a system hypothesis; this does not identify the active widget."""
    bus = None
    try:
        environment = await _command("/usr/bin/systemctl", "--user", "show-environment")
        values = {}
        for line in environment.splitlines():
            key, separator, value = line.partition("=")
            if separator and key in {"XMODIFIERS", "GTK_IM_MODULE", "QT_IM_MODULE"}:
                values[key] = value
        sources = await _command(
            "/usr/bin/gsettings", "get", "org.gnome.desktop.input-sources", "sources"
        )
        # GNOME emits a typed empty list when Fcitx owns the session.
        source_text = sources.strip()
        if source_text == "@a(ss) []":
            source_text = "[]"
        entries = ast.literal_eval(source_text)
        readable = isinstance(entries, list) and all(
            isinstance(item, tuple)
            and len(item) == 2
            and all(isinstance(part, str) and part for part in item)
            for item in entries
        )
        bus = await asyncio.wait_for(MessageBus().connect(), 2)
        ibus = await owner_identity(bus, "org.freedesktop.IBus", include_owner=True)
        fcitx = await owner_identity(bus, "org.fcitx.Fcitx5", include_owner=True)
        selected = choose(
            Evidence(
                values.get("XMODIFIERS"),
                values.get("GTK_IM_MODULE"),
                values.get("QT_IM_MODULE"),
                fcitx is not None and fcitx[0] == "fcitx",
                ibus is not None and ibus[0] == "ibus",
                True,
                True,
                readable,
            )
        )
        if selected == "fcitx":
            return selected, fcitx[1]
        if selected == "ibus":
            return selected, ibus[1]
        return None
    except Exception:
        return None
    finally:
        if bus is not None:
            bus.disconnect()


async def detect_system_framework():
    """IBus remains disabled until its focused target can be confirmed."""
    result = await collect_system_framework()
    if result is None or result[0] != "fcitx":
        return None
    # A disabled add-on may remain loaded in Fcitx until that daemon exits.
    # Check the user's published configuration before choosing it for a new
    # task, without interrupting a task already sending through the bridge.
    from inkecho.platform.fcitx5_install import FcitxInstaller

    version = await asyncio.to_thread(FcitxInstaller().auto_version)
    if version is None:
        return None
    return result if await _live_fcitx_version_matches(result[1], version) else None


async def _live_fcitx_version_matches(owner: str, expected: str) -> bool:
    """Query the pinned owner and recheck its verified identity before output."""
    bus = None
    try:
        bus = await asyncio.wait_for(MessageBus().connect(), 1)
        addons = await asyncio.wait_for(
            bus.call(
                Message(
                    destination=owner,
                    path="/controller",
                    interface="org.fcitx.Fcitx.Controller1",
                    member="GetAddonsV2",
                )
            ),
            1,
        )
        if (
            addons.message_type != MessageType.METHOD_RETURN
            or addons.sender != owner
            or addons.signature != "a(sssibbbasas)"
            or len(addons.body) != 1
            or not isinstance(addons.body[0], list)
        ):
            return False
        matches = [
            entry
            for entry in addons.body[0]
            if isinstance(entry, (list, tuple)) and entry and entry[0] == "inkecho"
        ]
        if (
            len(matches) != 1
            or len(matches[0]) != 9
            or type(matches[0][5]) is not bool
            or matches[0][5] is not True
        ):
            return False
        reply = await asyncio.wait_for(
            bus.call(
                Message(
                    destination=owner,
                    path="/inkecho",
                    interface="org.fcitx.Fcitx.InkEcho1",
                    member="RuntimeVersion",
                )
            ),
            1,
        )
        if (
            reply.message_type != MessageType.METHOD_RETURN
            or reply.sender != owner
            or reply.signature != "s"
            or reply.body != [expected]
        ):
            return False
        return await owner_identity(bus, "org.fcitx.Fcitx5", include_owner=True) == (
            "fcitx",
            owner,
        )
    except Exception:
        return False
    finally:
        if bus is not None:
            bus.disconnect()


async def verified_explicit_fcitx_owner() -> str | None:
    """Verify a manually selected bridge without relying on session hints."""
    from inkecho.platform.fcitx5_install import FcitxInstaller

    version = await asyncio.to_thread(FcitxInstaller().auto_version)
    if version is None:
        return None
    bus = None
    try:
        bus = await asyncio.wait_for(MessageBus().connect(), 1)
        identity = await owner_identity(bus, "org.fcitx.Fcitx5", include_owner=True)
        if identity is None or identity[0] != "fcitx":
            return None
        owner = identity[1]
        return owner if await _live_fcitx_version_matches(owner, version) else None
    except Exception:
        return None
    finally:
        if bus is not None:
            bus.disconnect()
