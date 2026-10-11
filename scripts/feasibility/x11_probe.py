#!/usr/bin/env python3
"""Probe Unicode typing on a deliberately isolated X11 test display.

This is a feasibility diagnostic, not a production injection backend. A focus
check followed by XTest input is not atomic. Never point this at user windows.
"""

import argparse
import ctypes
import json
import os
import subprocess
import sys
from collections.abc import Callable

SAMPLE = "中文输入 InkEcho — Καλημέρα 🌍\n第二行！"


class KeyboardMap:
    """Snapshot and restore the isolated server's keyboard mapping."""

    def __init__(self, display: str):
        self.x11 = ctypes.CDLL("libX11.so.6")
        pointer = ctypes.c_void_p
        integer = ctypes.c_int
        symbol = ctypes.c_ulong
        self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x11.XOpenDisplay.restype = pointer
        self.x11.XDisplayKeycodes.argtypes = [
            pointer,
            ctypes.POINTER(integer),
            ctypes.POINTER(integer),
        ]
        self.x11.XGetKeyboardMapping.argtypes = [
            pointer,
            ctypes.c_ubyte,
            integer,
            ctypes.POINTER(integer),
        ]
        self.x11.XGetKeyboardMapping.restype = ctypes.POINTER(symbol)
        self.x11.XChangeKeyboardMapping.argtypes = [
            pointer,
            integer,
            integer,
            ctypes.POINTER(symbol),
            integer,
        ]
        self.x11.XSync.argtypes = [pointer, integer]
        self.x11.XFree.argtypes = [pointer]
        self.x11.XCloseDisplay.argtypes = [pointer]
        self.display = self.x11.XOpenDisplay(display.encode())
        if not self.display:
            raise RuntimeError("Cannot open the isolated X11 display.")
        low, high = integer(), integer()
        self.x11.XDisplayKeycodes(self.display, ctypes.byref(low), ctypes.byref(high))
        self.first, self.count = low.value, high.value - low.value + 1
        self.original = self.read()

    def read(self) -> tuple[int, tuple[int, ...]]:
        width = ctypes.c_int()
        values = self.x11.XGetKeyboardMapping(
            self.display, self.first, self.count, ctypes.byref(width)
        )
        if not values:
            raise RuntimeError("Cannot read the isolated keyboard mapping.")
        try:
            return width.value, tuple(values[: self.count * width.value])
        finally:
            self.x11.XFree(values)

    def restore(self) -> bool:
        width, values = self.original
        if self.read() != self.original:
            array = (ctypes.c_ulong * len(values))(*values)
            self.x11.XChangeKeyboardMapping(
                self.display, self.first, width, array, self.count
            )
            self.x11.XSync(self.display, 0)
        return self.read() == self.original

    def close(self) -> None:
        self.x11.XCloseDisplay(self.display)


def inject(
    text: str,
    target: int,
    focus: Callable[[], int],
    send: Callable[[str], None],
    cancelled: Callable[[], bool],
) -> int:
    """Abort before the next character if the test task or target changes."""
    count = 0
    for character in text:
        if cancelled():
            raise RuntimeError("Cancelled; no further input was sent.")
        if focus() != target:
            raise RuntimeError("Focus changed; no further input was sent.")
        send(character)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-display", required=True)
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--xdotool", default="xdotool")
    parser.add_argument("--text", default=SAMPLE)
    parser.add_argument("--cancelled", action="store_true")
    args = parser.parse_args()
    # Keep an accidental default invocation away from the normal user display.
    if args.isolated_display in {":0", ":0.0", ":1", ":1.0"}:
        parser.error("Use a dedicated Xvfb display, not a normal desktop display.")
    environment = dict(os.environ, DISPLAY=args.isolated_display)

    def command(*arguments: str) -> str:
        return subprocess.check_output(
            [args.xdotool, *arguments], env=environment, text=True
        ).strip()

    def send(character: str) -> None:
        if character == "\n":
            command("key", "--clearmodifiers", "Return")
        else:
            command("type", "--clearmodifiers", "--delay", "100", "--", character)

    keyboard = KeyboardMap(args.isolated_display)
    result = {"display": args.isolated_display, "target": args.window}
    succeeded = False
    try:
        result["characters_sent"] = inject(
            args.text,
            args.window,
            lambda: int(command("getwindowfocus")),
            send,
            lambda: args.cancelled,
        )
        result["status"] = "sent; verify target contents separately"
        succeeded = True
    except RuntimeError as error:
        result["status"] = str(error)
    finally:
        try:
            result["keyboard_map_restored"] = keyboard.restore()
        finally:
            keyboard.close()
    print(json.dumps(result, ensure_ascii=False))
    if not succeeded or not result["keyboard_map_restored"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
