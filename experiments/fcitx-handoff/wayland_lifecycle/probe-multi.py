import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from inkecho.platform.wayland_keyboard import WaylandKeyboardInput

ROOT = Path("/tmp/wayland-lifecycle")


async def main():
    mode = sys.argv[1]
    assert mode in ("held", "early")
    for n in ("text", "focused"):
        (ROOT / n).unlink(missing_ok=True)
    env = dict(os.environ, GDK_BACKEND="wayland", GTK_IM_MODULE="gtk-im-context-simple")
    for k in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH"):
        env.pop(k, None)
    proc = subprocess.Popen(["/usr/bin/python3", str(ROOT / "target.py")], env=env)
    paused = False
    keyboard = WaylandKeyboardInput(timeout=10, cleanup_timeout=10)
    try:
        for _ in range(100):
            if (ROOT / "focused").exists():
                break
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError("owned target did not acquire focus")
        await keyboard.connect()
        await keyboard.authorize()
        os.kill(proc.pid, signal.SIGSTOP)
        paused = True
        started = time.monotonic()
        async with keyboard.output_session():
            count = await keyboard.insert("甲乙丙丁戊己庚辛壬癸", lambda: True)
            if mode == "held":
                os.kill(proc.pid, signal.SIGCONT)
                paused = False
                await asyncio.sleep(1)
        if paused:
            os.kill(proc.pid, signal.SIGCONT)
            paused = False
        await asyncio.sleep(1)
        value = (ROOT / "text").read_text() if (ROOT / "text").exists() else ""
        print(
            json.dumps(
                {
                    "mode": mode,
                    "returned": count,
                    "elapsed": time.monotonic() - started,
                    "actual": value,
                    "expected": "甲乙丙丁戊己庚辛壬癸",
                    "module": __import__(
                        "inkecho.platform.wayland_worker", fromlist=[""]
                    ).__file__,
                    "paused_during_send": True,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    finally:
        if paused:
            os.kill(proc.pid, signal.SIGCONT)
        try:
            await keyboard.aclose()
        finally:
            proc.terminate()
            proc.wait(timeout=5)


asyncio.run(main())
