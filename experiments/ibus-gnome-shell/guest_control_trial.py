import asyncio
import json
import os
import subprocess

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from client import CandidateError, Capability, Client  # noqa: E402
from gi.repository import GLib, Gtk, Vte  # noqa: E402


async def pump(n):
    end = asyncio.get_running_loop().time() + n
    while asyncio.get_running_loop().time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        await asyncio.sleep(0.01)


def activate(window):
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


async def send(value):
    cap = Capability(os.environ["XDG_RUNTIME_DIR"])
    c = Client(cap)
    try:
        await c.begin()
        try:
            return ["returned", await c.insert(value, lambda: True)]
        except CandidateError as e:
            return ["error", e.code]
    finally:
        await c.close()


async def main():
    out = {}
    w = Gtk.Window(title="InkEcho owned text trial")
    view = Gtk.TextView()
    w.add(view)
    w.show_all()
    await pump(0.5)
    w.present()
    view.grab_focus()
    activate(w)
    await pump(2)
    if not w.is_active() or not view.has_focus():
        raise RuntimeError("editor not focused")
    out["editor_send"] = await send("甲\n乙\t丙")
    await pump(1)
    b = view.get_buffer()
    out["editor_text"] = b.get_text(*b.get_bounds(), False)
    w.destroy()
    await pump(0.3)
    w = Gtk.Window(title="InkEcho owned terminal trial")
    term = Vte.Terminal()
    w.add(term)
    w.show_all()
    await pump(0.5)
    w.present()
    term.grab_focus()
    activate(w)
    code = 'import runpy; runpy.run_path("/tmp/inkecho-ibus-lf-trial/reader.py")'
    term.spawn_async(
        Vte.PtyFlags.DEFAULT,
        None,
        ["/usr/bin/python3", "-c", code],
        None,
        GLib.SpawnFlags.DEFAULT,
        None,
        None,
        -1,
        None,
        None,
        None,
    )
    await pump(2)
    if not w.is_active() or not term.has_focus():
        raise RuntimeError("terminal not focused")
    out["terminal_send"] = await send("甲\n乙\t丙")
    await pump(1)
    try:
        out["terminal_bytes"] = open("/tmp/inkecho-ibus-lf-received", "rb").read().hex()
    except FileNotFoundError:
        out["terminal_bytes"] = "not-read"
    w.destroy()
    print(json.dumps(out, ensure_ascii=False), flush=True)


asyncio.run(main())
