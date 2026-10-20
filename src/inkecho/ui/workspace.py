"""Five-page workspace groups existing independent editors without data loss."""

from dataclasses import replace

from PySide6.QtWidgets import QCheckBox, QFormLayout, QSpinBox, QTabWidget

from inkecho import __version__
from inkecho.ui.information import (
    AboutPage,
    CompatibilityPage,
    LogsPage,
    StatisticsPage,
)
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
    def __init__(self, session, stats, log, integration, command):
        super().__init__("设置", "录音、快捷键、外观与输入兼容性集中管理。")
        self.session = session
        self.tabs = QTabWidget()
        self.requests = Page("识别与润色", "选择处理方式与请求等待时间。")
        panel, body = card()
        settings = session.store.load_settings()
        self.polishing_enabled = QCheckBox("使用云端润色")
        self.polishing_enabled.setChecked(settings.polishing_enabled)
        self.streaming = QCheckBox("边润色边输入")
        self.streaming.setChecked(settings.polishing_streaming)
        self.fallback = QCheckBox("润色失败时使用原始识别文本")
        self.fallback.setChecked(settings.polishing_fallback)
        for widget in (self.polishing_enabled, self.streaming, self.fallback):
            body.addWidget(widget)
        form = QFormLayout()
        self.transcription_timeout = QSpinBox()
        self.polishing_timeout = QSpinBox()
        for widget, value in (
            (self.transcription_timeout, settings.transcription_timeout_seconds),
            (self.polishing_timeout, settings.polishing_timeout_seconds),
        ):
            widget.setRange(5, 120)
            widget.setSuffix(" 秒")
            widget.setValue(value)
            widget.valueChanged.connect(lambda: self.safe(self.save))
        form.addRow("转写请求超时", self.transcription_timeout)
        form.addRow("润色请求超时", self.polishing_timeout)
        body.addLayout(form)
        self.requests.body.addWidget(panel)
        self.requests.finish()
        self.polishing_enabled.toggled.connect(self.toggle_polishing)
        self.streaming.toggled.connect(lambda: self.safe(self.save))
        self.fallback.toggled.connect(lambda: self.safe(self.save))
        self.recording = RecordingPage(session, command)
        self.appearance = AppearancePage(session)
        self.compatibility = CompatibilityPage(session)
        self.statistics = StatisticsPage(session, stats)
        self.logs = LogsPage(session, log)
        self.integration = AboutPage(session, integration)
        for name, page in (
            ("识别与润色", self.requests),
            ("录音与快捷键", self.recording),
            ("悬浮提示", self.appearance),
            ("输入兼容性", self.compatibility),
            ("数据", self.statistics),
            ("日志", self.logs),
            ("桌面集成", self.integration),
        ):
            self.tabs.addTab(embed_editor(page), name)
        self.body.addWidget(self.tabs)
        self.finish()
        self.refresh()

    def toggle_polishing(self, enabled):
        self.polishing_timeout.setEnabled(enabled)
        self.streaming.setEnabled(enabled)
        self.fallback.setEnabled(enabled)
        self.safe(self.save)

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
        self.requests.message.setText("已自动保存。")

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
        from inkecho.platform.capabilities import detect_desktop

        environment = detect_desktop()
        session_name = {"wayland": "Wayland", "x11": "X11"}.get(
            environment.session, "会话未知"
        )
        desktop = environment.desktop.replace(":", " · ")
        body.addWidget(
            label(
                f"{environment.distribution} · {desktop} · {session_name}", muted=True
            )
        )
        self.update_status = label("", muted=True)
        self.update_button = button(
            "检查更新", lambda: self.run(self.check_update()), primary=True
        )
        self.release = label(
            '<a href="https://github.com/Creammmmm/InkEcho/releases">查看发布与下载</a>'
        )
        self.release.setOpenExternalLinks(True)
        body.addWidget(actions(self.update_button, self.release))
        body.addWidget(self.update_status)
        self.body.addWidget(panel)
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
