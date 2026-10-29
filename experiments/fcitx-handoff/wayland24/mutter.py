import asyncio
import json

from inkecho.platform.wayland_worker import MutterSession


async def main():
    session = MutterSession()
    result = {}
    try:
        try:
            await session.authorize()
            result["authorize"] = "ok"
        except Exception as e:
            result["authorize"] = getattr(e, "code", type(e).__name__)
    finally:
        try:
            await session.close()
            result["close"] = "ok"
        except Exception as e:
            result["close"] = getattr(e, "code", type(e).__name__)
    print(json.dumps(result), flush=True)


asyncio.run(main())
