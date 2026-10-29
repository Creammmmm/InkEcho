"""Disposable GNOME guest only: own GTK text view, never invokes a shell."""

import asyncio
import json
import os
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from client import CandidateError, Capability, Client  # noqa: E402
from gi.repository import Gtk  # noqa: E402


async def pump(seconds):
    end = asyncio.get_running_loop().time() + seconds
    while asyncio.get_running_loop().time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        await asyncio.sleep(0.01)


async def main():
    window = Gtk.Window(title="InkEcho owned boundary trial")
    view = Gtk.TextView()
    window.add(view)
    window.show_all()
    await pump(0.5)
    window.present()
    view.grab_focus()
    if os.environ.get("GDK_BACKEND") == "x11":
        gi.require_version("GdkX11", "3.0")
        from gi.repository import GdkX11

        subprocess.run(
            [
                "xdotool",
                "windowactivate",
                str(GdkX11.X11Window.get_xid(window.get_window())),
            ],
            check=True,
        )
    await pump(2)
    if not window.is_active() or not view.has_focus():
        raise RuntimeError("owned text view did not obtain focus")
    cap = Capability(os.environ["XDG_RUNTIME_DIR"])
    client = Client(cap)
    await client.begin()
    result = {}
    for name, text in (("newline", "甲\n乙"), ("tab", "甲\t乙")):
        try:
            await client.insert(text, lambda: True)
            result[name] = "accepted"
        except CandidateError as error:
            result[name] = error.code
    buffer = view.get_buffer()
    start, end = buffer.get_bounds()
    result["visible_after_controls"] = buffer.get_text(start, end, False)
    # Close the only owned window. This proves only that no owned window is
    # focused, not that no other desktop component has an input context.
    window.destroy()
    await pump(1)
    try:
        result["no_owned_window"] = await client.insert("丙", lambda: True)
    except CandidateError as error:
        result["no_owned_window"] = error.code
    await client.close()
    result["capability_removed"] = not cap.path.exists()
    print(json.dumps(result, ensure_ascii=False), flush=True)


asyncio.run(main())
