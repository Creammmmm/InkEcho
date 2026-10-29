import asyncio
import os
from pathlib import Path

from client import Client
from lifecycle import Capability


async def trusted(_):
    return True


async def run():
    root = Path(os.environ["XDG_RUNTIME_DIR"])
    # Deliberately abandoned file: a different task must still work.
    abandoned = Capability(root)
    os.close(abandoned._fd)
    abandoned._fd = None
    os.close(abandoned._dir)
    for i in range(2048):
        cap = Capability(root)
        client = Client(cap, owner_verifier=trusted)
        await client.begin()
        assert await client.insert("甲", lambda: True) == 1
        await client.cancel()
        await client.close()
        if i % 100 == 0:
            await asyncio.sleep(0.02)
    files = [
        path for path in root.iterdir() if path.name.startswith(("cap-", "used-cap-"))
    ]
    assert len(files) == 1 and files[0].name == abandoned.name
    print("2048 private-bus sessions passed; abandoned file preserved")


asyncio.run(run())
