"""Microphone, shortcut and visual preferences."""

import asyncio
from dataclasses import replace

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QProgressBar,
    QPushButton,
    QSpinBox,
)

from inkecho.audio import Recorder
from inkecho.platform.hotkeys import GnomeShortcuts, ShortcutError
from inkecho.ui.widgets import Page, actions, button, card


class ShortcutCapture(QPushButton):
    """Capture a physical combination without accepting text or IME input."""

    captured = Signal(str)

    def __init__(self, shortcut):
        super().__init__(shortcut)
        self.previous = shortcut
        self.listening = False
        self.pending = None
        self.clicked.connect(self.begin)

    def begin(self):
        self.listening = True
        self.pending = None
        self.setText("请按下快捷键 · Esc 取消")
        self.setFocus()

    def keyPressEvent(self, event):
        if not self.listening:
            return super().keyPressEvent(event)
        event.accept()
        if event.isAutoRepeat():
            return
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.cancel_capture()
            return
        if key in (
            Qt.Key.Key_Control,
            Qt.Key.Key_Shift,
            Qt.Key.Key_Alt,
            Qt.Key.Key_Meta,
            Qt.Key.Key_AltGr,
        ):
            return
        value = QKeySequence(event.keyCombination()).toString(
            QKeySequence.SequenceFormat.PortableText
        )
        from inkecho.platform.hotkeys import accelerator

        try:
            accelerator(value)
        except ShortcutError:
            self.pending = None
            self.setText("请选择字母、数字、空格或功能键组合")
            return
        self.pending = value
        self.setText(value)

    def keyReleaseEvent(self, event):
        if self.listening:
            event.accept()
            if self.pending and not event.isAutoRepeat():
                value = self.pending
                self.listening = False
                self.pending = None
                self.setEnabled(False)
                self.captured.emit(value)
            return
        super().keyReleaseEvent(event)

    def cancel_capture(self):
        self.listening = False
        self.pending = None
        self.setText(self.previous)

    def focusOutEvent(self, event):
        if self.listening:
            self.cancel_capture()
        super().focusOutEvent(event)


class RecordingPage(Page):
    def __init__(self, session, command):
        super().__init__("录音与快捷键", "选好麦克风，再为随时开口准备一个快捷键。")
        self.session, self.command = session, command
        self.shortcut_revision = 0
        self.shortcut_lock = asyncio.Lock()
        settings = session.store.load_settings()
        panel, body = card()
        form = QFormLayout()
        self.microphone = QComboBox()
        self.rate = QComboBox()
        for rate in (16000, 24000, 48000):
            self.rate.addItem(f"{rate:,} Hz · 单声道", rate)
        self.rate.setCurrentIndex(self.rate.findData(settings.sample_rate))
        self.limit = QSpinBox()
        self.limit.setRange(1, 300)
        self.limit.setSuffix(" 秒")
        self.limit.setValue(settings.recording_limit_seconds)
        self.shortcut = ShortcutCapture(settings.shortcut)
        self.shortcut.captured.connect(lambda value: self.run(self.enable(value)))
        for title, widget in (
            ("输入设备", self.microphone),
            ("采样率", self.rate),
            ("最长录音", self.limit),
            ("全局快捷键", self.shortcut),
        ):
            form.addRow(title, widget)
        body.addLayout(form)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        session.level.connect(lambda value: self.level.setValue(round(value * 100)))
        body.addWidget(self.level)
        body.addWidget(actions(button("刷新设备", self.refresh_devices)))
        self.body.addWidget(panel)
        self.refresh_devices()
        self.microphone.currentIndexChanged.connect(self.save)
        self.rate.currentIndexChanged.connect(self.save)
        self.limit.valueChanged.connect(self.save)
        self.finish()

    def refresh_devices(self):
        selected = self.session.store.load_settings().microphone
        self.microphone.blockSignals(True)
        self.microphone.clear()
        self.microphone.addItem("系统默认麦克风", "")
        for identifier, name in Recorder.devices():
            self.microphone.addItem(name, identifier.hex())
        index = self.microphone.findData(selected)
        if index < 0:
            self.microphone.addItem("已保存的设备当前不可用", selected)
            index = self.microphone.count() - 1
        self.microphone.setCurrentIndex(index)
        self.microphone.blockSignals(False)

    def save(self):
        try:
            settings = replace(
                self.session.store.load_settings(),
                microphone=self.microphone.currentData(),
                sample_rate=self.rate.currentData(),
                recording_limit_seconds=self.limit.value(),
            )
            self.session.store.save_settings(settings)
            self.message.setText("录音设置已自动保存。")
            return True
        except (ValueError, OSError):
            self.message.setText("无法保存，请检查配置文件或字段。")
            return False

    async def enable(self, shortcut=None):
        shortcut = shortcut or self.shortcut.text()
        old_shortcut = self.session.store.load_settings().shortcut
        try:
            async with self.shortcut_lock:
                await asyncio.to_thread(GnomeShortcuts().enable, shortcut, self.command)
                try:
                    self.session.store.save_settings(
                        replace(self.session.store.load_settings(), shortcut=shortcut)
                    )
                except (ValueError, OSError):
                    await asyncio.to_thread(
                        GnomeShortcuts().enable, old_shortcut, self.command
                    )
                    raise
            self.shortcut.previous = shortcut
            self.shortcut.setText(shortcut)
            self.message.setText("快捷键已保存并启用。")
        except (ShortcutError, ValueError, OSError):
            self.shortcut.setText(old_shortcut)
            self.message.setText("快捷键未更改，请检查组合键冲突或系统设置权限。")
        finally:
            self.shortcut.setEnabled(True)


