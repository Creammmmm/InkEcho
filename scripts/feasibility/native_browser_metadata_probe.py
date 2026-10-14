#!/usr/bin/env python3
"""Read-only interface discovery in owned native Wayland Chrome inputs; no typing."""

import argparse
import asyncio
import json
import subprocess
import time
from pathlib import Path

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus
from owned_wayland_browser_fixture import OwnedWaylandBrowser

ACCESSIBLE = "org.a11y.atspi.Accessible"
ROOT = ("org.a11y.atspi.Registry", "/org/a11y/atspi/accessible/root")
DBUS = ("org.freedesktop.DBus", "/org/freedesktop/DBus")


async def call(bus, address, interface, member, signature="", body=None):
    async with asyncio.timeout(2):
        reply = await bus.call(
            Message(
                destination=address[0],
                path=address[1],
                interface=interface,
                member=member,
                signature=signature,
                body=body or [],
            )
        )
    if reply.message_type == MessageType.ERROR:
        raise RuntimeError("Owned accessibility query failed")
    return reply.body


def state_enabled(words, index):
    return len(words) > index // 32 and bool(words[index // 32] & (1 << (index % 32)))


async def inspect_owned(bus, pid):
    applications = (await call(bus, ROOT, ACCESSIBLE, "GetChildren"))[0]
    owned = []
    for address in applications:
        try:
            actual = (
                await call(
                    bus, DBUS, DBUS[0], "GetConnectionUnixProcessID", "s", [address[0]]
                )
            )[0]
        except RuntimeError:
            continue
        if actual == pid:
            owned.append(tuple(address))
    if not owned:
        return None
    pending = list(owned)
    seen = set()
    nodes = []
    null_children = 0
    while pending:
        address = pending.pop()
        if address in seen:
            continue
        seen.add(address)
        if len(seen) > 1000:
            raise RuntimeError("Owned accessibility tree exceeded bound")
        if address[1].endswith("/null"):
            null_children += 1
            continue
        # Descendants must stay on the verified owned application's connection.
        if address[0] not in {root[0] for root in owned}:
            raise RuntimeError("Owned tree escaped its verified D-Bus connection")
        try:
            interfaces = (await call(bus, address, ACCESSIBLE, "GetInterfaces"))[0]
            role = (await call(bus, address, ACCESSIBLE, "GetRoleName"))[0]
            state = (await call(bus, address, ACCESSIBLE, "GetState"))[0]
            children = (await call(bus, address, ACCESSIBLE, "GetChildren"))[0]
        except RuntimeError:
            nodes.append({"query_failed": True})
            continue
        nodes.append(
            {
                "role": role,
                "interfaces": interfaces,
                "focused": state_enabled(state, 12),
                "editable_state": state_enabled(state, 7),
                "active": state_enabled(state, 1),
            }
        )
        pending.extend(tuple(child) for child in children)
    return {
        "owned_application_count": len(owned),
        "nodes": nodes,
        "null_children": null_children,
        "text_interfaces": sum(
            "org.a11y.atspi.Text" in n.get("interfaces", []) for n in nodes
        ),
        "editable_text_interfaces": sum(
            "org.a11y.atspi.EditableText" in n.get("interfaces", []) for n in nodes
        ),
    }


async def run(field):
    session = await MessageBus().connect()
    bus = None
    try:
        address = (
            await call(
                session,
                ("org.a11y.Bus", "/org/a11y/bus"),
                "org.a11y.Bus",
                "GetAddress",
            )
        )[0]
        bus = await MessageBus(bus_address=address).connect()
        with OwnedWaylandBrowser(field) as fixture:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                snapshot = fixture.snapshot()
                if fixture.process.poll() is not None:
                    raise RuntimeError("Owned Chrome exited before page readiness")
                if snapshot is not None:
                    break
                await asyncio.sleep(0.1)
            else:
                raise RuntimeError(
                    "Owned page did not report readiness: "
                    + json.dumps(
                        {"http": fixture.requests, "native": fixture.native_evidence()}
                    )
                )
            evidence = fixture.native_evidence()
            if not all(
                value is True
                for key, value in evidence.items()
                if key != "ozone_platform"
            ):
                raise RuntimeError("Native Wayland client evidence incomplete")
            metadata = None
            async with asyncio.timeout(12):
                for _ in range(20):
                    metadata = await inspect_owned(bus, fixture.process.pid)
                    if metadata is not None:
                        break
                    await asyncio.sleep(0.2)
            latest = fixture.snapshot()
            if latest["text"] != "" or snapshot["text"] != "":
                raise RuntimeError("Read-only fixture was not empty")
            return {
                "field": field,
                "owned_pid": fixture.process.pid,
                "native_evidence": evidence,
                "document_focused": latest["document_focused"],
                "field_focused": latest["field_focused"],
                "empty_before_and_after": True,
                "atspi": metadata,
                "keys_sent": 0,
                "insertion_called": False,
                "user_page_accessed": False,
                "clipboard_used": False,
            }
    finally:
        if bus is not None:
            bus.disconnect()
        session.disconnect()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    version = subprocess.check_output(["google-chrome", "--version"], text=True).strip()
    result = {"browser_version": version, "fixtures": []}
    for field in ("textarea", "contenteditable"):
        result["fixtures"].append(asyncio.run(run(field)))
    result["owned_fixtures_cleaned"] = True
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "browser_version": version,
                "owned_fixtures_cleaned": True,
                "fixtures": [
                    {
                        "field": item["field"],
                        "native_evidence": item["native_evidence"],
                        "document_focused": item["document_focused"],
                        "field_focused": item["field_focused"],
                        "nodes": len(item["atspi"]["nodes"]) if item["atspi"] else 0,
                        "editable_text_interfaces": item["atspi"][
                            "editable_text_interfaces"
                        ]
                        if item["atspi"]
                        else None,
                        "keys_sent": 0,
                    }
                    for item in result["fixtures"]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
