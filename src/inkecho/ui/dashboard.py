"""Numeric-only overview with explicit model selection and balance refresh."""

import asyncio
from dataclasses import replace
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QWidget,
)

from inkecho.billing import BalanceResult, console_for_provider
from inkecho.security import CredentialError
from inkecho.ui.widgets import Page, actions, button, card, label


class WeekChart(QWidget):
    def __init__(self):
        super().__init__()
        self.days = []
        self.setMinimumHeight(140)
        self.setAccessibleName("最近七天每日录音次数")

    def set_days(self, days):
        self.days = days
        self.setToolTip(
            "\n".join(f"{day}：{values['recordings']} 次" for day, values in days)
        )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        maximum = max([values["recordings"] for _, values in self.days] + [1])
        width = self.width() / 7
        for index, (day, values) in enumerate(self.days):
            count = values["recordings"]
            x = int(index * width)
            height = int((self.height() - 58) * count / maximum)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#3971ca" if count else "#e5ecf8"))
            painter.drawRoundedRect(
                x + 18,
                self.height() - 30 - max(height, 3),
                int(width - 36),
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
                day[5:],
            )
            painter.drawText(
                x,
                self.height() - 55 - height,
                int(width),
                24,
                Qt.AlignmentFlag.AlignCenter,
                str(count),
            )


