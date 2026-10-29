"""Daily usage and selected models with bounded automatic account balances."""

import asyncio
import time
from dataclasses import replace
from html import escape

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QSizePolicy, QWidget

from inkecho.billing import BalanceResult, balance_platform, console_for_provider
from inkecho.security import CredentialError
from inkecho.ui.widgets import Page, card, label


class WeekChart(QWidget):
    def __init__(self):
        super().__init__()
        self.days = []
        self.setMinimumSize(240, 230)
        self.setAccessibleName("最近七天每日尝试发送字符")

    def set_days(self, days):
        self.days = days
        self.setToolTip(
            "\n".join(
                f"{day}：尝试发送 {values['characters']:,} 字符" for day, values in days
            )
        )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        maximum = max([values["characters"] for _, values in self.days] + [1])
        width = self.width() / 7
        tick_font = painter.font()
        tick_font.setPixelSize(12)
        painter.setFont(tick_font)
        for index, (day, values) in enumerate(self.days):
            count = values["characters"]
            x = int(index * width)
            height = int((self.height() - 62) * count / maximum)
            bar_width = max(8, int(width * 0.48))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#3971ca" if count else "#e5ecf8"))
            painter.drawRoundedRect(
                x + int((width - bar_width) / 2),
                self.height() - 30 - max(height, 3),
                bar_width,
                max(height, 3),
                5,
                5,
            )
            painter.setPen(QColor("#526782"))
            painter.drawText(
                x,
                self.height() - 24,
                int(width),
                24,
                Qt.AlignmentFlag.AlignCenter,
                day[8:] + "日",
            )
            painter.drawText(
                x,
                self.height() - 55 - height,
                int(width),
                24,
                Qt.AlignmentFlag.AlignCenter,
                painter.fontMetrics().elidedText(
                    str(count), Qt.TextElideMode.ElideRight, int(width) - 4
                ),
            )


