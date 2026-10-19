"""Display-only XWayland process. Preview bytes exist only in its stdin and RAM."""

import json
import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QSocketNotifier, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from inkecho.integration import APP_ID
from inkecho.ui.overlay import Overlay

MAX_FRAME = 8192
DISPLAY_FIELDS = {
    "overlay_style",
    "overlay_opacity",
    "overlay_position",
    "overlay_seconds",
}
STATES = {
    "idle",
    "recording",
    "transcribing",
    "polishing",
    "injecting",
    "succeeded",
    "failed",
    "cancelled",
}


def decode_frame(line):
    """Reject unexpected fields, unbounded text and non-display configuration."""
    if len(line) > MAX_FRAME:
        raise ValueError("invalid_display_frame")
    frame = json.loads(line)
    if not isinstance(frame, dict) or set(frame) != {
        "revision",
        "state",
        "text",
        "level",
        "settings",
    }:
        raise ValueError("invalid_display_frame")
    if type(frame["revision"]) is not int or frame["revision"] < 0:
        raise ValueError("invalid_display_revision")
    if frame["state"] not in STATES:
        raise ValueError("invalid_display_state")
    if not isinstance(frame["text"], str) or len(frame["text"]) > 240:
        raise ValueError("invalid_display_text")
    level = frame["level"]
    if (
        type(level) not in (int, float)
        or not math.isfinite(level)
        or not 0 <= level <= 1
    ):
        raise ValueError("invalid_display_level")
    settings = frame["settings"]
    if not isinstance(settings, dict) or set(settings) != DISPLAY_FIELDS:
        raise ValueError("invalid_display_settings")
    if settings["overlay_style"] not in {"siri", "waveform", "pulse"}:
        raise ValueError("invalid_display_style")
    if settings["overlay_position"] not in {
        "bottom-center",
        "top-center",
        "bottom-right",
    }:
        raise ValueError("invalid_display_position")
    for name, low, high in (("overlay_opacity", 0.1, 1), ("overlay_seconds", 0.1, 30)):
        value = settings[name]
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not low <= value <= high
        ):
            raise ValueError("invalid_display_number")
    return frame


class DisplayChannel:
    """Ordered snapshots; older revisions cannot revive a cancelled preview."""

    def __init__(self, overlay, store):
        self.overlay, self.store = overlay, store
        self.revision = -1

    def apply(self, frame):
        if frame["revision"] <= self.revision:
            return
        self.revision = frame["revision"]
        self.store.settings = SimpleNamespace(**frame["settings"])
        state = frame["state"]
        if state != self.overlay.state or not self.overlay.isVisible():
            self.overlay.show_state(state)
        if state in {"recording", "transcribing", "polishing", "injecting"}:
            self.overlay.set_text(frame["text"])
        else:
            self.overlay.set_text("")
        self.overlay.set_level(frame["level"])


def main():
    app = QApplication(["InkEcho"])
    app.setApplicationName("InkEcho")
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(
        QIcon(str(Path(__file__).resolve().parents[1] / "assets/inkecho.png"))
    )
    app.setQuitOnLastWindowClosed(False)
    if app.platformName() != "xcb":
        return 1

    class Store:
        settings = None

        def load_settings(self):
            return self.settings

    store = Store()
    overlay = Overlay(store)
    channel = DisplayChannel(overlay, store)
    buffer = bytearray()
    notifier = QSocketNotifier(sys.stdin.fileno(), QSocketNotifier.Type.Read)

    def acknowledge():
        handle = overlay.windowHandle()
        print(
            json.dumps(
                {
                    "revision": channel.revision,
                    "visible": overlay.isVisible(),
                    "exposed": bool(handle and handle.isExposed()),
                    "style": getattr(overlay, "style", ""),
                    "text_length": len(overlay.text),
                }
            ),
            flush=True,
        )

    def finish():
        notifier.setEnabled(False)
        overlay.hide()
        overlay.close()
        app.quit()

    def read(*_):
        try:
            chunk = os.read(sys.stdin.fileno(), MAX_FRAME)
            if not chunk:
                finish()
                return
            buffer.extend(chunk)
            while b"\n" in buffer:
                line, _, tail = buffer.partition(b"\n")
                buffer[:] = tail
                channel.apply(decode_frame(line))
            if len(buffer) > MAX_FRAME:
                raise ValueError("invalid_display_frame")
            acknowledge()
        except (ValueError, TypeError, OSError):
            finish()

    notifier.activated.connect(read)
    # Acknowledgements never contain preview text or input/configuration values.
    timer = QTimer()
    timer.setInterval(100)
    timer.timeout.connect(acknowledge)
    timer.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
