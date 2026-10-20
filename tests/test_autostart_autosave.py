"""Autostart autosave ordering using isolated fake desktop integration."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from inkecho.integration import IntegrationError
from inkecho.ui.information import AboutPage


class FakeIntegration:
    def __init__(self):
        self.enabled = False

    def status(self):
        return {
            "executable": "/isolated/inkecho",
            "current": True,
            "installed": True,
            "autostart": self.enabled,
        }

    def set_autostart(self, enabled):
        self.enabled = enabled


def test_autostart_rapid_changes_keep_latest_choice(qt_app, monkeypatch):
    async def scenario():
        integration = FakeIntegration()
        tasks = []
        session = SimpleNamespace(
            diagnostic=SimpleNamespace(emit=Mock()),
            spawn_ui=lambda operation: tasks.append(asyncio.create_task(operation)),
        )
        page = AboutPage(session, integration)
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def worker(operation, enabled):
            calls.append(enabled)
            if len(calls) == 1:
                entered.set()
                await release.wait()
            operation(enabled)

        monkeypatch.setattr("inkecho.ui.information.asyncio.to_thread", worker)
        page.autostart.setChecked(True)
        await entered.wait()
        page.autostart.setChecked(False)
        page.autostart.setChecked(True)
        page.autostart.setChecked(False)
        await asyncio.sleep(0)
        assert calls == [True]
        assert not page.autostart.isChecked()
        release.set()
        await asyncio.gather(*tasks)
        assert calls == [True, False, True, False]
        assert not integration.enabled
        assert not page.autostart.isChecked()
        assert "已自动保存" in page.message.text()
        page.close()

    asyncio.run(scenario())


def test_autostart_failure_restores_actual_state(qt_app, monkeypatch):
    async def scenario():
        integration = FakeIntegration()
        tasks = []
        diagnostic = Mock()
        session = SimpleNamespace(
            diagnostic=SimpleNamespace(emit=diagnostic),
            spawn_ui=lambda operation: tasks.append(asyncio.create_task(operation)),
        )
        page = AboutPage(session, integration)

        async def worker(operation, enabled):
            raise IntegrationError("isolated failure")

        monkeypatch.setattr("inkecho.ui.information.asyncio.to_thread", worker)
        page.autostart.setChecked(True)
        await asyncio.gather(*tasks)
        assert len(tasks) == 1  # Refresh blocks signals and cannot enqueue a write.
        assert not integration.enabled
        assert not page.autostart.isChecked()
        assert "未保存" in page.message.text()
        assert "实际状态" in page.message.text()
        diagnostic.assert_called_once_with("integration_failed")
        page.close()

    asyncio.run(scenario())