class HomePage(Page):
    BALANCE_CACHE_SECONDS = 300

    def __init__(self, session, stats):
        super().__init__("概览", "把声音变成文字，让表达自然发生。")
        self.session, self.stats = session, stats
        self.revision = 0
        self.balance_signature = None
        self.balance_updated = None
        self.balance_task = None
        self.active = False
        self.balance_timer = QTimer(self)
        self.balance_timer.setInterval(self.BALANCE_CACHE_SECONDS * 1000)
        self.balance_timer.timeout.connect(self.schedule_balance)
        self.balance_schedule = QTimer(self)
        self.balance_schedule.setSingleShot(True)
        self.balance_schedule.timeout.connect(self.start_balance)
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(16)
        self.metrics = {}
        for key, caption in (
            ("characters", "今日尝试发送字符"),
            ("audio_seconds", "今日录音时长"),
            ("recordings", "今日使用次数"),
        ):
            tile, body = card()
            value = label("0")
            if key == "characters":
                value.setToolTip(
                    "按发送调用统计，不能确认目标收到；失败的部分可能未计入。"
                )
            value.setStyleSheet("font-size:28px; font-weight:600; color:#245ab1")
            body.addWidget(label(caption, muted=True))
            body.addWidget(value)
            self.metrics[key] = value
            metrics_row.addWidget(tile, 1)
        self.body.addLayout(metrics_row)
        columns = QHBoxLayout()
        columns.setSpacing(16)
        chart_card, chart_body = card()
        chart_body.addWidget(label("最近七天 · 每日尝试发送字符"))
        self.chart = WeekChart()
        chart_body.addWidget(self.chart, 1)
        self.outcomes = label("", muted=True)
        chart_body.addWidget(self.outcomes)
        columns.addWidget(chart_card, 1)
        models, model_body = card()
        model_body.addWidget(label("当前模型"))
        self.transcription = QComboBox()
        self.polishing = QComboBox()
        self.enabled = QCheckBox("使用云端润色")
        self.balance_labels = {}
        self.console_labels = {}
        for role, title, selector in (
            ("transcription", "语音模型", self.transcription),
            ("polishing", "润色模型", self.polishing),
        ):
            if role == "polishing":
                model_body.addWidget(self.enabled)
            heading = QHBoxLayout()
            heading.addWidget(label(title))
            status = label("余额未知", muted=True)
            status.setMinimumWidth(0)
            status.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
            )
            status.setTextFormat(Qt.TextFormat.PlainText)
            status.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            heading.addWidget(status, 1)
            model_body.addLayout(heading)
            selector.setMinimumWidth(0)
            selector.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            selector.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            model_body.addWidget(selector)
            console = label("", muted=True)
            console.setMinimumWidth(0)
            console.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
            )
            console.setOpenExternalLinks(True)
            model_body.addWidget(console)
            self.balance_labels[role] = status
            self.console_labels[role] = console
        model_body.addStretch()
        columns.addWidget(models, 1)
        self.body.addLayout(columns)
        self.transcription.currentIndexChanged.connect(self.selection_changed)
        self.polishing.currentIndexChanged.connect(self.selection_changed)
        self.enabled.toggled.connect(self.selection_changed)
        self.refresh()
        self.finish()

    def showEvent(self, event):
        super().showEvent(event)
        self.set_active(True)

    def hideEvent(self, event):
        self.set_active(False)
        super().hideEvent(event)

    def set_active(self, active):
        """Only the visible overview owns automatic read-only requests."""
        self.active = active
        if active:
            self.balance_timer.start()
            self.schedule_balance()
        else:
            self.balance_timer.stop()
            self.balance_schedule.stop()
            self.cancel_balance()

    def cancel_balance(self):
        self.revision += 1
        if self.balance_task is not None and not self.balance_task.done():
            self.balance_task.cancel()
        self.balance_task = None

    def schedule_balance(self):
        if self.active:
            self.balance_schedule.start(0)

    def start_balance(self):
        if not self.active:
            return
        # Qt can also display this page in a synchronous diagnostic/test process.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        if self.balance_task is not None and not self.balance_task.done():
            return
        if (
            self.balance_updated is not None
            and time.monotonic() - self.balance_updated < self.BALANCE_CACHE_SECONDS
            and self.balance_signature == self.configuration_signature()
        ):
            return
        self.balance_task = self.run(self.refresh_balance())

    def refresh(self):
        settings = self.session.store.load_settings()
        signature = self.configuration_signature()
        if signature != self.balance_signature:
            self.cancel_balance()
            self.balance_signature = signature
            self.balance_updated = None
            for role in self.balance_labels:
                self.balance_labels[role].setText("余额未知")
                self.console_labels[role].clear()
        for selector, kind, selected in (
            (self.transcription, "transcription", settings.transcription_provider),
            (self.polishing, "polishing", settings.polishing_provider),
        ):
            selector.blockSignals(True)
            selector.clear()
            selector.addItem("请先保存模型配置", "")
            for provider in self.session.store.providers():
                if provider.role == kind:
                    selector.addItem(
                        f"{provider.name} · {provider.model or '未选模型'}", provider.id
                    )
            selector.setCurrentIndex(max(0, selector.findData(selected)))
            selector.setToolTip(selector.currentText())
            selector.blockSignals(False)
        self.enabled.blockSignals(True)
        self.enabled.setChecked(settings.polishing_enabled)
        self.enabled.blockSignals(False)
        self.polishing.setEnabled(settings.polishing_enabled)
        self.balance_labels["polishing"].setEnabled(settings.polishing_enabled)
        self.console_labels["polishing"].setEnabled(settings.polishing_enabled)
        if not settings.polishing_enabled:
            self.balance_labels["polishing"].setText("未启用")
        day = self.stats.today()
        self.metrics["characters"].setText(f"{day['characters']:,}")
        self.metrics["audio_seconds"].setText(f"{day['audio_seconds'] / 60:.1f} 分钟")
        self.metrics["recordings"].setText(f"{day['recordings']} 次")
        self.outcomes.setText(
            f"今日尝试发送 {day['succeeded']} · 失败 {day['failed']} · "
            f"取消 {day['cancelled']}"
        )
        self.chart.set_days(self.stats.recent())
        self.schedule_balance()

    def selection_changed(self):
        self.cancel_balance()
        self.safe(
            lambda: self.session.store.save_settings(
                replace(
                    self.session.store.load_settings(),
                    transcription_provider=self.transcription.currentData() or "",
                    polishing_provider=self.polishing.currentData() or "",
                    polishing_enabled=self.enabled.isChecked(),
                )
            )
        )
        self.refresh()

    def configuration_signature(self):
        settings = self.session.store.load_settings()
        identifiers = [settings.transcription_provider]
        if settings.polishing_enabled:
            identifiers.append(settings.polishing_provider)
        providers = tuple(
            self.session.store.load_provider(identifier)
            for identifier in identifiers
            if identifier
        )
        try:
            info = (self.session.store.root / "credentials.json").stat()
            credential_revision = (info.st_mtime_ns, info.st_size)
        except FileNotFoundError:
            credential_revision = None
        return settings.polishing_enabled, providers, credential_revision

    async def refresh_balance(self):
        from inkecho.billing import fetch_balance

        self.revision += 1
        revision = self.revision
        signature = self.configuration_signature()
        settings = self.session.store.load_settings()
        selected = {"transcription": settings.transcription_provider}
        if settings.polishing_enabled:
            selected["polishing"] = settings.polishing_provider
        results = {}
        for role, identifier in selected.items():
            if not identifier:
                self.balance_labels[role].setText("未选择配置")
                continue
            provider = self.session.store.load_provider(identifier)
            self.balance_labels[role].setText("余额查询中…")
            platform = balance_platform(provider)
            try:
                # Includes credential loading: a stuck key source cannot hang the page.
                async with asyncio.timeout(12):
                    key = await self.session.key(provider.key_ref) if platform else ""
                    if (
                        revision != self.revision
                        or signature != self.configuration_signature()
                    ):
                        return
                    result = await fetch_balance(platform, key)
            except asyncio.CancelledError:
                if revision == self.revision:
                    self.balance_labels[role].setText("余额未知")
                raise
            except (CredentialError, ValueError, OSError, TimeoutError):
                result = BalanceResult(
                    "error", "无法读取当前配置凭据或余额，请检查配置。"
                )
            if revision != self.revision or signature != self.configuration_signature():
                return
            results[role] = (
                provider.name,
                replace(result, console_url=console_for_provider(provider)),
            )
        if revision != self.revision or signature != self.configuration_signature():
            return
        for role, (name, result) in results.items():
            amounts = " · ".join(
                f"{amount.currency} 余额 {amount.total}" for amount in result.balances
            )
            caption = amounts or (
                "余额未知" if result.status == "unsupported" else result.message
            )
            if result.is_available is False:
                caption += " · 账户当前不可用"
            elif result.is_available is True:
                caption += " · 账户可用"
            self.balance_labels[role].setText(caption)
            self.balance_labels[role].setToolTip(result.message)
            self.console_labels[role].setText(
                f'<a href="{escape(result.console_url, quote=True)}">'
                f"{escape(name)} 控制台</a>"
                if result.console_url
                else "无可用的余额接口或官方控制台入口"
            )
        self.balance_signature = signature
        self.balance_updated = time.monotonic()
