"""Production client against the isolated V2 GJS service; never target a desktop."""

import asyncio
import os
from pathlib import Path

from inkecho.platform.ibus import Capability, Client


async def trusted(_owner):
    # The isolated GJS process is not GNOME Shell; production keeps verification.
    return True


async def run():
    root = Path(os.environ["XDG_RUNTIME_DIR"])
    for _ in range(32):
        cap = Capability(root)
        client = Client(cap, owner_verifier=trusted)
        await client.begin()
        assert await client.insert("甲\n乙\t丙", lambda: True) == 5
        await client.cancel()
        await client.close()
    assert not list(root.glob("cap-*"))
    assert not list(root.glob("used-cap-*"))
    print("production client: 32 isolated GJS sessions passed")


asyncio.run(run())
