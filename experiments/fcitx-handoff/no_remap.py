"""Disposable X11 guest: existing keyboard layout only, fixed synthetic input."""

import asyncio
import ctypes
import hashlib
import json
import os
import subprocess
from pathlib import Path

from inkecho.platform.fcitx5 import Fcitx5Bridge, FcitxOutputError

ROOT = Path("/tmp/handoff-r7")


async def main():
    actors = []
    try:
        for name, module in [("fcitx", "fcitx"), ("simple", "gtk-im-context-simple")]:
            path = ROOT / name
            path.unlink(missing_ok=True)
            env = dict(os.environ, GTK_IM_MODULE=module)
            for key in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH"):
                env.pop(key, None)
            actors.append(
                subprocess.Popen(
                    ["/usr/bin/python3", str(ROOT / "target.py"), name, str(path)],
                    env=env,
                )
            )
        await asyncio.sleep(3)

        async def focus(i, name):
            ids = subprocess.check_output(
                [
                    "xdotool",
                    "search",
                    "--pid",
                    str(actors[i].pid),
                    "--onlyvisible",
                    "--name",
                    "^InkEcho isolated " + name + "$",
                ],
                text=True,
            ).splitlines()
            xid = ids[-1]
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", xid], check=True, timeout=5
            )
            await asyncio.sleep(0.5)
            assert (
                subprocess.check_output(
                    ["xdotool", "getactivewindow"], text=True
                ).strip()
                == xid
            )

        x = ctypes.CDLL("libX11.so.6")
        t = ctypes.CDLL("libXtst.so.6")
        p = ctypes.c_void_p
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XOpenDisplay.restype = p
        x.XKeysymToKeycode.argtypes = [p, ctypes.c_ulong]
        x.XKeysymToKeycode.restype = ctypes.c_ubyte
        x.XSync.argtypes = [p, ctypes.c_int]
        x.XCloseDisplay.argtypes = [p]
        t.XTestFakeKeyEvent.argtypes = [p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        display = x.XOpenDisplay(None)
        assert display

        def keymap():
            return hashlib.sha256(
                subprocess.check_output(["xmodmap", "-pke"])
            ).hexdigest()

        before = keymap()
        await focus(0, "fcitx")
        bridge = Fcitx5Bridge()
        await bridge.connect()
        assert await bridge.insert("甲", lambda: True) == 1
        await focus(1, "simple")
        try:
            await bridge.insert(
                "中", lambda: True, deadline=__import__("time").monotonic() + 0.7
            )
            status = "unexpected_success"
        except FcitxOutputError as error:
            status = error.code
        ascii_code = x.XKeysymToKeycode(display, ord("b"))
        chinese_code = x.XKeysymToKeycode(display, 0x01000000 | ord("中"))
        emoji_code = x.XKeysymToKeycode(display, 0x01000000 | ord("😀"))
        assert ascii_code and chinese_code == 0 and emoji_code == 0
        for pressed in (1, 0):
            assert t.XTestFakeKeyEvent(display, ascii_code, pressed, 0)
            x.XSync(display, 0)
            await asyncio.sleep(0.03)
        await asyncio.sleep(0.5)
        after = keymap()
        result = {
            "fcitx": (ROOT / "fcitx").read_text(),
            "simple": (ROOT / "simple").read_text(),
            "ascii_keycode": ascii_code,
            "chinese_keycode": chinese_code,
            "emoji_keycode": emoji_code,
            "partial_fcitx_status": status,
            "map_equal": before == after,
            "before_sha256": before,
            "after_sha256": after,
        }
        print(json.dumps(result, ensure_ascii=False), flush=True)
        assert (
            result["fcitx"] == "甲"
            and result["simple"] == "b"
            and status == "expired"
            and before == after
        )
        await bridge.aclose()
        x.XCloseDisplay(display)
    finally:
        for actor in actors:
            actor.terminate()
        for actor in actors:
            actor.wait(timeout=5)


asyncio.run(main())
