#!/usr/bin/env python3
"""Measure whether a Qt waveform overlay changes focus on isolated X11."""

import argparse
import ctypes
import json
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


def focus_preserved(samples: list[int]) -> bool:
    return len(samples) >= 3 and samples[0] > 1 and len(set(samples)) == 1


class Overlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("InkEcho isolated overlay")
        self.resize(180, 60)
        self.move(800, 100)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#18322f"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 18, 18)
        painter.setPen(QPen(QColor("#6ee7b7"), 5))
        for index, height in enumerate([8, 16, 28, 40, 28, 16, 8]):
            x = 36 + index * 18
            painter.drawLine(x, 30 - height // 2, x, 30 + height // 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--isolated-display", required=True)
    args = parser.parse_args()
    if args.isolated_display in {":0", ":0.0", ":1", ":1.0"}:
        parser.error("Use a dedicated Xvfb display, not a normal desktop display.")
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
    x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = x11.XOpenDisplay(args.isolated_display.encode())
    if not display:
        raise RuntimeError("Cannot open isolated X11 display.")
    samples = []

    def sample() -> None:
        window, revert = ctypes.c_ulong(), ctypes.c_int()
        x11.XGetInputFocus(display, ctypes.byref(window), ctypes.byref(revert))
        samples.append(window.value)

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    overlay = Overlay()
    sample()
    overlay.show()
    QTimer.singleShot(400, sample)
    QTimer.singleShot(800, sample)
    QTimer.singleShot(900, overlay.hide)
    QTimer.singleShot(1200, sample)
    QTimer.singleShot(1300, app.quit)
    try:
        app.exec()
    finally:
        overlay.close()
        x11.XCloseDisplay(display)
    passed = focus_preserved(samples)
    print(
        json.dumps(
            {
                "focus_samples": samples,
                "passed": passed,
                "environment": "isolated Xvfb; no compositor or window manager",
            }
        )
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
