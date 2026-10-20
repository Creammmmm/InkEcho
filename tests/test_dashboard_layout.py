"""Isolated overview layout and automatic balance lifecycle; no real services."""

import asyncio
from dataclasses import replace

import pytest
from PySide6.QtWidgets import QPushButton
from synthetic_providers import SYNTHETIC_PROVIDERS

from inkecho.app import Session
from inkecho.billing import BalanceResult
from inkecho.config import ConfigStore
from inkecho.statistics import Statistics
from inkecho.ui.dashboard import HomePage


@pytest.fixture
def home(tmp_path, qt_app):
    store = ConfigStore(tmp_path / "config")
    store.initialize()
    for provider in SYNTHETIC_PROVIDERS:
        store.save_provider(provider)
    store.save_settings(
        replace(
            store.load_settings(),
            transcription_provider="qwen",
            polishing_provider="deepseek",
            polishing_enabled=True,
        )
    )
    session = Session(store)
    page = HomePage(session, Statistics(tmp_path / "stats.json"))
    yield page
    page.set_active(False)
    page.close()
    session.timer.stop()
    asyncio.run(session.inputs.aclose())


def test_daily_metric_row_and_character_histogram(home):
    home.stats.record("succeeded", characters=213, audio_seconds=90)
    home.refresh()
    assert home.body.itemAt(2).layout().count() == 3
    assert home.body.itemAt(3).layout().count() == 2
    assert home.metrics["characters"].text() == "213"
    assert home.chart.days[-1][1]["characters"] == 213
    assert "213 字符" in home.chart.toolTip()
    assert "每日发送字符" in home.chart.accessibleName()
    assert not home.findChildren(QPushButton)


def test_visible_balance_cache_and_configuration_invalidation(home, monkeypatch):
    calls, keys = [], []

    async def balance(platform, key):
        calls.append(platform)
        return BalanceResult("unsupported", "余额未知")

    async def key(reference):
        keys.append(reference)
        return "synthetic"

    monkeypatch.setattr("inkecho.billing.fetch_balance", balance)
    monkeypatch.setattr(home.session, "key", key)

    async def scenario():
        home.set_active(True)
        home.start_balance()
        await home.balance_task
        assert calls == ["", "deepseek"]
        assert len(keys) == 1
        home.start_balance()
        assert home.balance_task.done()
        assert calls == ["", "deepseek"]
        # Credential replacement invalidates the cache without storing key contents.
        path = home.session.store.root / "credentials.json"
        path.touch()
        home.start_balance()
        await home.balance_task
        assert calls == ["", "deepseek", "", "deepseek"]
        home.balance_updated -= home.BALANCE_CACHE_SECONDS + 1
        home.start_balance()
        await home.balance_task
        assert len(calls) == 6
        home.set_active(False)
        assert not home.balance_timer.isActive()
        assert not home.balance_schedule.isActive()
        home.start_balance()
        assert home.balance_task is None

    asyncio.run(scenario())


def test_leaving_overview_cancels_without_applying_stale_balance(home, monkeypatch):
    async def scenario():
        entered = asyncio.Event()
        cancelled = asyncio.Event()

        async def balance(platform, key):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        monkeypatch.setattr("inkecho.billing.fetch_balance", balance)
        home.set_active(True)
        home.start_balance()
        task = home.balance_task
        await entered.wait()
        home.set_active(False)
        await task
        assert cancelled.is_set()
        assert home.balance_updated is None
        assert home.balance_labels["transcription"].text() != "OLD BALANCE"
        assert not home.balance_timer.isActive()

    asyncio.run(scenario())


def test_disabled_polishing_never_reads_its_key(home, monkeypatch):
    calls = []

    async def balance(platform, key):
        calls.append(platform)
        return BalanceResult("unsupported", "余额未知")

    async def forbidden(reference):
        raise AssertionError("disabled polishing must not read credentials")

    monkeypatch.setattr("inkecho.billing.fetch_balance", balance)
    monkeypatch.setattr(home.session, "key", forbidden)
    home.enabled.setChecked(False)
    asyncio.run(home.refresh_balance())
    assert calls == [""]
    assert home.balance_labels["polishing"].text() == "未启用"
    assert not home.polishing.isEnabled()
    assert "aliyun.com" in home.console_labels["transcription"].text()


def test_narrow_overview_wraps_long_balances_without_horizontal_growth(home, qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QScrollArea

    from inkecho.ui.widgets import STYLE

    home.setStyleSheet(STYLE)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.resize(720, 700)  # 940px main window minus 220px navigation.
    scroll.setWidget(home)
    for status in home.balance_labels.values():
        status.setText("USD 余额 12345678901234567890.123456789 · 账户当前不可用")
    for console in home.console_labels.values():
        console.setText("无法读取当前配置凭据或余额，请检查配置。")
    scroll.show()
    qt_app.processEvents()
    assert scroll.horizontalScrollBar().maximum() == 0
    assert home.width() <= scroll.viewport().width()
    for status in home.balance_labels.values():
        assert status.wordWrap()
        assert status.height() >= status.fontMetrics().height()
    canvas = QPixmap(home.chart.size())
    canvas.fill(Qt.GlobalColor.transparent)
    home.chart.render(canvas)
    assert not canvas.isNull()
    assert home.chart.days[-1][0] in home.chart.toolTip()
    # Detach the fixture-owned widget before its temporary scroll owner is destroyed.
    scroll.takeWidget()
    home.setParent(None)
    scroll.close()
