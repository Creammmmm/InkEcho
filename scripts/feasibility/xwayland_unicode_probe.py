#!/usr/bin/env python3
"""Explicit native XWayland test, confined to a newly created empty GTK window."""

import argparse
import asyncio
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from historical_accessibility import (
    ACCESSIBLE,
    ACTIVE,
    ROOT,
    AccessibilityInput,
    has_state,
)
from x11_probe import KeyboardMap
from xsend_transport import XSendProbe

SAMPLE = "你好 InkEcho，世界！ café Ω 😀\n第二行。"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xdotool", default="xdotool")
    parser.add_argument(
        "--transport", choices=("xtest", "xsend", "xsend-ascii"), default="xtest"
    )
    parser.add_argument("--owner-mask", action="store_true")
    parser.add_argument("--fixture", choices=("gtk", "chrome"), default="gtk")
    args = parser.parse_args()
    sample = "a" if args.transport == "xsend-ascii" else SAMPLE
    if os.environ.get("XDG_SESSION_TYPE") != "wayland" or not os.environ.get("DISPLAY"):
        raise RuntimeError("Native XWayland session required")

    def command(*arguments):
        return subprocess.check_output(
            [args.xdotool, *arguments], text=True, timeout=3
        ).strip()

    with tempfile.TemporaryDirectory(prefix="inkecho-owned-xwayland-") as temporary:
        received = Path(temporary) / "received.json"
        events = Path(temporary) / "events.jsonl"
        fixture = subprocess.Popen(
            [
                "/usr/bin/python3",
                str(
                    Path(__file__).with_name(
                        "owned_browser_fixture.py"
                        if args.fixture == "chrome"
                        else "wayland_editor_fixture.py"
                    )
                ),
                str(received),
                str(events),
            ],
            env=dict(os.environ, GDK_BACKEND="x11"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        keyboard = None
        sender = None
        loop = asyncio.new_event_loop()
        access = AccessibilityInput()
        result = {"characters_sent": 0}
        try:
            owned_pid = fixture.pid
            if args.fixture == "chrome":
                for _ in range(50):
                    if received.with_suffix(".pid").exists():
                        owned_pid = int(received.with_suffix(".pid").read_text())
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Owned browser PID unavailable")
            window = None
            for _ in range(80):
                try:
                    focus = command("getwindowfocus")
                    if int(command("getwindowpid", focus)) == owned_pid:
                        window = focus
                        break
                except subprocess.CalledProcessError:
                    pass
                time.sleep(0.1)
            if window is None:
                raise RuntimeError("Owned fixture did not receive focus")
            for _ in range(80):
                if received.exists():
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("Owned fixture did not finish loading")
            if json.loads(received.read_text()) != "":
                raise RuntimeError("Owned fixture is not empty")
            command("windowactivate", "--sync", window)
            time.sleep(0.3)
            loop.run_until_complete(access.connect())
            keyboard = KeyboardMap(os.environ["DISPLAY"])
            sender = (
                XSendProbe(keyboard) if args.transport.startswith("xsend") else None
            )

            async def owned_active():
                applications = (await access._call(ROOT, ACCESSIBLE, "GetChildren"))[0]
                for app in applications:
                    try:
                        if await access._external_process_id(app) != owned_pid:
                            continue
                        windows = (
                            await access._call(tuple(app), ACCESSIBLE, "GetChildren")
                        )[0]
                        for window in windows:
                            if has_state(await access._state(tuple(window)), ACTIVE):
                                return True
                    except Exception:
                        continue
                return False

            for character in sample:
                focus = command("getwindowfocus")
                focus_pid = int(command("getwindowpid", focus))
                if focus_pid != owned_pid:
                    result["stopped_focus_pid"] = focus_pid
                    raise RuntimeError("Owned fixture lost focus")
                if not loop.run_until_complete(owned_active()):
                    raise RuntimeError("Owned fixture not compositor-active")
                if sender is not None:
                    sender.send(
                        character,
                        focus,
                        existing=args.transport == "xsend-ascii",
                        owner_mask=args.owner_mask,
                    )
                elif character == "\n":
                    command("key", "--clearmodifiers", "Return")
                else:
                    command(
                        "type", "--clearmodifiers", "--delay", "100", "--", character
                    )
                result["characters_sent"] += 1
            time.sleep(0.3)
            actual = json.loads(received.read_text())
            result.update(
                exact_unicode=actual == sample,
                expected_codepoints=len(sample),
                received_codepoints=len(actual),
                fixture_received=actual,
                native_xwayland=True,
                compositor_active_verified=True,
                transport=args.transport,
                fixture=args.fixture,
                clipboard_used=False,
                owned_key_events=[
                    json.loads(line) for line in events.read_text().splitlines()
                ]
                if events.exists()
                else [],
            )
        finally:
            access.close()
            loop.close()
            if keyboard is not None:
                try:
                    if args.transport == "xsend-ascii":
                        result["keyboard_map_restored"] = (
                            keyboard.read() == keyboard.original
                        )
                    elif sender is not None:
                        result["keyboard_map_restored"] = sender.restore()
                        result["mapping_snapshot"] = sender.snapshot_path
                        result["temporary_slot"] = sender.code

                        def normalized(mapping):
                            width, values = mapping
                            rows = []
                            for offset in range(0, len(values), width):
                                row = list(values[offset : offset + width])
                                while row and row[-1] == 0:
                                    row.pop()
                                rows.append(row)
                            return rows

                        before = normalized(keyboard.original)
                        after = normalized(keyboard.read())
                        result["normalized_map_restored"] = before == after
                        result["changed_keycodes"] = [
                            keyboard.first + index
                            for index, (a, b) in enumerate(
                                zip(before, after, strict=True)
                            )
                            if a != b
                        ]
                    else:
                        result["keyboard_map_restored"] = keyboard.restore()
                finally:
                    keyboard.close()
            fixture.terminate()
            try:
                fixture.wait(timeout=3)
            except subprocess.TimeoutExpired:
                fixture.kill()
                fixture.wait()
            print(json.dumps(result, ensure_ascii=False), flush=True)
        if not result.get("exact_unicode") or not result.get("keyboard_map_restored"):
            raise RuntimeError("Owned XWayland Unicode validation failed")


if __name__ == "__main__":
    main()