class HomePage(Page):
    def __init__(self, session, stats):
        super().__init__("概览", "把声音变成文字，让表达自然发生。")
        self.session, self.stats = session, stats
        self.revision = 0
        self.balance_signature = None
        metrics, layout = card()
        self.summary = label("")
        self.summary.hide()
        layout.addWidget(self.summary)
        metrics_row = QHBoxLayout()
        self.metrics = {}
        for key, caption in (
            ("characters", "今日已发送字符"),
            ("audio_seconds", "今日录音时长"),
            ("recordings", "今日使用次数"),
        ):
            tile, tile_body = card()
            tile_body.setContentsMargins(14, 10, 14, 10)
            value = label("0")
            value.setStyleSheet("font-size:25px; font-weight:600; color:#245ab1")
            tile_body.addWidget(value)
            tile_body.addWidget(label(caption, muted=True))
            self.metrics[key] = value
            metrics_row.addWidget(tile)
        layout.addLayout(metrics_row)
        self.outcomes = label("", muted=True)
        layout.addWidget(self.outcomes)
        layout.addWidget(label("最近七天 · 每日录音次数", muted=True))
        self.chart = WeekChart()
        layout.addWidget(self.chart)
        self.body.addWidget(metrics)
        models, layout = card()
        form = QFormLayout()
        self.transcription = QComboBox()
        self.polishing = QComboBox()
        self.enabled = QCheckBox("使用云端润色")
        form.addRow("语音模型配置", self.transcription)
        form.addRow(self.enabled)
        form.addRow("润色模型配置", self.polishing)
        layout.addLayout(form)
        self.transcription.currentIndexChanged.connect(self.selection_changed)
        self.polishing.currentIndexChanged.connect(self.selection_changed)
        self.enabled.toggled.connect(self.selection_changed)
        self.balance = label("余额未知 · 点击刷新查询支持的平台", muted=True)
        self.balance.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.balance)
        layout.addWidget(
            actions(
                button("刷新 API 计费状态", lambda: self.run(self.refresh_balance()))
            )
        )
        self.console = label("")
        self.console.setOpenExternalLinks(True)
        layout.addWidget(self.console)
        self.body.insertWidget(2, models)
        self.body.addWidget(
            label(
                "字符按 Unicode 码点计数。统计仅保留数字，不保存录音或识别正文。"
                "云端处理会上传录音或文本。",
                muted=True,
            )
        )
        self.refresh()
        self.finish()

    def refresh(self):
        settings = self.session.store.load_settings()
        signature = self.configuration_signature()
        if signature != self.balance_signature:
            self.revision += 1
            self.balance_signature = signature
            self.balance.setText("当前模型的余额未知 · 点击刷新查询")
            self.console.clear()
        for selector, kind, selected in (
            (self.transcription, "transcription", settings.transcription_provider),
            (self.polishing, "polishing", settings.polishing_provider),
        ):
            selector.blockSignals(True)
            selector.clear()
            selector.addItem("请先保存模型配置", "")
            for provider in self.session.store.providers():
                if provider.role != kind:
                    continue
                selector.addItem(
                    f"{provider.name} · {provider.model or '未选模型'}", provider.id
                )
            selector.setCurrentIndex(max(0, selector.findData(selected)))
            selector.blockSignals(False)
        self.enabled.blockSignals(True)
        self.enabled.setChecked(settings.polishing_enabled)
        self.enabled.blockSignals(False)
        self.polishing.setEnabled(settings.polishing_enabled)
        day = self.stats.today()
        tokens = day["total_tokens"]
        token_text = str(tokens) if tokens is not None else "未知（平台未提供完整用量）"
        self.summary.setText(
            f"今日已发送 {day['characters']:,} 字符    ·    "
            f"录音 {day['audio_seconds'] / 60:.1f} 分钟    ·    "
            f"使用 {day['recordings']} 次\n"
            f"成功 {day['succeeded']}    失败 {day['failed']}    "
            f"取消 {day['cancelled']}\n"
            f"润色 Token：{token_text}"
        )
        self.metrics["characters"].setText(f"{day['characters']:,}")
        self.metrics["audio_seconds"].setText(f"{day['audio_seconds'] / 60:.1f} 分钟")
        self.metrics["recordings"].setText(f"{day['recordings']} 次")
        self.outcomes.setText(
            f"成功 {day['succeeded']} · 失败 {day['failed']} · 取消 {day['cancelled']}"
            f"  |  润色 Token：{token_text}"
        )
        self.chart.set_days(self.stats.recent())

    def selection_changed(self):
        self.revision += 1
        self.polishing.setEnabled(self.enabled.isChecked())
        self.balance.setText("当前模型的余额未知 · 点击刷新查询")
        self.console.clear()
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
        return (settings.polishing_enabled, providers, credential_revision)

    async def refresh_balance(self):
        expected = self.revision + 1
        try:
            await self._refresh_balance()
        except asyncio.CancelledError:
            if self.revision == expected:
                self.balance.setText("余额查询已取消，点击刷新重试。")
            raise
        except (CredentialError, ValueError, OSError):
            if self.revision == expected:
                self.balance.setText("配置暂不可读取，请检查配置后重新刷新。")

    async def _refresh_balance(self):
        from inkecho.billing import fetch_balance

        self.revision += 1
        revision = self.revision
        signature = self.configuration_signature()
        self.balance.setText("正在刷新当前模型计费状态……")
        results = []
        ids = [self.transcription.currentData()]
        if self.enabled.isChecked():
            ids.append(self.polishing.currentData())
        for identifier in dict.fromkeys(ids):
            if not identifier:
                continue
            provider = self.session.store.load_provider(identifier)
            # Only an explicit click reads credentials; unsupported platforms need none.
            platform = ""
            platform = (
                "deepseek"
                if provider.adapter == "openai"
                and provider.base_url.rstrip("/")
                in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}
                else platform
            )
            try:
                key = (
                    await self.session.key(provider.key_ref)
                    if platform == "deepseek"
                    else ""
                )
                result = await fetch_balance(platform, key)
            except (CredentialError, ValueError, OSError):
                result = BalanceResult(
                    "error", "无法读取当前配置凭据，请重新保存后刷新。"
                )
            results.append(
                (
                    provider.name,
                    replace(result, console_url=console_for_provider(provider)),
                )
            )
        if revision != self.revision or signature != self.configuration_signature():
            return
        self.balance.setText(
            "\n".join(
                f"{name}：{result.message}"
                + (
                    " · 账户可用"
                    if result.is_available is True
                    else " · 账户当前不可用"
                    if result.is_available is False
                    else ""
                )
                + "".join(
                    f"  {amount.currency} 余额 {amount.total}"
                    for amount in result.balances
                )
                for name, result in results
            )
            or "请先保存模型配置。"
        )
        self.console.setText(
            "  ".join(
                f'<a href="{result.console_url}">{escape(name)} 控制台</a>'
                for name, result in results
                if result.console_url
            )
        )
