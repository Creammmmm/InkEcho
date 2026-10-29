"""Disposable guest: actual router and owned GTK widgets, never user text."""

import asyncio
import json
import os
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from inkecho.platform.output_router import OutputRouter  # noqa: E402


class Keyboard:
    authorized = False

    def __init__(self):
        self.writes = []

    async def connect(self):
        pass

    async def authorize(self, parent_window=""):
        self.authorized = True

    async def aclose(self):
        pass

    async def insert(self, text, active, **kwargs):
        self.writes.append(text)
        raise RuntimeError("unexpected keyboard fallback")


async def pump(seconds):
    end = asyncio.get_running_loop().time() + seconds
    while asyncio.get_running_loop().time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        await asyncio.sleep(0.01)


async def main():
    windows = []
    for title in ("InkEcho automatic A", "InkEcho automatic B"):
        window = Gtk.Window(title=title)
        entry = Gtk.Entry()
        window.add(entry)
        window.show_all()
        windows.append((window, entry))
    await pump(0.5)

    def activate(pair):
        window, entry = pair
        window.present()
        entry.grab_focus()
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

    activate(windows[0])
    await pump(1.5)
    assert windows[0][0].is_active() and windows[0][1].has_focus()
    from inkecho.platform.framework_detection import detect_system_framework

    print("probe", await detect_system_framework(), flush=True)
    keyboard = Keyboard()
    router = OutputRouter(keyboard)
    await router.prepare_task("auto")
    async with router.output_session():
        first = await router.insert("甲", lambda: True)
        selected = router.selected
        await pump(0.5)
        activate(windows[1])
        await pump(1)
        assert windows[1][0].is_active() and windows[1][1].has_focus()
        second = await router.insert("乙", lambda: True)
        await pump(0.5)
    result = {
        "selected": selected,
        "counts": [first, second],
        "a": windows[0][1].get_text(),
        "b": windows[1][1].get_text(),
        "keyboard_writes": keyboard.writes,
    }
    print(json.dumps(result, ensure_ascii=False), flush=True)
    assert result == {
        "selected": "fcitx",
        "counts": [1, 1],
        "a": "甲",
        "b": "乙",
        "keyboard_writes": [],
    }
    for window, _ in windows:
        window.destroy()


asyncio.run(main())
