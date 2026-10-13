#!/usr/bin/env python3
"""Production XSendEvent probe against a new VTE raw-byte sink; no shell."""

import argparse
import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

from keyboard_backend_probe import SAMPLE, normalized
from x11_probe import KeyboardMap

from inkecho.platform.keyboard import KeyboardInput


async def main(args):
    if os.environ.get("XDG_SESSION_TYPE") != "wayland":
        raise RuntimeError("Native XWayland session required")
    inputs = KeyboardInput()
    keyboard = KeyboardMap(os.environ["DISPLAY"])
    fixture = None
    report = {}

    def command(*arguments):
        return subprocess.check_output(
            [args.xdotool, *arguments], text=True, timeout=3
        ).strip()

    try:
        await inputs.connect()
        with tempfile.TemporaryDirectory(prefix="inkecho-owned-vte-") as temporary:
            output = Path(temporary) / "received.json"
            fixture = subprocess.Popen(
                [
                    "/usr/bin/python3",
                    str(Path(__file__).with_name("terminal_raw_fixture.py")),
                    str(output),
                ],
                env=dict(os.environ, GDK_BACKEND="x11"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            window = None
            for _ in range(80):
                try:
                    matches = command(
                        "search", "--onlyvisible", "--pid", str(fixture.pid)
                    ).splitlines()
                    if matches and output.exists():
                        window = matches[0]
                        break
                except subprocess.CalledProcessError:
                    pass
                await asyncio.sleep(0.1)
            if window is None:
                raise RuntimeError("Owned raw terminal did not become ready")
            if int(command("getwindowpid", window)) != fixture.pid:
                raise RuntimeError("Owned fixture identity mismatch")
            command("windowactivate", "--sync", window)
            await asyncio.sleep(0.3)
            if json.loads(output.read_text())["raw_hex"] != "":
                raise RuntimeError("Owned terminal is not empty")
            original = inputs._send

            def guarded_send(target, code, pressed):
                if pressed:
                    driver = inputs._driver
                    active = driver._property(driver.root, driver.active_atom)
                    if (
                        driver._property(active, driver.pid_atom) != fixture.pid
                        or driver.focus() != target
                    ):
                        raise RuntimeError("Refusing delivery outside owned VTE")
                original(target, code, pressed)

            inputs._send = guarded_send
            report["sent_codepoints"] = await inputs.insert(SAMPLE, lambda: True)
            await asyncio.sleep(0.3)
            received = json.loads(output.read_text())
            expected_bytes = SAMPLE.replace("\n", "\r").encode("utf-8")
            raw = bytes.fromhex(received["raw_hex"])
            report.update(
                raw_utf8_with_return_exact=raw == expected_bytes,
                unicode_content_exact=received["text"].replace("\r", "\n") == SAMPLE,
                carriage_returns=raw.count(b"\r"),
                line_feeds=raw.count(b"\n"),
                expected_bytes=len(expected_bytes),
                received_bytes=len(raw),
                native_xwayland=True,
                shell_started=False,
                clipboard_used=False,
            )
    finally:
        try:
            await inputs.aclose()
        finally:
            try:
                report["map_restored"] = normalized(keyboard.read()) == normalized(
                    keyboard.original
                )
            finally:
                try:
                    keyboard.close()
                finally:
                    if fixture is not None and fixture.poll() is None:
                        fixture.terminate()
                        try:
                            fixture.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            fixture.kill()
                            fixture.wait()
                    print(json.dumps(report), flush=True)
    assert report["raw_utf8_with_return_exact"] and report["unicode_content_exact"]
    assert report["map_restored"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xdotool", required=True)
    asyncio.run(main(parser.parse_args()))
