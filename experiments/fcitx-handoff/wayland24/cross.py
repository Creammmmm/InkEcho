"""24 Wayland guest, owned targets: expose actual keyboard preflight limitation."""

import asyncio
import json
import os
import subprocess
import time
from pathlib import Path

from inkecho.platform.fcitx5 import Fcitx5Bridge, FcitxOutputError
from inkecho.platform.keyboard import KeyboardError
from inkecho.platform.wayland_keyboard import WaylandKeyboardInput

ROOT = Path("/tmp/wayland24-r1")


async def main():
    actors = []
    bridge = Fcitx5Bridge()
    keyboard = WaylandKeyboardInput(timeout=10, cleanup_timeout=10)
    try:

        async def launch(name, module):
            for suffix in ("-text", "-focus"):
                (ROOT / (name + suffix)).unlink(missing_ok=True)
            env = dict(os.environ, GDK_BACKEND="wayland", GTK_IM_MODULE=module)
            for k in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH"):
                env.pop(k, None)
            p = subprocess.Popen(
                ["/usr/bin/python3", str(ROOT / "cross-target.py"), name], env=env
            )
            actors.append(p)
            for _ in range(100):
                if (ROOT / (name + "-focus")).exists():
                    return p
                await asyncio.sleep(0.1)
            raise RuntimeError("owned target did not focus " + name)

        await launch("fcitx", "fcitx")
        await bridge.connect()
        assert await bridge.insert("甲", lambda: True) == 1
        await asyncio.sleep(0.3)
        await launch("simple", "gtk-im-context-simple")
        await asyncio.sleep(0.5)
        try:
            await bridge.insert("乙", lambda: True, deadline=time.monotonic() + 0.7)
            raise RuntimeError("simple unexpectedly accepted Fcitx")
        except FcitxOutputError as e:
            assert e.code == "expired" and e.accepted == 1 and not e.uncertain
        await keyboard.connect()
        try:
            await keyboard.authorize()
            status = "authorized"
        except KeyboardError as error:
            status = error.code
        await asyncio.sleep(0.5)
        a = (ROOT / "fcitx-text").read_text() if (ROOT / "fcitx-text").exists() else ""
        b = (
            (ROOT / "simple-text").read_text()
            if (ROOT / "simple-text").exists()
            else ""
        )
        print(
            json.dumps(
                {
                    "fcitx": a,
                    "simple": b,
                    "keyboard_authorize": status,
                    "keyboard_text_sent": False,
                    "fcitx_no_target_deadline": "expired",
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        assert a == "甲" and b == "" and status != "authorized"
    finally:
        try:
            try:
                await keyboard.aclose()
            except KeyboardError:
                pass
            await bridge.aclose()
        finally:
            for p in actors:
                p.terminate()
            for p in actors:
                p.wait(timeout=5)


asyncio.run(main())
