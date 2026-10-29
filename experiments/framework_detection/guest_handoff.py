"""Owned X11 GTK windows; fallback uses xdotool for ASCII, not product keyboard."""

import asyncio
import json
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from inkecho.platform.output_router import OutputRouter

ROOT = Path("/tmp/inkecho-autodetect-v2")


class Keyboard:
    authorized = False

    def __init__(self):
        self.sent = []

    async def connect(self):
        pass

    async def authorize(self, parent_window=""):
        self.authorized = True

    async def aclose(self):
        pass

    @asynccontextmanager
    async def output_session(self):
        yield

    async def insert(self, text, active, **kwargs):
        assert active() and text.isascii()
        subprocess.run(["xdotool", "type", "--clearmodifiers", text], check=True)
        self.sent.append(text)
        return len(text)


async def main():
    actors = []
    try:
        for name, module in (("fcitx", "fcitx"), ("simple", "gtk-im-context-simple")):
            output = ROOT / name
            env = dict(os.environ, GTK_IM_MODULE=module)
            actors.append(
                subprocess.Popen(
                    [sys.executable, str(ROOT / "target.py"), name, str(output)],
                    env=env,
                )
            )
            for _ in range(100):
                if Path(str(output) + ".module").exists():
                    break
                await asyncio.sleep(0.1)
            else:
                raise RuntimeError("target did not start")
        await asyncio.sleep(3)

        async def focus(index, name):
            ids = (
                subprocess.check_output(
                    [
                        "xdotool",
                        "search",
                        "--pid",
                        str(actors[index].pid),
                        "--onlyvisible",
                        "--name",
                        "^InkEcho isolated " + name + "$",
                    ],
                    text=True,
                )
                .strip()
                .splitlines()
            )
            xid = ids[-1]
            subprocess.run(["xdotool", "windowactivate", xid], check=True, timeout=5)
            await asyncio.sleep(1)
            assert (
                subprocess.check_output(
                    ["xdotool", "getactivewindow"], text=True
                ).strip()
                == xid
            )

        await focus(0, "fcitx")
        keyboard = Keyboard()
        router = OutputRouter(keyboard)
        await router.prepare_task("auto")
        async with router.output_session():
            assert await router.insert("A", lambda: True) == 1
            selected_before = router.selected
            await asyncio.sleep(0.5)
            await focus(1, "simple")
            assert await router.insert("BC", lambda: True) == 2
            selected_after = router.selected
        await asyncio.sleep(0.5)
        result = {
            "before": selected_before,
            "after": selected_after,
            "fcitx": (ROOT / "fcitx").read_text(),
            "simple": (ROOT / "simple").read_text(),
            "keyboard_writes": keyboard.sent,
        }
        print(json.dumps(result, ensure_ascii=False), flush=True)
        assert result == {
            "before": "fcitx",
            "after": "keyboard",
            "fcitx": "A",
            "simple": "BC",
            "keyboard_writes": ["BC"],
        }
    finally:
        for actor in actors:
            actor.terminate()
        for actor in actors:
            actor.wait(timeout=5)


asyncio.run(main())
