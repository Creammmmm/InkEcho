"""Compatibility, private usage data and explicit desktop integration pages."""

import asyncio
from datetime import date

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QPlainTextEdit,
    QSpinBox,
)

from inkecho import __version__
from inkecho.app import InputMaintenanceBusy
from inkecho.integration import IntegrationError
from inkecho.platform.capabilities import detect_desktop
from inkecho.platform.fcitx5_install import FcitxInstaller, FcitxInstallError
from inkecho.platform.ibus_extension import ExtensionError, ExtensionManager
from inkecho.platform.owned_extension import OwnedExtensionManager
from inkecho.statistics import StatisticsError
from inkecho.ui.widgets import Page, actions, button, card, label


class CompatibilityPage(Page):
    def __init__(self, session):
        super().__init__("输入与兼容性", "识别完成后，像键盘一样向当时的光标位置输入。")
        self.session = session
        self.fcitx_installer = FcitxInstaller()
        self.fcitx_action_lock = asyncio.Lock()
        self.ibus_extension = ExtensionManager()
        self.owned_extension = OwnedExtensionManager()
        self.ibus_action_lock = asyncio.Lock()
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
        layout.addWidget(label("不使用剪贴板；输入方式可在下方选择。", muted=True))
        form = QFormLayout()
        self.output_method = QComboBox()
        for title, value in (
            ("自动选择", "auto"),
            ("模拟键盘", "keyboard"),
            ("Fcitx5（需要 InkEcho 输入桥）", "fcitx"),
            ("IBus（旧 V2 实验扩展）", "ibus"),
            ("IBus（GNOME 新版扩展）", "ibus-owned"),
        ):
            self.output_method.addItem(title, value)
        selected = self.output_method.findData(
            session.store.load_settings().output_method
        )
        self.output_method.setCurrentIndex(selected)
        self._saved_output_method = self.output_method.currentData()
        self.output_method.currentIndexChanged.connect(self.save_output_method)
        form.addRow("文字输出方式", self.output_method)
        self.receiver_wait = QSpinBox()
        self.receiver_wait.setRange(20, 250)
        self.receiver_wait.setSuffix(" 毫秒")
        self.receiver_wait.setValue(
            session.store.load_settings().receiver_feedback_wait_ms
        )
        self._saved_receiver_wait = self.receiver_wait.value()
        self.receiver_wait.valueChanged.connect(self.save_receiver_wait)
        form.addRow("接收窗口绘制提示等待上限", self.receiver_wait)
        self.receiver_feedback = label("", muted=True)
        layout.addWidget(self.receiver_feedback)
        layout.addWidget(
            label(
                "默认最多等待 40 毫秒的窗口绘制提示；有提示可提前继续。"
                "仅已检测到绘制反馈的原生 X11 目标生效，不代表文字已显示。"
                "没有反馈时不会伪造帧确认；Wayland、XWayland及输入法输出暂不可用。"
                "新设置从下一次任务生效；键盘映射安全等待仍独立保留。",
                muted=True,
            )
        )
        self.mapping_wait = QSpinBox()
        self.mapping_wait.setRange(20, 250)
        self.mapping_wait.setSuffix(" 毫秒")
        self.mapping_wait.setValue(session.store.load_settings().x11_mapping_wait_ms)
        self._saved_mapping_wait = self.mapping_wait.value()
        self.mapping_wait.valueChanged.connect(self.save_mapping_wait)
        form.addRow("X11 键盘映射稳定等待", self.mapping_wait)
        self.feedback_timeout = QSpinBox()
        self.feedback_timeout.setRange(20, 250)
        self.feedback_timeout.setSuffix(" 毫秒")
        self.feedback_timeout.setValue(
            session.store.load_settings().x11_feedback_timeout_ms
        )
        self._saved_feedback_timeout = self.feedback_timeout.value()
        self.feedback_timeout.valueChanged.connect(self.save_feedback_timeout)
        form.addRow("X11 自适应反馈基准", self.feedback_timeout)
        layout.addLayout(form)
        layout.addWidget(
            label(
                "X11 首次映射固定等待 100 毫秒；设置的映射等待用于后续实际映射变化。"
                "绘制反馈仅用于原生 X11；Wayland（包括 XWayland）"
                "以及 Fcitx5、IBus 直接输出不使用。"
                "回退到原生 X11 键盘时可能使用；"
                "反馈基准受上方等待上限约束；仅供调度参考，不能确认文字已显示。新设置从下一次任务生效。",
                muted=True,
            )
        )
        layout.addWidget(
            label(
                "Fcitx5 需要额外安装输入桥；IBus 需要手动启用实验性 GNOME 扩展。"
                "自动模式优先使用检测与握手通过的 Fcitx5；也可使用下方单独安装、"
                "启用的 GNOME 自动输入扩展。扩展未安装或合法停用时保留原有自动策略。"
                "目标、扩展状态或预编辑无法确认时会停止，不盲目切换键盘；"
                "已尝试但未确认的文字不会重放。应用可能使用不同的输入方式。"
                "设置从下一次任务生效。",
                muted=True,
            )
        )
        self.body.addWidget(frame)
        extension_frame, extension_layout = card()
        extension_layout.addWidget(label("IBus 实验扩展"))
        extension_layout.addWidget(
            label(
                "仅在 GNOME 46 和 50 的隔离测试中验证；扩展使用 GNOME 私有接口，"
                "可能不兼容其他版本或应用。它不会切换输入法；只尝试提交，"
                "无法确认目标收到文字，目标未接入 IBus 时可能没有文字。"
                "安装、启用和停用均由下方按钮单独执行；安装后可能需要重新登录。"
                "如已安装旧版 InkEcho 实验扩展，请先在 GNOME 扩展管理器中"
                "停用并卸载旧版，"
                "再安装并启用新版；安装不会自动覆盖旧扩展。"
                "异常退出可能留下临时凭证文件。",
                muted=True,
            )
        )
        self.ibus_status = label("尚未检查扩展状态。")
        extension_layout.addWidget(self.ibus_status)
        extension_layout.addWidget(
            actions(
                button("安装实验扩展", lambda: self.run(self.ibus_action("install"))),
                button("启用实验扩展", lambda: self.run(self.ibus_action("enable"))),
                button("停用实验扩展", lambda: self.run(self.ibus_action("disable"))),
                button("检查扩展状态", lambda: self.run(self.ibus_action("status"))),
            )
        )
        self.body.addWidget(extension_frame)
        owned_frame, owned_layout = card()
        owned_layout.addWidget(label("自动方式的可选 GNOME 输入扩展"))
        owned_layout.addWidget(
            label(
                "与上方显式 IBus 的旧 V2 实验扩展分别管理；其协议保障不相同。"
                "安装和启用后，自动方式或所选「IBus（GNOME 新版扩展）」可使用此扩展；"
                "它不会切换输入法，也无法确认目标是否收到文字。"
                "本版本只使用带服务端期限的新协议；旧扩展需先停用并卸载，"
                "再安装匹配版本并重新登录桌面；仅停用再启用可能仍加载缓存代码。"
                "新版扩展拒绝旧客户端；请同时更新并重启 InkEcho。"
                "如不可用，请检查扩展状态或停用扩展后重新检查输入方式。",
                muted=True,
            )
        )
        self.owned_status = label("尚未检查扩展状态。")
        owned_layout.addWidget(self.owned_status)
        owned_layout.addWidget(
            actions(
                button(
                    "安装自动输入扩展", lambda: self.run(self.owned_action("install"))
                ),
                button(
                    "启用自动输入扩展", lambda: self.run(self.owned_action("enable"))
                ),
                button(
                    "停用自动输入扩展", lambda: self.run(self.owned_action("disable"))
                ),
                button(
                    "检查自动输入扩展", lambda: self.run(self.owned_action("status"))
                ),
            )
        )
        self.body.addWidget(owned_frame)
        fcitx_frame, fcitx_layout = card()
        fcitx_layout.addWidget(label("Fcitx5 实验输入桥"))
        fcitx_layout.addWidget(
            label(
                "仅限已验证的 Ubuntu 与 Fcitx5 版本。未安装 Fcitx5 时，"
                "请先通过系统软件管理器安装；如需使用，"
                "请在系统中选择 Fcitx5 并重新登录。"
                "安装到当前用户目录并发布加载配置；Fcitx5 重启后可能自动加载。"
                "启用会要求正在运行的 Fcitx5 重新检查插件。"
                "自动方式仅在检测到 Fcitx5 和已启用输入桥时尝试使用。"
                "停用只移除加载配置，"
                "已加载的插件会保留到 Fcitx5 退出，不会立即卸载。"
                "同一用户下的其他进程不构成安全隔离。",
                muted=True,
            )
        )
        self.fcitx_status = label("尚未检查输入桥状态。")
        fcitx_layout.addWidget(self.fcitx_status)
        fcitx_layout.addWidget(
            actions(
                button("安装输入桥", lambda: self.run(self.fcitx_action("install"))),
                button("启用输入桥", lambda: self.run(self.fcitx_action("enable"))),
                button("停用输入桥", lambda: self.run(self.fcitx_action("disable"))),
                button("检查输入桥", lambda: self.run(self.fcitx_action("status"))),
            )
        )
        self.body.addWidget(fcitx_frame)

        self.body.addWidget(
            actions(
                button("检查并启用所选方式", lambda: self.run(self.enable())),
                button("重新检查输入服务", lambda: self.run(self.recheck())),
            )
        )
        self.finish()
        self.refresh()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start()

    def save_receiver_wait(self):
        self._save_input_timing(
            self.receiver_wait, "receiver_feedback_wait_ms", "_saved_receiver_wait"
        )

    def save_mapping_wait(self):
        self._save_input_timing(
            self.mapping_wait, "x11_mapping_wait_ms", "_saved_mapping_wait"
        )

    def save_feedback_timeout(self):
        self._save_input_timing(
            self.feedback_timeout, "x11_feedback_timeout_ms", "_saved_feedback_timeout"
        )

    def _save_input_timing(self, widget, field, saved_attribute):
        from dataclasses import replace

        try:
            settings = self.session.store.load_settings()
            setattr(self, saved_attribute, getattr(settings, field))
            self.session.store.save_settings(
                replace(settings, **{field: widget.value()})
            )
            setattr(self, saved_attribute, widget.value())
            self.message.setText("输入设置已自动保存，将从下一次任务生效。")
        except (ValueError, OSError):
            # A write can fail after replacing the file; prefer the actual
            # readable value and otherwise retain the last known value.
            try:
                actual = getattr(self.session.store.load_settings(), field)
                setattr(self, saved_attribute, actual)
            except (ValueError, OSError):
                pass
            previous = widget.blockSignals(True)
            try:
                widget.setValue(getattr(self, saved_attribute))
            finally:
                widget.blockSignals(previous)
            self.message.setText("输入设置无法保存。")

    async def fcitx_action(self, operation):
        if (
            self.session.controller.task
            or self.session.preparing
            or self.session.testing
        ):
            self.message.setText("请先结束当前任务，再调整输入桥。")
            return
        try:
            async with self.fcitx_action_lock:
                if operation != "status":
                    await self.session.run_input_maintenance(
                        getattr(self.fcitx_installer, operation)
                    )
                try:
                    self.fcitx_status.setText(
                        await asyncio.to_thread(self.fcitx_installer.status)
                    )
                except FcitxInstallError as error:
                    if operation == "status":
                        raise
                    # The requested change has already succeeded. Report a
                    # failed follow-up check separately rather than implying
                    # that the installation or deactivation was rolled back.
                    self.fcitx_status.setText(f"状态检查失败：{error}")
            if operation == "disable":
                self.message.setText(
                    "加载配置已移除；已加载的插件会保留到 Fcitx5 退出。"
                )
            elif operation == "enable":
                self.message.setText("已请求 Fcitx5 检查插件，请检查输入服务状态。")
            elif operation == "install":
                self.message.setText(
                    "输入桥已安装；Fcitx5 重启后可能自动加载，"
                    "也可点击启用以请求立即检查。"
                )
            else:
                self.message.setText("输入桥状态已更新。")
        except InputMaintenanceBusy:
            self.message.setText("请先结束当前任务，再调整输入桥。")
        except FcitxInstallError as error:
            self.message.setText(str(error))

    async def ibus_action(self, operation):
        await self._run_ibus_action(self.ibus_extension, self.ibus_status, operation)

    async def owned_action(self, operation):
        await self._run_ibus_action(self.owned_extension, self.owned_status, operation)

    async def _run_ibus_action(self, manager, status, operation):
        if (
            self.session.controller.task
            or self.session.preparing
            or self.session.testing
        ):
            self.message.setText("请先结束当前任务，再调整扩展。")
            return
        try:
            async with self.ibus_action_lock:
                if operation != "status":
                    await self.session.run_input_maintenance(
                        getattr(manager, operation)
                    )
                try:
                    status.setText(await asyncio.to_thread(manager.status))
                except ExtensionError as error:
                    if operation == "status":
                        raise
                    # The change already ran; a failed follow-up inspection
                    # must not be presented as if the change was rolled back.
                    status.setText(f"状态检查失败：{error}")
                except Exception:
                    # Unexpected inspection failures are separate from the
                    # completed operation and may contain sensitive details.
                    status.setText("状态检查失败，请稍后重试。")
                    if operation == "status":
                        self.message.setText("状态检查失败，请稍后重试。")
                        return
            self.message.setText(
                "扩展操作已提交；请以扩展运行状态为准。"
                if operation != "status"
                else "扩展状态已更新。"
            )
        except InputMaintenanceBusy:
            self.message.setText("请先结束当前任务，再调整扩展。")
        except ExtensionError as error:
            if operation == "status":
                status.setText(f"状态检查失败：{error}")
            self.message.setText(str(error))

    def save_output_method(self):
        from dataclasses import replace

        try:
            settings = self.session.store.load_settings()
            self._saved_output_method = settings.output_method
            self.session.store.save_settings(
                replace(settings, output_method=self.output_method.currentData())
            )
            self._saved_output_method = self.output_method.currentData()
            self.message.setText("输入方式已保存，将从下一次任务生效。")
        except (ValueError, OSError):
            # A failing write can have replaced the file already; prefer the
            # readable on-disk value and otherwise keep the last known value.
            try:
                self._saved_output_method = (
                    self.session.store.load_settings().output_method
                )
            except (ValueError, OSError):
                pass
            previous = self.output_method.blockSignals(True)
            try:
                self.output_method.setCurrentIndex(
                    self.output_method.findData(self._saved_output_method)
                )
            finally:
                self.output_method.blockSignals(previous)
            self.message.setText("输入设置无法保存。")

    def refresh(self):
        status = getattr(self.session.inputs, "receiver_feedback_status", "not_checked")
        self.receiver_feedback.setText(
            {
                "not_checked": "绘制反馈：输出时检测当前接收窗口。",
                "available": "本次输出：可观察窗口绘制提示，不确认文字接收或显示。",
                "unsupported": "本次输出：此输入方式无绘制反馈，等待设置不生效。",
                "unavailable": "本次输出：当前窗口无可用绘制反馈，等待设置不生效。",
            }.get(status, "绘制反馈：当前能力未知，等待设置不生效。")
        )
        environment = detect_desktop()
        self.environment.setText(
            f"{environment.distribution} · {environment.desktop} "
            f"· {environment.session}"
        )
        native = getattr(self.session.inputs, "backend", None) == "gnome-wayland"
        self.scope.setText(
            "GNOME Wayland 实验性键盘输入：按输出时的焦点选择原生 Wayland "
            "或 XWayland 路径。可用性取决于桌面版本和目标应用；部分环境"
            "不支持原生 Wayland 输出。原生路径不支持 emoji 等扩展字符，"
            "含这些字符的结果会整段停止发送。输入前请松开按键并关闭大写锁定。"
            "未经实测的应用不保证兼容。"
            if native
            else "当前键盘输入方式面向 X11 / XWayland 应用，无需远程控制授权。"
            "此方式不支持原生 Wayland 应用；未经实测的应用不保证兼容。"
        )
        try:
            method = self.session.store.load_settings().output_method
        except (ValueError, OSError):
            self.availability.setText("输入设置无法读取，请检查配置文件。")
            return
        keyboard = getattr(self.session.inputs, "keyboard", self.session.inputs)
        keyboard_connected = getattr(keyboard, "connected", self.session.connected)
        keyboard_authorized = getattr(keyboard, "authorized", False)
        if method == "ibus-owned":
            text = (
                "只使用新版 GNOME IBus 扩展，适用于兼容的原生 Wayland 控件；"
                "X11 / XWayland 目标不适用。输出时检查实际目标、服务身份与协议。"
                "未安装、未启用或目标不兼容时停止，不回退其他方式；"
                "录音准备不校验目标，提交完成仍不代表目标确认接收。"
            )
        elif method == "ibus":
            text = "IBus 仅尝试提交；目标未接入时可能没有文字，无法自动确认接收。"
        elif method == "fcitx":
            text = "Fcitx5 输入桥将在任务开始时检查；未安装或未运行时无法输出。"
        elif method == "auto":
            text = (
                "自动模式在输出时检测可用的 Fcitx5 或 GNOME IBus 输入桥，"
                "不满足条件时可能使用键盘或停止；应用可能使用不同输入方式。"
            )
        elif not keyboard_connected:
            text = "键盘输入服务尚未连接。"
        elif keyboard_authorized:
            text = (
                "GNOME 键盘输入已启用；文字将发送到输出当时的光标位置。"
                if native
                else "键盘输入已启用；输出时请使用兼容的 X11 / XWayland 应用。"
            )
        else:
            text = "输入服务已连接，请点击「检查并启用所选方式」完成准备。"
        if environment.session == "x11" and method in {"auto", "keyboard"}:
            text += (
                " Xorg 下使用模拟键盘时可能中断正在进行的输入法组词；"
                "请先完成或取消组词再输出。"
            )
        elif environment.session == "x11" and method == "ibus":
            text += (
                " Xorg 下使用旧版 IBus 扩展时可能中断正在进行的输入法组词；"
                "请先完成或取消组词再输出。"
            )
        self.availability.setText(text)

    async def enable(self):
        if (
            self.session.controller.task
            or self.session.preparing
            or self.session.testing
        ):
            self.message.setText("请先结束当前任务，再调整键盘输入连接。")
            return
        try:
            enabled = await self.session.authorize_input()
            method = self.session.store.load_settings().output_method
        except (ValueError, OSError):
            self.availability.setText("输入设置无法读取，请检查配置文件。")
            self.message.setText("输入设置无法读取，请检查配置文件。")
            return
        self.refresh()
        if method == "ibus-owned":
            self.message.setText(
                "已保存本次准备；新版扩展身份与目标将在实际输出时验证，本次未输入文字。"
                if enabled
                else "新版扩展准备失败，请查看错误提示。"
            )
        elif method == "auto":
            keyboard = getattr(self.session.inputs, "keyboard", self.session.inputs)
            if enabled and getattr(keyboard, "authorized", False):
                self.message.setText(
                    "键盘已授权；自动方式将在输出时检测，目标兼容性尚未确认。"
                )
            else:
                self.message.setText(
                    "键盘未确认可用；自动方式将在输出时检测，当前尚未确认可用。"
                )
        else:
            self.message.setText(
                "所选输入方式已准备；此操作不会输入文字。"
                if enabled
                else "所选输入方式不可用，请查看错误提示。"
            )

    async def recheck(self):
        if not self.session.connected:
            await self.session.initialize()
        self.refresh()
        self.message.setText("已更新状态；此检查不会请求授权或输入文字。")


