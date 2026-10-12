"""Bounded, read-only AT-SPI metadata probe; no names, content or actions."""

import argparse
import asyncio
import collections
import json

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus

A = "org.a11y.atspi.Accessible"
ROOT = ("org.a11y.atspi.Registry", "/org/a11y/atspi/accessible/root")
DBUS = ("org.freedesktop.DBus", "/org/freedesktop/DBus")
PREFIX = "org.a11y.atspi."
NULL = "/org/a11y/atspi/null"


class MetadataError(Exception):
    def __init__(self, name: str) -> None:
        # Only the D-Bus protocol error name, never error body or message.
        self.name = name


async def call(
    bus: MessageBus,
    address: tuple[str, str],
    interface: str,
    member: str,
    signature: str = "",
    body: list | None = None,
) -> list:
    reply = await asyncio.wait_for(
        bus.call(
            Message(
                destination=address[0],
                path=address[1],
                interface=interface,
                member=member,
                signature=signature,
                body=body or [],
            )
        ),
        2,
    )
    if reply.message_type == MessageType.ERROR:
        raise MetadataError(reply.error_name)
    return reply.body


async def inspect_app(bus: MessageBus, root: tuple[str, str], app: dict) -> None:
    pending, seen, roles = [tuple(root)], set(), collections.Counter()
    while pending and len(seen) < 4096:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node)
        values, errors = {}, {}
        # Each failure is isolated. In particular, optional role
        # metadata never blocks state/interface/child inspection.
        for method in (
            "GetRoleName",
            "GetState",
            "GetInterfaces",
            "GetChildren",
        ):
            try:
                values[method] = (await call(bus, node, A, method))[0]
            except MetadataError as error:
                errors[method] = error.name
            except TimeoutError:
                errors[method] = "probe.timeout"
        role = values.get("GetRoleName")
        interfaces = values.get("GetInterfaces", [])
        states = values.get("GetState", [])
        children = values.get("GetChildren", [])
        if role is not None:
            roles[role] += 1
        text = PREFIX + "Text" in interfaces
        editable = PREFIX + "EditableText" in interfaces
        focused = bool(states and states[0] & (1 << 12))
        app["text_interfaces"] += text
        app["editable_text_interfaces"] += editable
        if text or editable or focused:
            if len(app["controls"]) < 64:
                app["controls"].append(
                    {
                        "role": role,
                        "interfaces": [x.removeprefix(PREFIX) for x in interfaces],
                        "state_words": states,
                        "active": bool(states and states[0] & (1 << 1)),
                        "child_count": len(children),
                        "null_children": sum(child[1] == NULL for child in children),
                        "focused": focused,
                        "editable_state": bool(states and states[0] & (1 << 7)),
                    }
                )
        if errors:
            app["incomplete_nodes"].append(
                {
                    "index": len(seen),
                    "null_reference": node[1] == NULL,
                    "empty_bus_name": not node[0],
                    "successful_methods": list(values),
                    "errors": errors,
                    "child_count": len(children),
                    "state_words": states,
                    "interfaces": [x.removeprefix(PREFIX) for x in interfaces],
                }
            )
        pending.extend(tuple(child) for child in children)
    app["nodes"] = len(seen)
    app["roles"] = dict(roles)
    app["complete"] = not pending and not app["incomplete_nodes"]


async def main(target_pid: int) -> None:
    session = bus = None
    report = {
        "requested_pid": target_pid,
        "read_only": True,
        "content_read": False,
        "focus_changed": False,
        "apps": [],
        "registry_errors": [],
        "complete": False,
    }
    try:
        async with asyncio.timeout(40):
            session = await MessageBus().connect()
            address = await call(
                session, ("org.a11y.Bus", "/org/a11y/bus"), "org.a11y.Bus", "GetAddress"
            )
            bus = await MessageBus(bus_address=address[0]).connect()
            roots = (await call(bus, ROOT, A, "GetChildren"))[0]
            report["registry_app_count"] = len(roots)
            for root in roots:
                try:
                    pid = (
                        await call(
                            bus,
                            DBUS,
                            "org.freedesktop.DBus",
                            "GetConnectionUnixProcessID",
                            "s",
                            [root[0]],
                        )
                    )[0]
                    if pid != target_pid:
                        continue
                    app = {
                        "pid": pid,
                        "nodes": 0,
                        "roles": {},
                        "text_interfaces": 0,
                        "editable_text_interfaces": 0,
                        "controls": [],
                        "incomplete_nodes": [],
                        "complete": False,
                    }
                    report["apps"].append(app)
                    await inspect_app(bus, tuple(root), app)
                except MetadataError as error:
                    report["registry_errors"].append(error.name)
                except (TimeoutError, OSError) as error:
                    report["registry_errors"].append(type(error).__name__)
            report["complete"] = True
    except MetadataError as error:
        report["registry_errors"].append(error.name)
    except (TimeoutError, OSError) as error:
        report["registry_errors"].append(type(error).__name__)
    finally:
        if bus:
            bus.disconnect()
        if session:
            session.disconnect()
        print(json.dumps(report, ensure_ascii=False))


def positive_pid(value: str) -> int:
    pid = int(value)
    if pid <= 0:
        raise argparse.ArgumentTypeError("PID must be positive")
    return pid


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=positive_pid, required=True)
    asyncio.run(main(parser.parse_args().pid))
