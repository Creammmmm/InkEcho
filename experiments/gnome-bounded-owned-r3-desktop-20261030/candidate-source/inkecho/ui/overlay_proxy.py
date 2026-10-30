"""Nonblocking display-only IPC; the main settings application stays native."""

import asyncio
import json
import sys

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal
from PySide6.QtWidgets import QApplication

from inkecho.ui.overlay import Overlay
from inkecho.ui.overlay_host import DISPLAY_FIELDS, MAX_FRAME


class OverlayProxy(QObject):
    failed = Signal(str)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.state, self.text, self.level = "idle", "", 0.0
        self.capture_ready = False
        self.revision = 0
        self.state_revision = 0
        self.last_ack_revision = -1
        self.preview_token = 0
        self.visible = False
        self.exposed = False
        self.style = ""
        self.settings = None
        self.text_length = 0
        self.closed = False
        self.broken = False
        self.pending = None
        self.reply = bytearray()
        self.process = QProcess(self)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("QT_QPA_PLATFORM", "xcb")
        self.process.setProcessEnvironment(environment)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.setStandardErrorFile(QProcess.nullDevice())
        self.process.started.connect(self.flush)
        self.process.readyReadStandardOutput.connect(self.read_reply)
        self.process.bytesWritten.connect(self.flush)
        self.process.errorOccurred.connect(self.process_error)
        self.process.finished.connect(self.finished)
        self.ack_timeout = QTimer(self)
        self.ack_timeout.setSingleShot(True)
        self.ack_timeout.setInterval(3000)
        self.ack_timeout.timeout.connect(self.fail)
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.flush)
        self.timer.start()

    def isVisible(self):
        return self.visible

    def snapshot(self):
        settings = self.settings
        if settings is None:
            return
        self.style = settings.overlay_style
        self.revision += 1
        self.pending = (
            json.dumps(
                {
                    "revision": self.revision,
                    "state": self.state,
                    "text": self.text,
                    "level": self.level,
                    "capture_ready": self.capture_ready,
                    "settings": {
                        name: getattr(settings, name) for name in DISPLAY_FIELDS
                    },
                },
                ensure_ascii=False,
            ).encode()
            + b"\n"
        )
        if len(self.pending) > MAX_FRAME:
            raise ValueError("invalid_display_frame")

    def flush(self, *_):
        if self.closed or self.broken or self.pending is None:
            return
        if self.process.state() == QProcess.ProcessState.NotRunning:
            if self.state == "idle":
                self.pending = None
                return
            self.ack_timeout.start()
            self.process.start(sys.executable, ["-m", "inkecho.ui.overlay_host"])
            return
        if (
            self.process.state() != QProcess.ProcessState.Running
            or self.process.bytesToWrite()
        ):
            return
        frame, self.pending = self.pending, None
        self.process.write(frame)

    def show_state(self, state):
        if self.closed or self.broken:
            return
        self.settings = self.store.load_settings()
        self.preview_token += 1
        self.state = state
        if state != "recording":
            self.capture_ready = False
        if state in {
            "idle",
            "recording",
            "succeeded",
            "unconfirmed",
            "failed",
            "cancelled",
        }:
            self.text = ""
        self.snapshot()
        self.state_revision = self.revision
        self.flush()

    def set_text(self, text):
        if (
            self.closed
            or self.broken
            or self.state
            not in {
                "recording",
                "transcribing",
                "polishing",
                "injecting",
            }
        ):
            return
        self.text = text[-240:] if isinstance(text, str) else ""
        self.snapshot()

    def set_capture_ready(self, ready):
        if self.closed or self.broken:
            return
        self.capture_ready = bool(ready) and self.state == "recording"
        self.snapshot()

    def set_level(self, value):
        if (
            self.closed
            or self.broken
            or self.state
            not in {
                "recording",
                "transcribing",
                "polishing",
                "injecting",
            }
        ):
            return
        self.level = min(1.0, max(0.0, float(value)))
        self.snapshot()

    def hide(self):
        self.show_state("idle")

    def preview(self):
        self.show_state("recording")
        self.set_capture_ready(True)
        token = self.preview_token
        QTimer.singleShot(
            2200, lambda: self.hide() if self.preview_token == token else None
        )

    def read_reply(self):
        self.reply.extend(bytes(self.process.readAllStandardOutput()))
        try:
            while b"\n" in self.reply:
                line, _, tail = self.reply.partition(b"\n")
                self.reply[:] = tail
                value = json.loads(line)
                revision = value["revision"]
                if (
                    type(revision) is int
                    and max(self.state_revision, self.last_ack_revision)
                    <= revision
                    <= self.revision
                ):
                    self.last_ack_revision = revision
                    self.ack_timeout.stop()
                    self.visible = value["visible"] is True
                    self.exposed = value["exposed"] is True
                    self.text_length = value["text_length"]
            if len(self.reply) > MAX_FRAME:
                raise ValueError("invalid_display_reply")
        except (ValueError, KeyError, TypeError):
            self.fail()

    def fail(self):
        if self.closed or self.broken:
            return
        self.broken = True
        self.ack_timeout.stop()
        self.pending = None
        self.text = ""
        self.visible = self.exposed = False
        self.process.closeWriteChannel()
        self.failed.emit(
            "悬浮预览不可用，请检查 XWayland 是否可用；录音与输入仍可继续。"
        )

    def process_error(self, _):
        self.fail()

    def finished(self, *_):
        self.visible = self.exposed = False
        self.fail()

    def close(self):
        self.closed = True
        self.preview_token += 1
        self.timer.stop()
        self.ack_timeout.stop()
        self.pending = None
        self.text = ""
        self.visible = self.exposed = False
        self.process.closeWriteChannel()

    async def shutdown(self):
        self.close()

        async def wait_for_exit():
            while self.process.state() != QProcess.ProcessState.NotRunning:
                await asyncio.sleep(0.01)

        try:
            await asyncio.wait_for(wait_for_exit(), 3)
        except TimeoutError:
            # Only this owned display process: never restart or replay its text.
            self.failed.emit("悬浮预览未能及时关闭，正在清理显示进程。")
            self.process.kill()
            await asyncio.wait_for(wait_for_exit(), 3)


def create_overlay(store, parent=None):
    if QApplication.platformName().startswith("wayland"):
        return OverlayProxy(store, parent)
    return Overlay(store)