class StatisticsPage(Page):
    def __init__(self, session, stats):
        super().__init__("使用数据", "每日汇总与模型用量。")
        self.session, self.stats = session, stats
        frame, layout = card()
        self.summary = label("")
        layout.addWidget(self.summary)
        form = QFormLayout()
        names = {
            "recordings": "今日任务数",
            "succeeded": "已尝试发送任务数",
            "failed": "失败",
            "cancelled": "取消",
            "characters": "尝试发送字符数（Unicode 码点）",
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
        self.body.addWidget(
            actions(
                button("刷新", self.refresh),
                button("清除统计", lambda: self.run(self.clear_statistics())),
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

    async def clear_statistics(self):
        await asyncio.to_thread(self.stats.clear)
        self.refresh()
        self.message.setText("统计已清除；配置、凭据和日志保持不变。")


class LogsPage(Page):
    def __init__(self, session, log):
        super().__init__("诊断日志", "查看本地诊断记录。")
        self.session, self.log = session, log
        panel, body = card()
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMinimumHeight(240)
        self.logs.setPlaceholderText("暂无诊断记录")
        body.addWidget(self.logs)
        body.addWidget(
            actions(
                button("刷新", self.refresh),
                button("清除日志", lambda: self.run(self.clear_logs())),
            )
        )
        self.body.addWidget(panel)
        self.finish()
        self.refresh()

    def refresh(self):
        try:
            self.logs.setPlainText(self.log.recent())
        except OSError:
            self.logs.setPlainText("日志暂不可读取。")

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
        self.autostart_lock = asyncio.Lock()
        self.autostart_revision = 0
        frame, layout = card()
        layout.addWidget(label(f"InkEcho {__version__} · Linux 首期开发版"))
        self.location = label("")
        self.integration_status = label("")
        layout.addWidget(self.location)
        layout.addWidget(self.integration_status)
        layout.addWidget(
            label(
                "图标与启动器安装到当前用户目录。移动 AppImage 后可在此修复路径；"
                "移除桌面集成不会删除应用配置或 credentials.json 中的明文凭据。",
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
        self.finish()
        self.refresh()
        self.autostart.toggled.connect(self.queue_autostart)

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
        self.autostart.blockSignals(True)
        self.autostart.setChecked(status["autostart"])
        self.autostart.blockSignals(False)

    async def apply(self, operation):
        try:
            await asyncio.to_thread(operation)
            self.refresh()
            self.message.setText("桌面集成已更新。")
        except IntegrationError as error:
            self.message.setText(str(error))
            self.session.diagnostic.emit("integration_failed")

    def queue_autostart(self, enabled):
        self.autostart_revision += 1
        revision = self.autostart_revision
        self.run(self.save_autostart(enabled, revision))

    async def save_autostart(self, enabled=None, revision=None):
        if enabled is None:
            enabled = self.autostart.isChecked()
        if revision is None:
            self.autostart_revision += 1
            revision = self.autostart_revision
        async with self.autostart_lock:
            try:
                await asyncio.to_thread(self.integration.set_autostart, enabled)
            except IntegrationError:
                if revision == self.autostart_revision:
                    self.refresh()
                    self.message.setText("自启动设置未保存，已恢复实际状态。")
                self.session.diagnostic.emit("integration_failed")
                return
            if revision == self.autostart_revision:
                self.refresh()
                self.message.setText("自启动设置已自动保存。")
