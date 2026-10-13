#!/usr/bin/env python3
"""Keyboard-only portal Unicode test, exclusively in an owned blank GTK editor.

Normal portal consent occurs before the fixture is opened. No persistence,
clipboard, screen sharing, user document inspection, or input-method registration.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus

from inkecho.platform.accessibility import AccessibilityInput, InputUnavailable

DEST = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
IFACE = "org.freedesktop.portal.RemoteDesktop"
SAMPLE = "你好 InkEcho，世界！ café Ω 😀\n第二行。"


async def probe():
    if os.environ.get("XDG_SESSION_TYPE") != "wayland":
        raise RuntimeError("Native Wayland required")
    bus = await MessageBus().connect()
    session = None
    pending = {}
    pressed = set()
    fixture = None
    access = AccessibilityInput()

    async def call(path, interface, member, signature="", body=None):
        reply = await asyncio.wait_for(
            bus.call(
                Message(
                    destination=DEST,
                    path=path,
                    interface=interface,
                    member=member,
                    signature=signature,
                    body=body or [],
                )
            ),
            3,
        )
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(reply.error_name)
        return reply.body

    def response(message):
        if (
            message.message_type == MessageType.SIGNAL
            and message.interface == "org.freedesktop.portal.Request"
            and message.member == "Response"
        ):
            future = pending.get(message.path)
            if future is not None and not future.done():
                future.set_result(message.body)

    async def request(method, signature, arguments, options):
        token = "inkecho_" + uuid.uuid4().hex
        sender = bus.unique_name[1:].replace(".", "_")
        path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        future = asyncio.get_running_loop().create_future()
        pending[path] = future
        options["handle_token"] = Variant("s", token)
        try:
            result = await call(PATH, IFACE, method, signature, [*arguments, options])
            if result != [path]:
                raise RuntimeError("Unexpected request path")
            code, values = await asyncio.wait_for(future, 60)
            if code:
                raise RuntimeError(f"portal_response_{code}")
            return values
        finally:
            pending.pop(path, None)
            if not future.done() or future.cancelled():
                try:
                    await call(path, "org.freedesktop.portal.Request", "Close")
                except RuntimeError:
                    pass

    async def key(keysym, state):
        await call(
            PATH,
            IFACE,
            "NotifyKeyboardKeysym",
            "oa{sv}iu",
            [session, {}, keysym, state],
        )

    try:
        bus.add_message_handler(response)
        reply = await bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="AddMatch",
                signature="s",
                body=[
                    "type='signal',interface='org.freedesktop.portal.Request',member='Response'"
                ],
            )
        )
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError("Signal subscription failed")
        values = await request(
            "CreateSession",
            "a{sv}",
            [],
            {"session_handle_token": Variant("s", "inkecho_" + uuid.uuid4().hex)},
        )
        session = values["session_handle"].value
        await request(
            "SelectDevices",
            "oa{sv}",
            [session],
            {"types": Variant("u", 1), "persist_mode": Variant("u", 0)},
        )
        print(json.dumps({"waiting_for_standard_keyboard_consent": True}), flush=True)
        values = await request("Start", "osa{sv}", [session, ""], {})
        if values.get("devices", Variant("u", 0)).value != 1:
            raise RuntimeError("Keyboard-only grant required")
        print(json.dumps({"keyboard_only_granted": True}), flush=True)
        with tempfile.TemporaryDirectory(prefix="inkecho-portal-unicode-") as temporary:
            received = Path(temporary) / "received.json"
            fixture = subprocess.Popen(
                [
                    "/usr/bin/python3",
                    str(Path(__file__).with_name("wayland_editor_fixture.py")),
                    str(received),
                ],
                env=dict(os.environ, GDK_BACKEND="wayland"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            await access.connect()
            target = None
            for _ in range(50):
                try:
                    candidate = await access.capture_target()
                    if candidate.process_id == fixture.pid:
                        target = candidate
                        break
                except InputUnavailable:
                    pass
                await asyncio.sleep(0.1)
            if (
                target is None
                or not received.exists()
                or json.loads(received.read_text()) != ""
            ):
                raise RuntimeError("Owned empty fixture not active")
            # Test-only ownership/focus guard. Product semantics use output-time
            # focus; this guard confines diagnostic text to the owned fixture.
            for char in SAMPLE:
                candidate = await access.capture_target()
                if candidate.process_id != fixture.pid:
                    raise RuntimeError("Owned fixture lost focus")
                keysym = 0xFF0D if char == "\n" else ord(char)
                if keysym > 255 and char != "\n":
                    keysym |= 0x01000000
                pressed.add(keysym)
                try:
                    await key(keysym, 1)
                finally:
                    await key(keysym, 0)
                    pressed.discard(keysym)
                await asyncio.sleep(0.04)
            await asyncio.sleep(0.3)
            actual = json.loads(received.read_text())
            print(
                json.dumps(
                    {
                        "exact_unicode": actual == SAMPLE,
                        "expected_codepoints": len(SAMPLE),
                        "received_codepoints": len(actual),
                        "fixture_received": actual,
                        "fixture_codepoints": [f"U+{ord(char):04X}" for char in actual],
                        "native_wayland": True,
                        "clipboard_used": False,
                    }
                ),
                flush=True,
            )
            if actual != SAMPLE:
                raise RuntimeError("Owned fixture Unicode mismatch")
    finally:
        for keysym in pressed:
            try:
                await key(keysym, 0)
            except Exception:
                pass
        if session:
            try:
                await call(session, "org.freedesktop.portal.Session", "Close")
            except Exception:
                pass
        access.close()
        bus.disconnect()
        if fixture is not None:
            fixture.terminate()
            try:
                fixture.wait(timeout=3)
            except subprocess.TimeoutExpired:
                fixture.kill()
                fixture.wait()


if __name__ == "__main__":
    try:
        asyncio.run(probe())
    except Exception as error:
        print(
            json.dumps(
                {
                    "failed": type(error).__name__,
                    "reason": str(error)
                    if isinstance(error, RuntimeError)
                    else "probe_failed",
                }
            ),
            flush=True,
        )
        sys.exit(1)
