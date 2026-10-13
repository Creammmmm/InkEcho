#!/usr/bin/env python3
"""Exercise production keyboard delivery only in owned native XWayland fixtures."""

import argparse
import asyncio
import ctypes
import json
import os
import subprocess
import tempfile
from pathlib import Path

from x11_probe import KeyboardMap

from inkecho.platform.accessibility import AccessibilityInput, InputUnavailable
from inkecho.platform.keyboard import KeyboardError, KeyboardInput

SAMPLE = "你好 InkEcho，世界！ café Ω 😀\n第二行。"


def normalized(mapping):
    width, values = mapping
    rows = []
    for offset in range(0, len(values), width):
        row = list(values[offset : offset + width])
        while row and row[-1] == 0:
            row.pop()
        rows.append(row)
    return rows


async def main(args):
    if os.environ.get("XDG_SESSION_TYPE") != "wayland":
        raise RuntimeError("Native XWayland session required")
    fixtures = []
    access = AccessibilityInput()
    inputs = KeyboardInput()
    keyboard = KeyboardMap(os.environ["DISPLAY"])
    report = {}

    def command(*arguments):
        return subprocess.check_output(
            [args.xdotool, *arguments], text=True, timeout=3
        ).strip()

    try:
        await access.connect()
        await inputs.connect()
        with tempfile.TemporaryDirectory(prefix="inkecho-owned-keyboard-") as temporary:
            outputs, windows = [], []
            for index in range(2):
                output = Path(temporary) / f"fixture{index}.json"
                process = subprocess.Popen(
                    [
                        "/usr/bin/python3",
                        str(Path(__file__).with_name("wayland_editor_fixture.py")),
                        str(output),
                    ],
                    env=dict(os.environ, GDK_BACKEND="x11"),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                fixtures.append(process)
                outputs.append(output)
                window = None
                for _ in range(80):
                    try:
                        matches = command(
                            "search", "--onlyvisible", "--pid", str(process.pid)
                        ).splitlines()
                        if matches and output.exists():
                            window = matches[0]
                            break
                    except subprocess.CalledProcessError:
                        pass
                    await asyncio.sleep(0.1)
                if window is None:
                    raise RuntimeError("Owned fixture not ready")
                windows.append(window)

            async def activate(index):
                if int(command("getwindowpid", windows[index])) != fixtures[index].pid:
                    raise RuntimeError("Owned window identity changed")
                command("windowactivate", "--sync", windows[index])
                for _ in range(50):
                    try:
                        if (await access.capture_target()).process_id == fixtures[
                            index
                        ].pid:
                            return
                    except InputUnavailable:
                        pass
                    await asyncio.sleep(0.1)
                raise RuntimeError("Owned fixture did not become active")

            original = inputs._send
            events = []
            mode = "unicode"
            allowed = True
            pressed = 0

            def guarded_send(window, keycode, is_pressed):
                nonlocal allowed, pressed
                if is_pressed:
                    driver = inputs._driver
                    if driver.focus() != window:
                        raise RuntimeError("Fixture focus changed before test emission")
                    active = driver._property(driver.root, driver.active_atom)
                    pid = driver._property(active, driver.pid_atom)
                    if pid not in {process.pid for process in fixtures}:
                        raise RuntimeError("Refusing input outside owned fixtures")
                    pressed += 1
                original(window, keycode, is_pressed)
                events.append((window, keycode, is_pressed))
                if mode == "switch" and not is_pressed and pressed == 1:
                    command("windowactivate", "--sync", windows[1])
                if mode == "cancel" and is_pressed:
                    allowed = False

            inputs._send = guarded_send
            await activate(0)
            report["unicode_count"] = await inputs.insert(SAMPLE, lambda: True)
            await asyncio.sleep(0.2)
            report["production_unicode_exact"] = (
                json.loads(outputs[0].read_text()) == SAMPLE
            )
            mode, pressed = "switch", 0
            await inputs.insert("甲乙丙丁", lambda: True)
            await asyncio.sleep(0.2)
            report["switch_first_exact"] = (
                json.loads(outputs[0].read_text()) == SAMPLE + "甲"
            )
            report["switch_second_exact"] = (
                json.loads(outputs[1].read_text()) == "乙丙丁"
            )
            mode, pressed = "cancel", 0
            before = len(events)
            try:
                await inputs.insert("ABCDE", lambda: allowed)
            except KeyboardError as error:
                report["cancel_code"] = error.code
            await asyncio.sleep(0.2)
            report["cancel_one_press_one_release"] = [
                item[2] for item in events[before:]
            ] == [True, False]
            report["cancel_no_tail"] = json.loads(outputs[1].read_text()) == "乙丙丁A"
            # Reserve and destroy our own unmapped X resource on the still-live
            # connection, avoiding another client's potential XID reuse.
            driver = inputs._driver
            driver.x11.XCreateSimpleWindow.argtypes = [
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.c_ulong,
                ctypes.c_ulong,
            ]
            driver.x11.XCreateSimpleWindow.restype = ctypes.c_ulong
            driver.x11.XDestroyWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            dead = driver.x11.XCreateSimpleWindow(
                driver.display, driver.root, 0, 0, 1, 1, 0, 0, 0
            )
            assert dead
            driver.x11.XDestroyWindow(driver.display, dead)
            driver.x11.XSync(driver.display, 0)
            try:
                inputs._driver.send(dead, 38, True)
            except KeyboardError as error:
                report["closed_window_code"] = error.code
            report["map_restored"] = normalized(keyboard.original) == normalized(
                keyboard.read()
            )
    finally:
        try:
            await inputs.aclose()
        finally:
            try:
                access.close()
            finally:
                try:
                    keyboard.close()
                finally:
                    for process in fixtures:
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
                    print(json.dumps(report), flush=True)
    assert report["production_unicode_exact"]
    assert report["switch_first_exact"] and report["switch_second_exact"]
    assert report["cancel_code"] == "input_cancelled"
    assert report["cancel_one_press_one_release"] and report["cancel_no_tail"]
    assert report["closed_window_code"] == "injection_failed"
    assert report["map_restored"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xdotool", required=True)
    asyncio.run(main(parser.parse_args()))
