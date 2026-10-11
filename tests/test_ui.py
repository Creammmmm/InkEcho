"""Qt widget interactions, isolated persistence and asynchronous form ownership."""

import asyncio
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton

from inkecho.app import Session
from inkecho.config import BUILTIN_PROMPT, ConfigStore
from inkecho.integration import DesktopIntegration
from inkecho.logging import DiagnosticLog
from inkecho.statistics import Statistics
from inkecho.ui.settings import AppearancePage
from inkecho.ui.window import MainWindow


@pytest.fixture
def window(tmp_path, qt_app):
    store = ConfigStore(tmp_path / "config")
    store.initialize()
    session = Session(store)
    log = DiagnosticLog(tmp_path / "data")
    integration = DesktopIntegration(
        Path(sys.executable),
        data_home=tmp_path / "desktop",
        config_home=tmp_path / "autostart",
    )
    widget = MainWindow(
        session,
        Statistics(tmp_path / "statistics.json"),
        log,
        integration,
        [sys.executable, "-m", "inkecho", "--toggle"],
    )
    widget.tray.hide()
    widget.show()
    qt_app.processEvents()
    yield widget
    session.timer.stop()
    session.inputs.close()
    widget.dispose()
    log.close()
    qt_app.processEvents()


def click(widget, text):
    matches = [item for item in widget.findChildren(QPushButton) if item.text() == text]
    assert len(matches) == 1
    QTest.mouseClick(matches[0], Qt.MouseButton.LeftButton)


def test_appearance_save_reload_and_builtin_prompt_copy(window, qt_app):
    page = window.pages[6]
    window.navigation.setCurrentRow(6)
    page.style.setCurrentIndex(page.style.findData("pulse"))
    page.position.setCurrentIndex(page.position.findData("top-center"))
    click(page, "保存外观")
    reloaded = AppearancePage(window.session, lambda: None)
    assert reloaded.style.currentData() == "pulse"
    assert reloaded.position.currentData() == "top-center"
    reloaded.close()
    prompts = window.pages[4]
    window.navigation.setCurrentRow(4)
    prompts.text.setPlainText("保留用户措辞，只修改标点。")
    click(prompts, "保存模板")
    assert prompts.identifier != BUILTIN_PROMPT.id
    assert window.session.store.load_prompt(BUILTIN_PROMPT.id) == BUILTIN_PROMPT
    assert (
        window.session.store.load_prompt(prompts.identifier).body
        == "保留用户措辞，只修改标点。"
    )


def test_navigation_scroll_and_icon(window, qt_app):
    assert not window.icon.isNull()
    for index in range(len(window.pages)):
        window.navigation.setCurrentRow(index)
        qt_app.processEvents()
        scroll = window.stack.widget(index)
        assert scroll.verticalScrollBar().value() == 0
        bar = scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        qt_app.processEvents()
        assert bar.value() == bar.maximum()


def test_own_window_toggle_refused(window, qt_app):
    window.activateWindow()
    qt_app.processEvents()
    window.handle_command("toggle")
    assert not window.session.pending
    assert "不能向 InkEcho 自身输入" in window.home.description.text()


def test_no_tray_processing_retains_cancel_entry(window):
    window.hide()
    window.update_state("transcribing")
    assert window.controls.isVisible()
    assert not window.controls.stop.isEnabled()
    click(window.controls, "取消")
    assert "已取消" in window.home.description.text()


def test_preparation_cancel_restores_window(window):
    async def scenario():
        waiting = asyncio.Event()

        async def slow(**_kwargs):
            waiting.set()
            await asyncio.Event().wait()

        window.session.toggle = slow
        window.start_from_window()
        await waiting.wait()
        assert not window.isVisible()
        window.session.cancel()
        await asyncio.gather(*window.session.pending, return_exceptions=True)
        assert window.isVisible()

    asyncio.run(scenario())


def test_model_discovery_does_not_overwrite_another_form(window):
    async def scenario():
        page = window.pages[2]
        waiting, release = asyncio.Event(), asyncio.Event()

        async def key(_reference):
            return "test-key"

        class Client:
            async def models(self, *_args):
                waiting.set()
                await release.wait()
                return ["old-provider-model"]

        window.session.key = key
        window.session.provider_client = lambda _role: Client()
        request = asyncio.create_task(page.discover())
        await waiting.wait()
        page.new()
        page.model.setCurrentText("new-provider-model")
        release.set()
        await request
        assert page.model.currentText() == "new-provider-model"
        assert page.model.findText("old-provider-model") == -1

    asyncio.run(scenario())


def test_provider_save_snapshots_preferences_before_keyring_wait(window):
    async def scenario():
        page = window.pages[3]
        waiting, release = asyncio.Event(), asyncio.Event()
        written = []

        async def save_key(reference, value):
            written.append((reference, value))
            waiting.set()
            await release.wait()

        window.session.save_key = save_key
        page.key.setText("temporary-test-secret")
        page.enabled.setChecked(True)
        page.fallback.setChecked(False)
        original = page.identifier
        request = asyncio.create_task(page.save())
        await waiting.wait()
        assert page.key.text() == ""
        page.new()
        page.enabled.setChecked(False)
        page.fallback.setChecked(True)
        release.set()
        await request
        settings = window.session.store.load_settings()
        assert settings.polishing_provider == original
        assert settings.polishing_enabled
        assert not settings.polishing_fallback
        assert page.identifier != original
        assert written[0][1] == "temporary-test-secret"
        assert (
            "temporary-test-secret"
            not in (window.session.store.root / "config.json").read_text()
        )

    asyncio.run(scenario())
