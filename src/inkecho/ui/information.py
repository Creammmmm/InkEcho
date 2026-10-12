"""Compatibility, private usage data and explicit desktop integration pages."""

import asyncio
from datetime import date

from PySide6.QtWidgets import QCheckBox, QFormLayout, QPlainTextEdit

from inkecho import __version__
from inkecho.integration import IntegrationError
from inkecho.platform.capabilities import detect_desktop
from inkecho.statistics import StatisticsError
from inkecho.ui.widgets import Page, actions, button, card, label


class CompatibilityPage(Page):
    def __init__(self, session):
        super().__init__(
            "输入与兼容性", "明确当前环境的能力，安全校验始终先于文字输入。"
        )
        self.session = session
        frame, layout = card()
        self.environment = label("")
        self.availability = label("")
        layout.addWidget(self.environment)
        layout.addWidget(self.availability)
        layout.addWidget(
            label(
                "已验证的直接输入路径为 AT-SPI 可编辑文本控件。"
                "中文、其他 Unicode 与换行在隔离 X11 编辑器中通过测试；"
                "目标失焦、光标改变或任务取消后，迟到结果不会改投其他窗口。"
            )
        )
        layout.addWidget(
            label(
                "Chrome 和 VTE 终端在本机未提供所需的可编辑辅助功能接口。"
                "Wayland 现允许实验性逐目标检查，完整原生输入链路仍未验证。"
                "Ubuntu 24.04 的完整桌面、"
                "不同桌面环境及物理 F13/F14 仍待验证。",
                muted=True,
            )
        )
        layout.addWidget(
            label("不读取或改写剪贴板，也不会在失败时改用粘贴。", muted=True)
        )
        self.body.addWidget(frame)
        self.body.addWidget(
            actions(button("重新检查输入服务", lambda: self.run(self.recheck())))
        )
        self.finish()
        self.refresh()

    def refresh(self):
        environment = detect_desktop()
        self.environment.setText(
            f"{environment.distribution} · {environment.desktop} "
            f"· {environment.session}"
        )
        if environment.session == "wayland" and self.session.connected:
            text = (
                "辅助功能服务已连接。Wayland 输入为实验性：仅在目标明确可编辑、"
                "窗口活动且光标焦点均通过校验时开始，失败时会显示原因。"
            )
        elif self.session.connected:
            text = "辅助功能服务已连接。具体输入目标仍需通过可编辑性与焦点校验。"
        else:
            text = "辅助功能服务尚未连接，请检查桌面辅助功能服务后重试。"
        self.availability.setText(text)

    async def recheck(self):
        if not self.session.connected:
            await self.session.initialize()
        self.refresh()
        self.message.setText(
            "已更新状态。聚焦目标文本框后，用快捷键开始；此页不会注入文字。"
        )


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
            "succeeded": "成功",
            "failed": "失败",
            "cancelled": "取消",
            "characters": "已输入字符数（Unicode 码点）",
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
