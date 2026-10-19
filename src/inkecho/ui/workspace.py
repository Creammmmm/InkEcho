"""Five-page workspace groups existing independent editors without data loss."""

from dataclasses import replace

from PySide6.QtWidgets import QCheckBox, QFormLayout, QSpinBox, QTabWidget

from inkecho import __version__
from inkecho.ui.information import AboutPage, CompatibilityPage, StatisticsPage
from inkecho.ui.providers import ProviderPage
from inkecho.ui.settings import AppearancePage, RecordingPage
from inkecho.ui.widgets import Page, actions, button, card, label


def embed_editor(page):
    """Use the parent page heading; keep the independent form compact."""
    for index in (0, 1):
        widget = page.body.itemAt(index).widget()
        if widget:
            widget.hide()
    page.body.setContentsMargins(12, 16, 12, 12)
    page.body.setSpacing(12)
    return page


class ModelsPage(Page):
    def __init__(self, session):
        super().__init__(
            "模型配置",
            "分别保存语音识别与文字润色配置。首次使用请填写名称、模型与认证信息。",
        )
        self.session = session
        self.tabs = QTabWidget()
        self.transcription = embed_editor(ProviderPage(session, "transcription"))
        self.polishing = embed_editor(ProviderPage(session, "polishing"))
        self.tabs.addTab(self.transcription, "语音模型")
        self.tabs.addTab(self.polishing, "润色模型")
        self.body.addWidget(self.tabs)
        self.finish()
        self.refresh()

    def refresh(self):
        self.polishing.setEnabled(self.session.store.load_settings().polishing_enabled)


class SettingsPage(Page):
    def __init__(self, session, stats, log, integration, command, preview):
        super().__init__("设置", "录音、快捷键、外观与输入兼容性集中管理。")
        self.session = session
        panel, body = card()
        form = QFormLayout()
        settings = session.store.load_settings()
        self.transcription_timeout = QSpinBox()
        self.polishing_timeout = QSpinBox()
        for widget, value in (
            (self.transcription_timeout, settings.transcription_timeout_seconds),
            (self.polishing_timeout, settings.polishing_timeout_seconds),
        ):
            widget.setRange(5, 120)
            widget.setSuffix(" 秒")
            widget.setValue(value)
        form.addRow("转写请求超时", self.transcription_timeout)
        form.addRow("润色请求超时", self.polishing_timeout)
        self.polishing_enabled = QCheckBox("使用云端润色")
        self.polishing_enabled.setChecked(settings.polishing_enabled)
        self.polishing_enabled.toggled.connect(self.toggle_polishing)
        form.addRow(self.polishing_enabled)
        self.streaming = QCheckBox("边润色边输入")
        self.streaming.setChecked(settings.polishing_streaming)
        self.fallback = QCheckBox("润色失败时使用原始识别文本")
        self.fallback.setChecked(settings.polishing_fallback)
        form.addRow(self.streaming)
        form.addRow(self.fallback)
        body.addLayout(form)
        body.addWidget(
            button("保存请求设置", lambda: self.safe(self.save), primary=True)
        )
        self.body.addWidget(panel)
        self.tabs = QTabWidget()
        self.recording = RecordingPage(session, command)
        self.appearance = AppearancePage(session, preview)
        self.compatibility = CompatibilityPage(session)
        self.statistics = StatisticsPage(session, stats, log)
        self.integration = AboutPage(session, integration)
        for name, page in (
            ("录音与快捷键", self.recording),
            ("显示与悬浮提示", self.appearance),
            ("输入兼容性", self.compatibility),
            ("数据与日志", self.statistics),
            ("启动与桌面", self.integration),
        ):
            self.tabs.addTab(embed_editor(page), name)
        self.body.addWidget(self.tabs)
        self.finish()
        self.refresh()

    def toggle_polishing(self, enabled):
        self.polishing_timeout.setEnabled(enabled)
        self.streaming.setEnabled(enabled)
        self.fallback.setEnabled(enabled)
        self.safe(
            lambda: self.session.store.save_settings(
                replace(self.session.store.load_settings(), polishing_enabled=enabled)
            )
        )

    def save(self):
        self.session.store.save_settings(
            replace(
                self.session.store.load_settings(),
                transcription_timeout_seconds=self.transcription_timeout.value(),
                polishing_timeout_seconds=self.polishing_timeout.value(),
                polishing_enabled=self.polishing_enabled.isChecked(),
                close_to_tray=True,
                polishing_streaming=self.streaming.isChecked(),
                polishing_fallback=self.fallback.isChecked(),
            )
        )
        self.message.setText("请求设置已保存。")

    def refresh(self):
        settings = self.session.store.load_settings()
        self.polishing_enabled.blockSignals(True)
        self.polishing_enabled.setChecked(settings.polishing_enabled)
        self.polishing_enabled.blockSignals(False)
        self.polishing_timeout.setEnabled(settings.polishing_enabled)
        self.streaming.setEnabled(settings.polishing_enabled)
        self.fallback.setEnabled(settings.polishing_enabled)


class HelpPage(Page):
    def __init__(self, session):
        super().__init__("帮助", "版本信息、升级检查与使用说明。")
        self.session = session
        panel, body = card()
        body.addWidget(label(f"InkEcho {__version__}"))
        body.addWidget(
            label("Linux 开源语音输入 · 不使用剪贴板或系统输入法", muted=True)
        )
        self.update_status = label(
            "仅在点击后连接 GitHub 检查正式版，不自动下载或安装。", muted=True
        )
        body.addWidget(self.update_status)
        self.update_button = button(
            "检查更新", lambda: self.run(self.check_update()), primary=True
        )
        body.addWidget(actions(self.update_button))
        self.release = label(
            '<a href="https://github.com/Creammmmm/InkEcho/releases">查看发布与下载</a>'
        )
        self.release.setOpenExternalLinks(True)
        body.addWidget(self.release)
        self.body.addWidget(panel)
        self.body.addWidget(
            label(
                "使用方法：先在模型配置中保存语音模型和认证信息，在设置中启用快捷键与键盘输入。按快捷键录音，再按一次结束。输出时把光标放在希望接收文字的位置。"
            )
        )
        self.body.addWidget(
            label(
                "关闭窗口会隐藏到托盘；桌面不支持托盘时保留最小化入口。"
                "可通过应用启动器再次打开。退出可使用托盘菜单或命令行 --quit。",
                muted=True,
            )
        )
        self.body.addWidget(
            label(
                "API 凭据以明文保存在配置目录 credentials.json，目录0700、文件0600。"
                "不保存录音或识别正文。Ubuntu 24.04 GNOME 46 "
                "原生 Wayland 键盘输入不支持；"
                "实际支持范围请参阅项目兼容性文档。",
                muted=True,
            )
        )
        self.finish()

    async def check_update(self):
        from inkecho.updates import check_for_update

        self.update_button.setEnabled(False)
        self.update_status.setText("正在检查 GitHub 最新正式版……")
        try:
            result = await check_for_update(__version__)
            self.update_status.setText(result.message)
            if result.release_url:
                self.release.setText(
                    f'<a href="{result.release_url}">'
                    f"查看 {result.latest_version} 发布详情</a>"
                )
        finally:
            self.update_button.setEnabled(True)
