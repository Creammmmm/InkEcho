"""Fixed synthetic text, owned GTK targets, disposable guest only."""

import asyncio
import json
import os
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dbus_next import Message
from dbus_next.aio import MessageBus

from inkecho.platform.output_router import OutputRouter, OutputRouterError

ROOT = Path("/tmp/handoff-r7")


class Keyboard:
    authorized = True

    def __init__(self):
        self.sent = []

    async def connect(self):
        pass

    async def aclose(self):
        pass

    @asynccontextmanager
    async def output_session(self):
        yield

    async def insert(self, text, *a, **kw):
        self.sent.append(text)
        raise AssertionError("unexpected keyboard handoff")


async def main():
    mode = sys.argv[1]
    actors = []
    results = {}
    try:
        for name, module in [("fcitx", "fcitx"), ("simple", "gtk-im-context-simple")]:
            path = ROOT / name
            path.unlink(missing_ok=True)
            Path(str(path) + ".module").unlink(missing_ok=True)
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

        await focus(0, "fcitx")
        bus = await MessageBus().connect()
        owner = await bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="GetNameOwner",
                signature="s",
                body=["org.fcitx.Fcitx5"],
            )
        )
        bus.disconnect()

        async def detect():
            return ("fcitx", owner.body[0])

        kb = Keyboard()
        router = OutputRouter(kb)
        router._system_detector = detect
        await router.prepare_task("auto")
        active = [True]
        try:
            async with router.output_session():
                assert await router.insert("甲", lambda: active[0]) == 1
                results["backend"] = router.selected
                await asyncio.sleep(0.3)
                await focus(1, "simple")
                deadline = time.monotonic() + (1.5 if mode == "expiry" else 5)
                finished = [False]

                async def control():
                    await asyncio.sleep(0.7)
                    results["pending_after_grace"] = not finished[0]
                    results["simple_during_wait"] = (
                        (ROOT / "simple").read_text()
                        if (ROOT / "simple").exists()
                        else ""
                    )
                    if mode == "restore":
                        await focus(0, "fcitx")
                    if mode == "cancel":
                        active[0] = False

                controller = asyncio.create_task(control())
                try:
                    results["send"] = await router.insert(
                        "乙", lambda: active[0], deadline=deadline
                    )
                except OutputRouterError as e:
                    results["error"] = e.code
                finally:
                    finished[0] = True
                    await controller
        except OutputRouterError as e:
            results.setdefault("error", e.code)
        await asyncio.sleep(0.5)
        results["fcitx"] = (
            (ROOT / "fcitx").read_text() if (ROOT / "fcitx").exists() else ""
        )
        results["simple"] = (
            (ROOT / "simple").read_text() if (ROOT / "simple").exists() else ""
        )
        results["keyboard"] = kb.sent
        results["selected_with_fixed_owner_probe"] = True
        expected = {
            "restore": ("甲乙", 2, None),
            "expiry": ("甲", None, "partial_input_failed"),
            "cancel": ("甲", None, "fcitx_cancelled"),
        }[mode]
        results["pass"] = (
            results["backend"] == "fcitx"
            and results["pending_after_grace"]
            and not results["simple_during_wait"]
            and not results["simple"]
            and not kb.sent
            and results["fcitx"] == expected[0]
            and results.get("error") == expected[2]
            and (mode != "restore" or results.get("send") == 1)
        )
        print(json.dumps({"mode": mode, **results}, ensure_ascii=False), flush=True)
        assert results["pass"]
    finally:
        for actor in actors:
            actor.terminate()
        for actor in actors:
            actor.wait(timeout=5)


asyncio.run(main())
