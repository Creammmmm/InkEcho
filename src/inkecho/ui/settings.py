"""Microphone, shortcut and visual preferences."""

import asyncio
from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QProgressBar,
    QSpinBox,
)

from inkecho.audio import Recorder
from inkecho.platform.hotkeys import GnomeShortcuts
from inkecho.ui.widgets import Page, actions, button, card, label


class RecordingPage(Page):
    def __init__(self, session, command):
        super().__init__("录音与快捷键", "选好麦克风，再为随时开口准备一个快捷键。")
        self.session, self.command = session, command
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
        self.shortcut = QLineEdit(settings.shortcut)
        self.shortcut.setPlaceholderText("F13 / F14 / Ctrl+Alt+K")
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
        body.addWidget(
            actions(
                button("刷新设备", self.refresh_devices),
                button("测试麦克风 · 3 秒", lambda: self.run(self.test_audio())),
            )
        )
        body.addWidget(
            label("麦克风测试只在内存采集，不上传、不保存音频。", muted=True)
        )
        self.body.addWidget(panel)
        self.body.addWidget(
            actions(
                button("保存录音设置", self.save, primary=True),
                button("保存并启用快捷键", lambda: self.run(self.enable())),
                button("停用快捷键", lambda: self.run(self.disable())),
            )
        )
        self.body.addWidget(
            label(
                "快捷键由 GNOME 管理。启用会检查冲突；不会覆盖其他应用的绑定。"
                "当前原生会话的实际按键触发仍需验证。",
                muted=True,
            )
        )
        self.refresh_devices()
        self.finish()

    def refresh_devices(self):
        selected = self.session.store.load_settings().microphone
        self.microphone.clear()
        self.microphone.addItem("系统默认麦克风", "")
        for identifier, name in Recorder.devices():
            self.microphone.addItem(name, identifier.hex())
        index = self.microphone.findData(selected)
        if index < 0:
            self.microphone.addItem("已保存的设备当前不可用", selected)
            index = self.microphone.count() - 1
        self.microphone.setCurrentIndex(index)

    def save(self):
        try:
            settings = replace(
                self.session.store.load_settings(),
                microphone=self.microphone.currentData(),
                sample_rate=self.rate.currentData(),
                recording_limit_seconds=self.limit.value(),
                shortcut=self.shortcut.text().strip(),
            )
            self.session.store.save_settings(settings)
            self.message.setText("录音设置已保存。")
            return True
        except (ValueError, OSError):
            self.message.setText("无法保存，请检查配置文件或字段。")
            return False

    async def test_audio(self):
        if not self.save():
            return
        self.message.setText("请说话，正在采集 3 秒麦克风音频……")
        audio = await self.session.sample_audio()
        self.message.setText(
            f"麦克风测试完成，收到 {len(audio):,} 字节 WAV 数据；未上传。"
        )

    async def enable(self):
        if not self.save():
            return
        await asyncio.to_thread(
            GnomeShortcuts().enable, self.shortcut.text(), self.command
        )
        self.message.setText("GNOME 快捷键已配置。请在目标文本框中实测触发。")

    async def disable(self):
        await asyncio.to_thread(GnomeShortcuts().disable)
        self.message.setText("InkEcho 快捷键已停用。")


class AppearancePage(Page):
    def __init__(self, session, preview):
        super().__init__("外观与悬浮提示", "以轻量波形显示进度，避免打断输入。")
        self.session = session
        settings = session.store.load_settings()
        panel, body = card()
        form = QFormLayout()
        self.style = QComboBox()
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
        body.addWidget(self.tray)
        self.body.addWidget(panel)
        self.body.addWidget(
            actions(
                button("保存外观", self.save, primary=True),
                button("预览波形", lambda: preview()),
            )
        )
        self.body.addWidget(
            label(
                "悬浮窗使用不接收焦点与鼠标穿透标志。"
                "已验证隔离 X11 环境不抢焦点，原生 Wayland 尚未验收。",
                muted=True,
            )
        )
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
                    close_to_tray=self.tray.isChecked(),
                )
            )
            self.message.setText("外观设置已保存。")
        except (ValueError, OSError):
            self.message.setText("外观设置无法保存。")