class AppearancePage(Page):
    def __init__(self, session, preview):
        super().__init__("外观与悬浮提示", "以轻量波形显示进度，避免打断输入。")
        self.session = session
        settings = session.store.load_settings()
        panel, body = card()
        form = QFormLayout()
        self.style = QComboBox()
        self.style.addItem("Siri 灵感光谱 · 实时文字", "siri")
        self.style.addItem("简约波形", "waveform")
        self.style.addItem("呼吸圆点", "pulse")
        self.style.setCurrentIndex(max(0, self.style.findData(settings.overlay_style)))
        self.position = QComboBox()
        for title, value in (
            ("屏幕底部居中", "bottom-center"),
            ("屏幕顶部居中", "top-center"),
            ("右下角", "bottom-right"),
        ):
            self.position.addItem(title, value)
        self.position.setCurrentIndex(
            max(0, self.position.findData(settings.overlay_position))
        )
        self.opacity = QDoubleSpinBox()
        self.opacity.setRange(0.1, 1)
        self.opacity.setSingleStep(0.1)
        self.opacity.setValue(settings.overlay_opacity)
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.1, 30)
        self.duration.setSuffix(" 秒")
        self.duration.setValue(settings.overlay_seconds)
        self.tray = QCheckBox("关闭窗口时保留托盘入口（托盘不可用时保持窗口可见）")
        self.tray.setChecked(settings.close_to_tray)
        form.addRow("动画样式", self.style)
        form.addRow("位置", self.position)
        form.addRow("不透明度", self.opacity)
        form.addRow("结果显示时间", self.duration)
        body.addLayout(form)
        self.tray.hide()
        self.body.addWidget(panel)
        self.style.currentIndexChanged.connect(self.save)
        self.position.currentIndexChanged.connect(self.save)
        self.opacity.valueChanged.connect(self.save)
        self.duration.valueChanged.connect(self.save)
        self.finish()

    def save(self):
        try:
            self.session.store.save_settings(
                replace(
                    self.session.store.load_settings(),
                    overlay_position=self.position.currentData(),
                    overlay_style=self.style.currentData(),
                    overlay_opacity=self.opacity.value(),
                    overlay_seconds=self.duration.value(),
                    close_to_tray=True,
                )
            )
            self.message.setText("外观设置已保存。")
        except (ValueError, OSError):
            self.message.setText("外观设置无法保存。")
