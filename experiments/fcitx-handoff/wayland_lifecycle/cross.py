import asyncio
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from inkecho.platform.fcitx5 import Fcitx5Bridge, FcitxOutputError
from inkecho.platform.wayland_keyboard import WaylandKeyboardInput

ROOT = Path("/tmp/wayland-lifecycle")


async def main():
    actors = []
    paused = False
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
        await keyboard.connect()
        await keyboard.authorize()
        assert await bridge.insert("甲", lambda: True) == 1
        await asyncio.sleep(0.3)
        target = await launch("simple", "gtk-im-context-simple")
        await asyncio.sleep(0.5)
        try:
            await bridge.insert("乙", lambda: True, deadline=time.monotonic() + 0.7)
            raise RuntimeError("simple unexpectedly accepted Fcitx")
        except FcitxOutputError as e:
            assert e.code == "expired" and e.accepted == 1 and not e.uncertain
        os.kill(target.pid, signal.SIGSTOP)
        paused = True
        text = "乙丙丁戊己庚辛壬癸"
        async with keyboard.output_session():
            count = await keyboard.insert(text, lambda: True)
        os.kill(target.pid, signal.SIGCONT)
        paused = False
        await asyncio.sleep(1)
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
                    "expected_simple": text,
                    "keyboard_count": count,
                    "fcitx_no_target_deadline": "expired",
                    "simple_paused_during_keyboard_and_restore": True,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        assert a == "甲" and b == text and count == len(text)
    finally:
        if paused:
            os.kill(target.pid, signal.SIGCONT)
        try:
            await keyboard.aclose()
            await bridge.aclose()
        finally:
            for p in actors:
                p.terminate()
            for p in actors:
                p.wait(timeout=5)


asyncio.run(main())
