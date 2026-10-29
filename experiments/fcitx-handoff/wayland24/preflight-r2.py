import asyncio
import json
import platform
from pathlib import Path

import inkecho.platform.wayland_keyboard as module
import inkecho.platform.wayland_worker as worker


async def main():
    keyboard = module.WaylandKeyboardInput(timeout=10, cleanup_timeout=10)
    result = {
        "worker": str(Path(worker.__file__).resolve()),
        "keyboard": str(Path(module.__file__).resolve()),
        "machine": platform.machine(),
        "text_sent": False,
    }
    try:
        try:
            await keyboard.connect()
            result["connect"] = "ok"
        except Exception as error:
            result["connect"] = getattr(error, "code", type(error).__name__)
        if result["connect"] == "ok":
            try:
                await keyboard.authorize()
                result["authorize"] = "ok"
            except Exception as error:
                result["authorize"] = getattr(error, "code", type(error).__name__)
    finally:
        try:
            await keyboard.aclose()
            result["close"] = "ok"
        except Exception as error:
            result["close"] = getattr(error, "code", type(error).__name__)
    print(json.dumps(result), flush=True)


asyncio.run(main())
