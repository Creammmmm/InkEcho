"""Run only inside a disposable X11 guest; no user content is observed."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from inkecho.platform.fcitx5 import Fcitx5Bridge

ROOT = Path("/tmp/inkecho-autodetect-v2")


async def wait_for(path):
    for _ in range(100):
        if path.exists():
            return
        await asyncio.sleep(0.1)
    raise RuntimeError("target did not start")


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
            await wait_for(Path(str(output) + ".module"))
        # A GTK process can report its module before Mutter maps its window.
        await asyncio.sleep(3)
        info = {}
        for index, name in enumerate(("fcitx", "simple")):
            xid = (
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
                .splitlines()[-1]
            )
            subprocess.run(["xdotool", "windowactivate", xid], check=True, timeout=5)
            await asyncio.sleep(1)
            focused = subprocess.check_output(
                ["xdotool", "getactivewindow"], text=True
            ).strip()
            info[name + "_window_focused"] = focused == xid
            if focused != xid:
                raise RuntimeError("owned target not focused")
            client = Fcitx5Bridge()
            try:
                await client.connect()
                try:
                    info[name + "_send"] = await client.insert(
                        ("甲", "乙")[index], lambda: True
                    )
                except Exception as error:
                    info[name + "_send"] = getattr(error, "code", type(error).__name__)
            finally:
                await client.aclose()
            await asyncio.sleep(0.5)
        for name in ("fcitx", "simple"):
            info[name + "_module"] = (ROOT / (name + ".module")).read_text()
            path = ROOT / name
            info[name + "_text"] = path.read_text() if path.exists() else ""

        print(json.dumps(info, ensure_ascii=False), flush=True)
    finally:
        for actor in actors:
            actor.terminate()
        for actor in actors:
            actor.wait(timeout=5)


asyncio.run(main())
