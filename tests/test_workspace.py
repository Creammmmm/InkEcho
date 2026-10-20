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
        "润色风格",
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
    assert workspace.home.metrics["characters"].text() == "12"
    assert workspace.home.metrics["audio_seconds"].text() == "1.5 分钟"
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
    assert "CNY 余额 12.50" in "\n".join(
        item.text() for item in workspace.home.balance_labels.values()
    )
    assert caption in "\n".join(
        item.text() for item in workspace.home.balance_labels.values()
    )


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
        assert "OLD BALANCE" not in "\n".join(
            item.text() for item in workspace.home.balance_labels.values()
        )

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
    assert "正在刷新" not in "\n".join(
        item.text() for item in workspace.home.balance_labels.values()
    )
    assert "无法读取当前配置凭据" in "\n".join(
        item.text() for item in workspace.home.balance_labels.values()
    )
    assert "synthetic secret" not in "\n".join(
        item.text() for item in workspace.home.balance_labels.values()
    )
    assert "DeepSeek 控制台" in "\n".join(
        item.text() for item in workspace.home.console_labels.values()
    )


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
    assert "余额未知" in "\n".join(
        item.text() for item in workspace.home.balance_labels.values()
    )
    assert "deepseek.com" not in "\n".join(
        item.text() for item in workspace.home.console_labels.values()
    )


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


def test_overview_has_no_recording_card_or_recording_widgets(workspace):
    from PySide6.QtWidgets import QLabel, QProgressBar

    home = workspace.home
    texts = [item.text() for item in home.findChildren(QLabel)]
    buttons = [item.text() for item in home.findChildren(QPushButton)]
    assert "准备就绪" not in texts
    assert "开始录音" not in buttons
    assert "取消任务" not in buttons
    assert not home.findChildren(QProgressBar)
    for name in ("record", "state", "description", "level", "duration"):
        assert not hasattr(home, name)
    assert home.body.itemAt(2).layout().count() == 3
    assert home.body.itemAt(3).layout().count() == 2
    assert home.transcription in home.findChildren(type(home.transcription))


def test_shortcut_command_and_recording_duration_remain_available(workspace):
    async def scenario():
        calls = []

        async def toggle():
            calls.append("toggle")

        workspace.session.toggle = toggle
        workspace.handle_command("toggle")
        await asyncio.gather(*workspace.session.pending)
        assert calls == ["toggle"]

    asyncio.run(scenario())
    workspace.wayland = False
    workspace.update_state("recording")
    assert workspace.recording_started is not None
    assert workspace.duration_timer.isActive()
    workspace.update_duration()
    assert workspace.controls.duration.text() == "00:00"
    workspace.update_state("idle")
    assert not workspace.duration_timer.isActive()


def test_preparing_shortcut_keeps_status_cancel_until_pending_cleanup(workspace):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    seed_models(workspace)
    store = workspace.session.store
    store.save_provider(replace(store.load_provider("qwen"), model="qwen3-asr-flash"))
    store.save_settings(replace(store.load_settings(), polishing_enabled=False))

    async def scenario():
        entered = asyncio.Event()

        async def blocked_key(_reference):
            entered.set()
            await asyncio.Event().wait()

        workspace.session.key = blocked_key
        workspace.show()
        workspace.handle_command("toggle")
        await asyncio.wait_for(entered.wait(), 1)
        assert workspace.session.preparing
        assert workspace.session.controller.task is None
        QTest.qWait(150)
        assert workspace.cancel_action.isVisible()
        QTest.mouseClick(workspace.cancel_action, Qt.MouseButton.LeftButton)
        await asyncio.gather(*workspace.session.pending, return_exceptions=True)
        await asyncio.sleep(0)
        QTest.qWait(150)
        assert not workspace.session.preparing
        assert not workspace.session.pending
        assert workspace.cancel_action.isHidden()
        assert "已取消" in workspace.statusBar().currentMessage()

    asyncio.run(scenario())
