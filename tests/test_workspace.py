"""Five-page behavior using isolated configuration, no cloud or real credentials."""

import asyncio
import sys
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from PySide6.QtWidgets import QPushButton

from inkecho.app import Session
from inkecho.billing import BalanceAmount, BalanceResult
from inkecho.config import DEFAULT_PROVIDERS, ConfigStore
from inkecho.integration import DesktopIntegration
from inkecho.logging import DiagnosticLog
from inkecho.security import CredentialError
from inkecho.statistics import Statistics
from inkecho.ui.window import MainWindow


@pytest.fixture
def workspace(tmp_path, qt_app, monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setattr("inkecho.audio.Recorder.devices", lambda: [])
    store = ConfigStore(tmp_path / "config")
    store.initialize()
    session = Session(store)
    stats = Statistics(tmp_path / "statistics.json")
    log = DiagnosticLog(tmp_path / "data")
    integration = DesktopIntegration(
        Path(sys.executable),
        data_home=tmp_path / "desktop",
        config_home=tmp_path / "autostart",
    )
    window = MainWindow(
        session, stats, log, integration, [sys.executable, "-m", "inkecho"]
    )
    window.tray.hide()
    yield window
    window.dispose()
    session.timer.stop()
    asyncio.run(session.inputs.aclose())
    log.close()


def test_blank_five_page_workspace_preserves_empty_configuration(workspace):
    assert [workspace.navigation.item(i).text() for i in range(5)] == [
        "概览",
        "模型配置",
        "风格",
        "设置",
        "帮助",
    ]
    assert len(workspace.pages) == 5
    assert workspace.session.store.providers() == []
    assert workspace.home.transcription.currentData() == ""
    assert not workspace.home.polishing.isEnabled()
    assert not workspace.models_page.polishing.isEnabled()
    assert not workspace.settings_page.polishing_timeout.isEnabled()
    assert not any(
        button.text() == "退出 InkEcho"
        for button in workspace.findChildren(QPushButton)
    )
    workspace.models_page.transcription.new()
    assert workspace.models_page.transcription.name.text() == ""
    assert workspace.models_page.transcription.preset.currentIndex() == -1


def test_polishing_switch_and_timeout_use_current_settings(workspace):
    workspace.home.enabled.setChecked(True)
    workspace.models_page.refresh()
    workspace.settings_page.refresh()
    assert workspace.models_page.polishing.isEnabled()
    assert workspace.settings_page.polishing_timeout.isEnabled()
    workspace.settings_page.transcription_timeout.setValue(45)
    workspace.settings_page.polishing_timeout.setValue(55)
    workspace.settings_page.save()
    settings = workspace.session.store.load_settings()
    assert settings.transcription_timeout_seconds == 45
    assert settings.polishing_timeout_seconds == 55
    workspace.settings_page.polishing_enabled.setChecked(False)
    workspace.home.refresh()
    assert not workspace.home.polishing.isEnabled()
    assert not workspace.settings_page.streaming.isEnabled()
    assert not workspace.settings_page.fallback.isEnabled()


def test_weekly_statistics_zero_fill_and_chart(workspace):
    workspace.stats.record("succeeded", characters=12, audio_seconds=90)
    days = workspace.stats.recent()
    assert len(days) == 7
    assert days[0][0] == (date.today() - timedelta(days=6)).isoformat()
    assert days[-1][1]["characters"] == 12
    assert all(values["recordings"] == 0 for _, values in days[:-1])
    days[-1][1]["characters"] = 900
    assert workspace.stats.today()["characters"] == 12
    workspace.home.refresh()
    assert "12 字符" in workspace.home.summary.text()
    assert "1.5 分钟" in workspace.home.summary.text()
    assert len(workspace.home.chart.days) == 7


def test_close_without_tray_keeps_recoverable_window(workspace, qt_app):
    workspace.show()
    workspace.close()
    qt_app.processEvents()
    assert workspace.isVisible()
    assert workspace.isMinimized()
    workspace.show_window()
    assert not workspace.isMinimized()


def seed_models(workspace):
    for provider in DEFAULT_PROVIDERS:
        workspace.session.store.save_provider(provider)
    workspace.session.store.save_settings(
        replace(
            workspace.session.store.load_settings(),
            transcription_provider="qwen",
            polishing_provider="deepseek",
            polishing_enabled=True,
        )
    )
    workspace.home.refresh()


@pytest.mark.parametrize(
    "available, caption", [(True, "账户可用"), (False, "账户当前不可用")]
)
def test_balance_only_reads_official_platform_and_shows_amount(
    workspace, monkeypatch, available, caption
):
    seed_models(workspace)
    keys, requests = [], []

    async def key(reference):
        keys.append(reference)
        return "synthetic"

    async def balance(platform, supplied):
        requests.append((platform, supplied))
        return BalanceResult(
            "ok",
            "账户余额",
            (BalanceAmount("CNY", "12.50", "0", "12.50"),),
            is_available=available,
        )

    monkeypatch.setattr(workspace.session, "key", key)
    monkeypatch.setattr("inkecho.billing.fetch_balance", balance)
    asyncio.run(workspace.home.refresh_balance())
    assert len(keys) == 1
    assert requests == [("", ""), ("deepseek", "synthetic")]
    assert "CNY 余额 12.50" in workspace.home.balance.text()
    assert caption in workspace.home.balance.text()


def test_late_balance_does_not_leak_into_changed_configuration(workspace, monkeypatch):
    seed_models(workspace)

    async def key(reference):
        return "synthetic"

    async def scenario():
        entered, finish = asyncio.Event(), asyncio.Event()

        async def balance(platform, supplied):
            entered.set()
            await finish.wait()
            return BalanceResult("ok", "OLD BALANCE")

        monkeypatch.setattr("inkecho.billing.fetch_balance", balance)
        task = asyncio.create_task(workspace.home.refresh_balance())
        await entered.wait()
        workspace.home.enabled.setChecked(False)
        finish.set()
        await task
        assert "OLD BALANCE" not in workspace.home.balance.text()

    monkeypatch.setattr(workspace.session, "key", key)
    asyncio.run(scenario())


def test_missing_balance_key_does_not_leave_loading_or_stop_other_platform(
    workspace, monkeypatch
):
    seed_models(workspace)
    calls = []

    async def missing(reference):
        raise CredentialError("synthetic secret text must not escape")

    async def balance(platform, supplied):
        calls.append(platform)
        return BalanceResult("unsupported", "余额未知")

    monkeypatch.setattr(workspace.session, "key", missing)
    monkeypatch.setattr("inkecho.billing.fetch_balance", balance)
    asyncio.run(workspace.home.refresh_balance())
    assert calls == [""]
    assert "正在刷新" not in workspace.home.balance.text()
    assert "无法读取当前配置凭据" in workspace.home.balance.text()
    assert "synthetic secret" not in workspace.home.balance.text()
    assert "DeepSeek 控制台" in workspace.home.console.text()


def test_custom_gateway_never_sends_key_to_official_balance_endpoint(
    workspace, monkeypatch
):
    seed_models(workspace)
    original = workspace.session.store.load_provider("deepseek")
    workspace.session.store.save_provider(
        replace(original, base_url="https://custom.invalid/v1")
    )

    async def forbidden(reference):
        raise AssertionError("must not read a gateway key for official balance")

    monkeypatch.setattr(workspace.session, "key", forbidden)
    asyncio.run(workspace.home.refresh_balance())
    assert "余额未知" in workspace.home.balance.text()
    assert "deepseek.com" not in workspace.home.console.text()


def test_completed_statistics_refresh_without_navigation(workspace):
    workspace.record_statistics(
        {"outcome": "succeeded", "characters": 37, "audio_seconds": 120}
    )
    assert workspace.home.metrics["characters"].text() == "37"
    assert workspace.home.metrics["audio_seconds"].text() == "2.0 分钟"
    assert workspace.home.chart.days[-1][1]["recordings"] == 1


def test_reopening_refreshes_statistics_without_replacing_model_draft(workspace):
    workspace.models_page.transcription.name.setText("Unsaved draft")
    workspace.stats.record("cancelled", audio_seconds=2)
    workspace.show_window()
    assert workspace.home.metrics["recordings"].text() == "1 次"
    assert workspace.models_page.transcription.name.text() == "Unsaved draft"
