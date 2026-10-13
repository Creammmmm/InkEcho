#!/usr/bin/env python3
"""Bounded owned native Wayland fixture test; no audio, cloud or clipboard."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dbus_next import Message, MessageType
from historical_accessibility import AccessibilityInput, InputUnavailable

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = "独立焦点验证：你好，InkEcho 🌍。"


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xdotool")
    args = parser.parse_args()
    if args.xdotool and os.environ.get("DISPLAY") in (None, ":0", ":1"):
        raise SystemExit("Use an isolated Xvfb display")
    backend = AccessibilityInput()
    emitter = AccessibilityInput()
    children = []
    events = []
    report = {}

    def observe(message):
        if (
            message.message_type == MessageType.SIGNAL
            and message.interface == "org.a11y.atspi.Event.Object"
            and message.member == "StateChanged"
            and len(message.body) >= 2
            and message.body[0] in {"focused", "active", "defunct"}
        ):
            events.append((message.sender, message.path, *message.body[:2]))

    def fixture(path):
        child = subprocess.Popen(
            [
                "/usr/bin/python3",
                str(ROOT / "scripts/feasibility/wayland_editor_fixture.py"),
                str(path),
            ],
            env={**os.environ, "GDK_BACKEND": "x11" if args.xdotool else "wayland"},
        )
        children.append(child)
        return child

    def focus(child):
        if args.xdotool:
            window = (
                subprocess.check_output(
                    [
                        args.xdotool,
                        "search",
                        "--pid",
                        str(child.pid),
                        "--name",
                        "InkEcho owned",
                    ],
                    text=True,
                )
                .strip()
                .splitlines()[-1]
            )
            subprocess.run([args.xdotool, "windowfocus", window], check=True)

    try:
        with tempfile.TemporaryDirectory(
            prefix="inkecho-listening-events-"
        ) as directory:
            output = Path(directory) / "first.json"
            first = fixture(output)
            await asyncio.sleep(1)
            focus(first)
            await asyncio.sleep(0.2)
            await backend.connect()
            backend.bus.add_message_handler(observe)
            target = await backend.capture_target()
            assert target.process_id == first.pid, "Owned fixture must be focused"
            report["owned_target_captured"] = True
            report["session"] = "isolated-x11" if args.xdotool else "native-wayland"
            events.clear()
            transient = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    "from PySide6.QtWidgets import QApplication,QLineEdit; "
                    "from PySide6.QtCore import QTimer; "
                    "a=QApplication([]); w=QLineEdit(); w.show(); "
                    "QTimer.singleShot(350,w.close); "
                    "QTimer.singleShot(600,a.quit); a.exec()",
                ],
                env={
                    **os.environ,
                    "QT_QPA_PLATFORM": "offscreen",
                    "QT_LINUX_ACCESSIBILITY_ALWAYS_ON": "1",
                },
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            children.append(transient)
            await asyncio.wait_for(asyncio.to_thread(transient.wait), 5)
            await asyncio.sleep(0.3)
            report["transient_qt_foreign_state_events"] = sum(
                event[:2] not in (target.address, target.window) for event in events
            )
            assert backend.target_is_current(target) and await backend._current(target)
            report["transient_qt_target_survived"] = True
            # Synthetic regression events over the real accessibility D-Bus;
            # these are explicitly not claimed to originate from the Qt child.
            await emitter.connect()
            events.clear()
            for state, enabled in (("defunct", 1), ("focused", 0), ("active", 0)):
                await emitter.bus.send(
                    Message.new_signal(
                        "/inkecho/probe/foreign",
                        "org.a11y.atspi.Event.Object",
                        "StateChanged",
                        "si",
                        [state, enabled],
                    )
                )
            await asyncio.sleep(0.1)
            replayed = [
                event for event in events if event[1] == "/inkecho/probe/foreign"
            ]
            assert len(replayed) == 3
            assert backend.target_is_current(target) and await backend._current(target)
            report["synthetic_foreign_events_old_handler_would_cancel"] = len(replayed)
            report["synthetic_foreign_events_new_handler_survived"] = True
            await backend.inject(target, SAMPLE, lambda: True)
            await asyncio.sleep(0.1)
            assert json.loads(output.read_text()) == SAMPLE
            report["unicode_insert_exact"] = True
            target = await backend.capture_target()
            try:
                await backend.inject(target, "CANCELLED", lambda: False)
            except InputUnavailable:
                pass
            else:
                raise AssertionError("Cancelled token inserted")
            assert json.loads(output.read_text()) == SAMPLE
            report["explicit_cancel_no_insert"] = True
            second = fixture(Path(directory) / "second.json")
            await asyncio.sleep(1)
            focus(second)
            await asyncio.sleep(0.2)
            assert not backend.target_is_current(target)
            second.terminate()
            await asyncio.wait_for(asyncio.to_thread(second.wait), 5)
            focus(first)
            await asyncio.sleep(0.4)
            assert await backend._state(target.address)
            try:
                await backend.inject(target, "STALE", lambda: True)
            except InputUnavailable:
                pass
            else:
                raise AssertionError("Focus-lost token inserted")
            assert json.loads(output.read_text()) == SAMPLE
            report["focus_away_old_token_rejected"] = True
            report["cloud_calls"] = 0
            print(json.dumps(report))
    finally:
        backend.close()
        emitter.close()
        for child in children:
            if child.poll() is None:
                child.terminate()
                await asyncio.wait_for(asyncio.to_thread(child.wait), 5)


if __name__ == "__main__":
    asyncio.run(main())
