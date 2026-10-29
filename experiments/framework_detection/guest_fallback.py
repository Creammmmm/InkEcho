"""Disposable guest: verify unavailable bridge chooses a fake keyboard once."""

import asyncio
import json
from contextlib import asynccontextmanager

from inkecho.platform.output_router import OutputRouter


class Keyboard:
    authorized = False

    def __init__(self):
        self.sent = []

    async def connect(self):
        pass

    async def authorize(self, parent_window=""):
        self.authorized = True

    @asynccontextmanager
    async def output_session(self):
        yield

    async def insert(self, text, active, **kwargs):
        self.sent.append(text)
        return len(text)

    async def aclose(self):
        pass


async def run():
    keyboard = Keyboard()
    router = OutputRouter(keyboard)
    await router.prepare_task("auto")
    async with router.output_session():
        await router.insert("甲", lambda: True)
        selected = router.selected
    print(json.dumps({"selected": selected, "sent": keyboard.sent}, ensure_ascii=False))
    assert selected == "keyboard" and keyboard.sent == ["甲"]


asyncio.run(run())
