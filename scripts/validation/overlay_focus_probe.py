#!/usr/bin/env python3
"""Verify production overlay focus behavior on a dedicated virtual X11 display."""

import argparse
import ctypes
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLineEdit

from inkecho.config import ConfigStore
from inkecho.ui.overlay import Overlay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-display", required=True)
    args = parser.parse_args()
    if args.isolated_display in {":0", ":0.0", ":1", ":1.0"}:
        parser.error("Use a dedicated virtual display.")
    os.environ["DISPLAY"] = args.isolated_display
    os.environ["QT_QPA_PLATFORM"] = "xcb"
    x11 = ctypes.CDLL("libX11.so.6")
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XGetInputFocus.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.POINTER(ctypes.c_int),
    ]
    x11.XSetInputFocus.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_ulong,
    ]
    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = x11.XOpenDisplay(args.isolated_display.encode())
    if not display:
        raise RuntimeError("Virtual display unavailable")
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    target = QLineEdit("InkEcho isolated focus target")
    target.setWindowTitle("InkEcho owned overlay focus target")
    target.show()
    app.processEvents()
    target_id = int(target.winId())
    x11.XSetInputFocus(display, target_id, 1, 0)
    x11.XSync(display, 0)
    samples = []
    with tempfile.TemporaryDirectory(prefix="inkecho-overlay-") as directory:
        store = ConfigStore(Path(directory))
        store.initialize()
        overlay = Overlay(store)

        def sample(stage):
            focused, revert = ctypes.c_ulong(), ctypes.c_int()
            x11.XGetInputFocus(display, ctypes.byref(focused), ctypes.byref(revert))
            samples.append({"stage": stage, "focus": focused.value})

        def show(style, state):
            store.save_settings(replace(store.load_settings(), overlay_style=style))
            overlay.show_state(state)

        sample("before")
        for index, (style, state) in enumerate(
            [
                ("waveform", "recording"),
                ("pulse", "recording"),
                ("pulse", "transcribing"),
                ("waveform", "polishing"),
                ("waveform", "injecting"),
                ("waveform", "succeeded"),
                ("waveform", "failed"),
                ("pulse", "cancelled"),
            ]
        ):
            QTimer.singleShot(index * 150, lambda s=style, t=state: show(s, t))
            QTimer.singleShot(
                index * 150 + 100, lambda s=style, t=state: sample(s + ":" + t)
            )
        QTimer.singleShot(1300, overlay.hide)
        QTimer.singleShot(1700, lambda: sample("after"))
        QTimer.singleShot(2200, app.quit)
        try:
            app.exec()
        finally:
            overlay.close()
            target.close()
            x11.XCloseDisplay(display)
    passed = len(samples) == 10 and all(item["focus"] == target_id for item in samples)
    print(
        json.dumps(
            {"passed": passed, "environment": "isolated Xvfb", "samples": samples}
        )
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
