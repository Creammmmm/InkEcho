"""Disposable guest only: owned windows, synthetic text, no surrounding reads."""

import asyncio
import json
import os
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("IBus", "1.0")
from client import INTERFACE, PATH, CandidateError, Client  # noqa: E402
from dbus_next import Message, MessageType  # noqa: E402
from dbus_next.aio import MessageBus  # noqa: E402
from gi.repository import Gtk, IBus  # noqa: E402
from lifecycle import Capability  # noqa: E402

IBus.init()
ibus = IBus.Bus.new()
assert ibus.is_connected()


def engine():
    desc = ibus.get_global_engine()
    return desc.get_name() if desc else None


async def pump(seconds):
    loop = asyncio.get_running_loop()
    end = loop.time() + seconds
    while loop.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        await asyncio.sleep(0.01)


def activate(window, entry):
    window.present()
    entry.grab_focus()
    if os.environ.get("GDK_BACKEND") == "x11":
        gi.require_version("GdkX11", "3.0")
        from gi.repository import GdkX11

        xid = GdkX11.X11Window.get_xid(window.get_window())
        subprocess.run(["xdotool", "windowactivate", str(xid)], check=True)


async def run():
    initial = engine()
    windows = []
    for title in ("InkEcho owned A", "InkEcho owned B"):
        window = Gtk.Window(title=title)
        window.set_default_size(350, 110)
        entry = Gtk.Entry()
        window.add(entry)
        window.show_all()
        windows.append((window, entry))
    a, b = windows
    await pump(0.5)  # Let the X11 window manager map the owned windows.
    activate(*a)
    await pump(1.5)
    assert a[0].is_active() and a[1].has_focus(), "first window not active"
    cap = Capability(os.environ["XDG_RUNTIME_DIR"])
    client = Client(cap)
    await client.begin()
    await client.insert("甲", lambda: True)
    await pump(0.5)
    assert a[1].get_text() == "甲"
    # A different unique sender cannot use the known token or sequence.
    foreign = await MessageBus().connect()
    denied = await foreign.call(
        Message(
            destination=client._owner,
            path=PATH,
            interface=INTERFACE,
            member="Commit",
            signature="us",
            body=[1, "丙"],
        )
    )
    assert denied.message_type == MessageType.METHOD_RETURN and denied.body == [
        "rejected"
    ]
    foreign.disconnect()
    activate(*b)
    await pump(1)
    assert b[0].is_active() and b[1].has_focus(), "second window not active"
    await client.insert("乙", lambda: True)
    await pump(0.5)
    assert b[1].get_text() == "乙"
    await client.cancel()
    try:
        await client.insert("丙", lambda: True)
        raise AssertionError("cancelled client sent")
    except CandidateError as error:
        assert error.code == "not_ready"
    await pump(0.5)
    assert b[1].get_text() == "乙"
    await client.close()
    assert not (Path(os.environ["XDG_RUNTIME_DIR"]) / cap.name).exists()
    await pump(0.4)
    # Hold a real Commit reply after server processing; cancellation must prevent
    # a second character even when a previously dispatched character is visible.
    cap2 = Capability(os.environ["XDG_RUNTIME_DIR"])
    client2 = Client(cap2)
    await client2.begin()
    original_request = client2._request
    processed, release = asyncio.Event(), asyncio.Event()

    async def held_request(method, signature, body):
        reply = await original_request(method, signature, body)
        if method == "Commit":
            processed.set()
            await release.wait()
        return reply

    client2._request = held_request
    pending = asyncio.create_task(client2.insert("丙甲", lambda: True))
    await asyncio.wait_for(processed.wait(), 2)
    await client2.cancel()
    release.set()
    try:
        await pending
        raise AssertionError("cancelled send continued")
    except CandidateError as error:
        assert error.code == "cancelled"
    await pump(0.5)
    assert b[1].get_text() == "乙丙"
    await client2.close()
    assert not (Path(os.environ["XDG_RUNTIME_DIR"]) / cap2.name).exists()
    assert engine() == initial
    print(
        json.dumps(
            {
                "engine_before": initial,
                "engine_after": engine(),
                "a": a[1].get_text(),
                "b": b[1].get_text(),
                "different_sender": "rejected",
                "cancel_before_next": "stopped",
                "cancel_after_server_process_reply_held": "no_second_send",
                "backend": os.environ.get("GDK_BACKEND"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    for window, _entry in windows:
        window.destroy()
    await pump(0.2)


asyncio.run(run())
