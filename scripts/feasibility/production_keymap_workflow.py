"""Exercise the production worker only inside nested_keymap_probe's owned desktop."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path


async def run_worker(
    sample,
    *,
    after_character=None,
    cancel_after=None,
    eof_after=None,
):
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", ""))
    if (
        runtime.parent.parent != Path("/tmp")
        or not runtime.parent.name.startswith("inkecho-isolated-keymap-")
        or runtime.name != "runtime"
        or os.environ.get("DISPLAY")
        or not os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    ):
        raise RuntimeError("private_worker_precondition_failed")
    repository = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(repository / "src"))
    process = await asyncio.create_subprocess_exec(
        str(repository / ".venv/bin/python"),
        "-m",
        "inkecho.platform.wayland_worker",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    number = 0

    async def request(operation, **fields):
        nonlocal number
        number += 1
        process.stdin.write(
            (json.dumps({"id": number, "op": operation, **fields}) + "\n").encode()
        )
        await process.stdin.drain()
        line = await asyncio.wait_for(process.stdout.readline(), 10)
        if not line:
            diagnostic = await asyncio.wait_for(process.stderr.read(), 2)
            print(diagnostic[-5000:].decode(errors="replace"), file=sys.stderr)
            raise RuntimeError("isolated_worker_exited")
        response = json.loads(line)
        if response.get("event"):
            print(
                json.dumps(
                    {
                        "worker_event": response["event"],
                        "operation": operation,
                        "request_id": number,
                    }
                ),
                file=sys.stderr,
            )
            raise RuntimeError("worker_" + str(response["event"]))
        if response.get("id") != number or not response.get("ok"):
            raise RuntimeError("worker_" + str(response.get("error", "protocol_error")))
        return response

    try:
        await request("connect")
        await request("authorize")
        await request("begin", deadline=time.monotonic() + 60)
        count = 0
        for character in sample:
            response = await request("key", value=character)
            count += response["count"]
            if after_character is not None:
                await after_character(count)
            if count == cancel_after:
                await request("cancel")
                await request("close")
                return count
            if count == eof_after:
                process.stdin.close()
                await asyncio.wait_for(process.wait(), 10)
                if process.returncode != 0:
                    raise RuntimeError("worker_eof_cleanup_failed")
                return count
        await request("finish")
        await request("close")
        return count
    finally:
        process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), 10)
            if process.returncode:
                diagnostic = await asyncio.wait_for(process.stderr.read(), 2)
                print(diagnostic[-5000:].decode(errors="replace"), file=sys.stderr)
        except TimeoutError:
            # This helper is restricted to the disposable compositor. A failure
            # is reported; do not pretend its restoration was accepted.
            process.terminate()
            raise RuntimeError("isolated_worker_cleanup_timeout") from None
