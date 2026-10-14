"""Compatibility, private usage data and explicit desktop integration pages."""

import asyncio
from datetime import date

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QCheckBox, QFormLayout, QPlainTextEdit

from inkecho import __version__
from inkecho.integration import IntegrationError
from inkecho.platform.capabilities import detect_desktop
from inkecho.statistics import StatisticsError
from inkecho.ui.widgets import Page, actions, button, card, label


class CompatibilityPage(Page):
    def __init__(self, session):
        super().__init__("输入与兼容性", "识别完成后，像键盘一样向当时的光标位置输入。")
        self.session = session
        frame, layout = card()
        self.environment = label("")
        self.availability = label("")
        layout.addWidget(self.environment)
        layout.addWidget(self.availability)
        layout.addWidget(
            label(
                "录音前不用选择文本框；录音和识别期间可以切换窗口。"
                "输出时请把光标放在希望接收文字的位置。"
                "取消任务会停止后续输入，已经发送的按键无法撤回。"
            )
        )
        self.scope = label("", muted=True)
        layout.addWidget(self.scope)
        layout.addWidget(label("不使用剪贴板，也不依赖系统输入法。", muted=True))
        self.body.addWidget(frame)
        self.body.addWidget(
            actions(
                button("启用键盘输入", lambda: self.run(self.enable())),
                button("重新检查输入服务", lambda: self.run(self.recheck())),
            )
        )
        self.finish()
        self.refresh()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start()

    def refresh(self):
        environment = detect_desktop()
        self.environment.setText(
            f"{environment.distribution} · {environment.desktop} "
            f"· {environment.session}"
        )
        native = getattr(self.session.inputs, "backend", None) == "gnome-wayland"
        self.scope.setText(
            "GNOME Wayland 实验性键盘输入：同一路径用于原生与 XWayland 窗口。"
            "支持中文等基本多文种字符；emoji 等扩展字符暂不支持，"
            "含这些字符的结果会整段停止发送。输入前请松开按键并关闭大写锁定。"
            "未经实测的应用不保证兼容。"
            if native
            else "当前键盘输入方式面向 X11 / XWayland 应用，无需远程控制授权。"
            "此方式不支持原生 Wayland 应用；未经实测的应用不保证兼容。"
        )
        if not self.session.connected:
            text = "键盘输入服务尚未连接。"
        elif getattr(self.session.inputs, "authorized", False):
            text = (
                "GNOME 键盘输入已启用；文字将发送到输出当时的光标位置。"
                if native
                else "键盘输入已启用；输出时请使用兼容的 X11 / XWayland 应用。"
            )
        else:
            text = "输入服务已连接，请点击「启用键盘输入」完成准备。"
        self.availability.setText(text)

    async def enable(self):
        if (
            self.session.controller.task
            or self.session.preparing
            or self.session.testing
        ):
            self.message.setText("请先结束当前任务，再调整键盘输入连接。")
            return
        enabled = await self.session.authorize_input()
        self.refresh()
        self.message.setText(
            "键盘输入已启用；此操作不会输入文字。"
            if enabled
            else "键盘输入尚未启用，请查看错误提示。"
        )

    async def recheck(self):
        if not self.session.connected:
            await self.session.initialize()
        self.refresh()
        self.message.setText("已更新状态；此检查不会请求授权或输入文字。")


