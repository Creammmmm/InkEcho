"""Text-free status waveform, with no focus or mouse input requested."""

import math

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


class Overlay(QWidget):
    def __init__(self, store):
        super().__init__()
        self.store = store
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
        self.setWindowTitle("InkEcho 状态提示")
        self.resize(176, 58)
        self.state, self.level, self.phase = "idle", 0.0, 0.0
        self.animation = QTimer(self)
        self.animation.setInterval(40)
        self.animation.timeout.connect(self.animate)
        self.dismiss = QTimer(self)
        self.dismiss.setSingleShot(True)
        self.dismiss.timeout.connect(self.hide)

    def animate(self):
        self.phase += 0.2
        self.update()

    def set_level(self, value):
        self.level = value

    def show_state(self, state):
        if state == "idle":
            return
        self.state = state
        settings = self.store.load_settings()
        self.style = settings.overlay_style
        self.setWindowOpacity(settings.overlay_opacity)
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + (screen.width() - self.width()) // 2
        y = screen.bottom() - self.height() - 45
        if settings.overlay_position == "top-center":
            y = screen.y() + 45
        elif settings.overlay_position == "bottom-right":
            x = screen.right() - self.width() - 30
        self.move(x, y)
        self.dismiss.stop()
        self.show()
        self.animation.start()
        if state in {"succeeded", "failed", "cancelled"}:
            self.dismiss.start(round(settings.overlay_seconds * 1000))

    def preview(self):
        self.show_state("recording")
        self.dismiss.start(2200)

    def hideEvent(self, event):
        self.animation.stop()
        super().hideEvent(event)

    def paintEvent(self, _event):
        colors = {
            "failed": "#fca5a5",
            "cancelled": "#b9c5d9",
            "transcribing": "#8ed6f2",
            "polishing": "#93adff",
        }
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#102a56"))
        painter.drawRoundedRect(self.rect(), 18, 18)
        painter.setPen(
            QPen(
                QColor(colors.get(self.state, "#9fc0ff")),
                5,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            )
        )
        if self.state == "succeeded":
            painter.drawLine(71, 30, 82, 40)
            painter.drawLine(82, 40, 105, 18)
            return
        if self.state == "cancelled":
            painter.drawLine(73, 29, 103, 29)
            return
        if self.state == "failed":
            painter.drawLine(76, 19, 100, 39)
            painter.drawLine(76, 39, 100, 19)
            return
        if self.state == "injecting":
            painter.drawLine(62, 29, 110, 29)
            painter.drawLine(99, 18, 110, 29)
            painter.drawLine(99, 40, 110, 29)
            return
        if getattr(self, "style", "waveform") == "pulse":
            painter.setBrush(QColor(colors.get(self.state, "#9fc0ff")))
            radius = 7 + int(4 * abs(math.sin(self.phase)))
            painter.drawEllipse(88 - radius, 29 - radius, radius * 2, radius * 2)
            return
        for index in range(7):
            height = 8 + int(
                (10 + self.level * 18) * abs(math.sin(self.phase + index * 0.65))
            )
            x = 34 + index * 18
            painter.drawLine(x, 29 - height // 2, x, 29 + height // 2)
