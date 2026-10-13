#!/usr/bin/env python3
"""Actual AT-SPI Unicode/focus test on an isolated Xvfb + D-Bus session.

Historical captured-target workflow: run against a pre-current-focus checkout.
The current TaskController intentionally has no captured-target API.
"""

import argparse
import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

from historical_accessibility import AccessibilityInput, InputUnavailable

from inkecho.core import State, TaskController

SAMPLE = "你好 InkEcho，世界！ café Ω 😀\n第二行。"


async def main():
    if not hasattr(TaskController, "focus_changed"):
        raise SystemExit(
            "Historical workflow requires the alpha6 or earlier captured-target "
            "Session/Core. Use its historical checkout or packaged runtime."
        )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xdotool", default="xdotool")
    args = parser.parse_args()
    if os.environ.get("DISPLAY") in (None, ":0", ":1"):
        raise SystemExit("Use an isolated Xvfb display, never a user desktop.")
    fixture = Path(__file__).with_name("gtk_target.py")
    processes = []
    backend = AccessibilityInput()
    with tempfile.TemporaryDirectory(prefix="inkecho-atspi-") as folder:
        output = Path(folder) / "received.json"
        try:
            process = subprocess.Popen(
                ["/usr/bin/python3", str(fixture), "editor", str(output)],
                env=dict(os.environ, GDK_BACKEND="x11"),
            )
            processes.append(process)
            await asyncio.sleep(1)

            def xdo(*arguments):
                return subprocess.check_output(
                    [args.xdotool, *arguments], text=True
                ).strip()

            window = xdo(
                "search", "--pid", str(process.pid), "--name", "InkEcho isolated editor"
            ).splitlines()[-1]
            xdo("windowfocus", window)
            await asyncio.sleep(0.2)
            await backend.connect()
            target = await backend.capture_target()
            await backend.inject(target, SAMPLE, lambda: True)
            await asyncio.sleep(0.2)
            assert json.loads(output.read_text()) == SAMPLE

            class CoreInput:
                delivery = None

                def target_is_current(self, token):
                    return backend.target_is_current(token)

                def inject(self, task_id, token, text, can_continue):
                    async def deliver():
                        await backend.inject(token, text, can_continue)
                        controller.injection_finished(task_id)

                    self.delivery = asyncio.create_task(deliver())

            core_input = CoreInput()
            controller = TaskController(core_input)
            backend.on_focus_lost = controller.focus_changed
            task_id = controller.begin(await backend.capture_target())
            assert task_id is not None
            assert controller.recording_stopped(task_id)
            controller.transcribed(task_id, "✓")
            await core_input.delivery
            assert controller.outcome == State.SUCCEEDED
            expected = json.loads(output.read_text())
            assert expected == SAMPLE + "✓"

            target = await backend.capture_target()
            try:
                await backend.inject(target, "NEVER_INSERT_CANCELLED", lambda: False)
                raise AssertionError("Cancelled task unexpectedly inserted")
            except InputUnavailable:
                pass
            assert json.loads(output.read_text()) == expected

            xdo("windowfocus", "1")
            await asyncio.sleep(0.2)
            xdo("windowfocus", window)
            await asyncio.sleep(0.2)
            assert not backend.target_is_current(target), (
                "Focus return revived stale target"
            )
            try:
                await backend.inject(target, "NEVER_INSERT_STALE", lambda: True)
                raise AssertionError("Stale task unexpectedly inserted")
            except InputUnavailable:
                pass
            assert json.loads(output.read_text()) == expected
            print(
                json.dumps(
                    {
                        "transport": "targeted AT-SPI",
                        "exact_unicode": True,
                        "cancelled_unchanged": True,
                        "focus_away_back_unchanged": True,
                        "core_injection_succeeded": True,
                        "display": os.environ["DISPLAY"],
                    },
                    ensure_ascii=False,
                )
            )
        finally:
            backend.close()
            for process in processes:
                process.terminate()
                process.wait(timeout=5)


asyncio.run(main())