class StatisticsPage(Page):
    def __init__(self, session, stats, log):
        super().__init__(
            "统计与日志", "仅保存汇总数字和固定诊断代码，不保存音频与转写正文。"
        )
        self.session, self.stats, self.log = session, stats, log
        frame, layout = card()
        self.summary = label("")
        layout.addWidget(self.summary)
        form = QFormLayout()
        names = {
            "recordings": "今日任务数",
            "succeeded": "已发送任务数",
            "failed": "失败",
            "cancelled": "取消",
            "characters": "已发送字符数（Unicode 码点）",
            "audio_seconds": "累计录音",
            "transcription_calls": "转写调用次数",
            "transcription_seconds": "转写耗时",
            "polishing_calls": "润色调用次数",
            "polishing_seconds": "润色耗时",
            "input_tokens": "润色输入 Token",
            "output_tokens": "润色输出 Token",
            "total_tokens": "润色总 Token",
        }
        self.values = {}
        for key, title in names.items():
            self.values[key] = label("—")
            form.addRow(title, self.values[key])
        layout.addLayout(form)
        self.body.addWidget(frame)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumHeight(160)
        self.logs.setPlaceholderText("暂无诊断记录")
        self.body.addWidget(self.logs)
        self.body.addWidget(
            actions(
                button("刷新", self.refresh),
                button("清除统计", lambda: self.run(self.clear_statistics())),
                button("清除日志", lambda: self.run(self.clear_logs())),
            )
        )
        self.finish()
        self.refresh()

    def refresh(self):
        self.summary.setText(f"{date.today().isoformat()} · 本地时区")
        try:
            values = self.stats.today()
            for key, widget in self.values.items():
                value = values[key]
                text = "未知（供应商未提供完整用量）" if value is None else str(value)
                if key.endswith("_seconds"):
                    text = f"{value:.1f} 秒"
                widget.setText(text)
            self.message.setText("Token 仅展示供应商报告值；未知值不会冒充精确计量。")
        except StatisticsError as error:
            self.message.setText(str(error))
            for widget in self.values.values():
                widget.setText("—")
        try:
            self.logs.setPlainText(self.log.recent())
        except OSError:
            self.logs.setPlainText("日志暂不可读取。")

    async def clear_statistics(self):
        await asyncio.to_thread(self.stats.clear)
        self.refresh()
        self.message.setText("统计已清除；配置、凭据和日志保持不变。")

    async def clear_logs(self):
        await asyncio.to_thread(self.log.clear)
        self.refresh()
        self.message.setText("诊断日志已清除。")


class AboutPage(Page):
    def __init__(self, session, integration):
        super().__init__(
            "关于与桌面集成", "为当前安装位置创建启动器；开机自启动由你决定。"
        )
        self.session, self.integration = session, integration
        frame, layout = card()
        layout.addWidget(label(f"InkEcho {__version__} · Linux 首期开发版"))
        self.location = label("")
        self.integration_status = label("")
        layout.addWidget(self.location)
        layout.addWidget(self.integration_status)
        layout.addWidget(
            label(
                "图标与启动器安装到当前用户目录。移动 AppImage 后可在此修复路径；"
                "移除桌面集成不会删除应用配置或系统密钥环中的凭据。",
                muted=True,
            )
        )
        self.autostart = QCheckBox("登录时在后台启动 InkEcho")
        layout.addWidget(self.autostart)
        self.body.addWidget(frame)
        self.body.addWidget(
            actions(
                button(
                    "安装启动器与图标",
                    lambda: self.run(self.apply(self.integration.install)),
                ),
                button(
                    "修复路径", lambda: self.run(self.apply(self.integration.repair))
                ),
                button(
                    "移除桌面集成",
                    lambda: self.run(self.apply(self.integration.remove)),
                ),
            )
        )
        self.body.addWidget(
            button("保存自启动设置", lambda: self.run(self.save_autostart()))
        )
        self.finish()
        self.refresh()

    def refresh(self):
        status = self.integration.status()
        self.location.setText(f"当前程序：{status['executable']}")
        if status["current"]:
            text = "桌面启动器已安装，路径有效。"
        elif status["installed"]:
            text = "启动器路径需要更新，请点击「修复路径」。"
        else:
            text = "尚未安装桌面启动器。"
        self.integration_status.setText(text)
        self.autostart.setChecked(status["autostart"])

    async def apply(self, operation):
        try:
            await asyncio.to_thread(operation)
            self.refresh()
            self.message.setText("桌面集成已更新。")
        except IntegrationError as error:
            self.message.setText(str(error))
            self.session.diagnostic.emit("integration_failed")

    async def save_autostart(self):
        enabled = self.autostart.isChecked()
        await self.apply(lambda: self.integration.set_autostart(enabled))
