import asyncio
import os
import time
from collections import Counter
from pathlib import Path

from inkecho.platform.ibus_lifecycle import LifecycleCleanupError
from inkecho.platform.ibus_owned import Capability, Client


async def trusted(_):
    return True


async def main():
    root = Path(os.environ["XDG_RUNTIME_DIR"])
    counts = Counter()
    for _ in range(30):
        cap = Capability(root)
        client = Client(cap, owner_verifier=trusted)
        await client.begin(deadline=time.monotonic() + 10)
        assert (root / ("used-" + cap.name)).exists()
        await client.cancel()
        await client.close()
        assert not list(root.glob("*cap-*"))
        counts["normal"] += 1
    for i in range(100):
        cap = Capability(root)
        client = Client(cap, owner_verifier=trusted)
        begin = asyncio.create_task(client.begin(deadline=time.monotonic() + 10))
        await asyncio.sleep((i % 10) * 0.0002)
        try:
            cap.close()
            counts["close_ok"] += 1
        except LifecycleCleanupError:
            counts["close_uncertain"] += 1
        try:
            await begin
            counts["begin_ok"] += 1
            await client.cancel()
        except Exception:
            counts["begin_rejected"] += 1
        try:
            await client.close()
        except LifecycleCleanupError:
            counts["client_close_uncertain"] += 1
        leftovers = list(root.glob("*cap-*"))
        counts["leftovers"] += len(leftovers)
        for path in leftovers:
            path.unlink()
    print(dict(counts))


asyncio.run(main())
