"""Test-only owned-focus gate around production Guardian's remote injection seam."""

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

from natural_owned_browser import parent_pid, process_start


def save(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, indent=2)
    temporary.replace(path)


def guard_allowed(state: dict, owner: int, now: float) -> bool:
    try:
        return bool(
            state["allowed"] is True
            and state["backend_confirmed"] is True
            and state["owner_pid"] == owner
            and parent_pid(state["pid"]) == owner
            and process_start(state["pid"]) == state["start_ticks"]
            and 0 <= now - state["sampled_at"] <= 0.25
        )
    except (KeyError, TypeError, ValueError):
        return False


async def worker(guard_path: Path, count_path: Path, owner: int) -> None:
    from inkecho.platform.keyboard import KeyboardError
    from inkecho.platform.wayland_worker import Guardian, MutterSession, serve

    counts = {"press_success": 0, "release_success": 0, "guard_rejections": 0}
    save(count_path, counts)

    class GuardedRemote(MutterSession):
        async def key(self, code, pressed, *, newline=False):
            if pressed:
                try:
                    state = json.loads(guard_path.read_text())
                except (OSError, ValueError):
                    state = {}
                if not guard_allowed(state, owner, time.monotonic()):
                    counts["guard_rejections"] += 1
                    save(count_path, counts)
                    raise KeyboardError("input_cancelled")
            result = await super().key(code, pressed, newline=newline)
            counts["press_success" if pressed else "release_success"] += 1
            save(count_path, counts)
            return result

    # This is the production protocol and mapping/cancel/cleanup algorithm, with
    # an explicit remote dependency. No production class or API is monkeypatched.
    guardian = Guardian(remote=GuardedRemote())
    reader = asyncio.StreamReader(limit=4096)
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_running_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)

    def stop():
        guardian.stop(permanent=True)
        reader.feed_eof()

    for name in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(name, stop)
    transport, output_protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout.buffer
    )
    writer = asyncio.StreamWriter(transport, output_protocol, None, loop)

    async def reply(value):
        try:
            writer.write((json.dumps(value, separators=(",", ":")) + "\n").encode())
            await asyncio.wait_for(writer.drain(), 1)
        except (TimeoutError, BrokenPipeError, OSError):
            stop()

    await serve(reader, reply, guardian)
