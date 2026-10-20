"""Real GUI startup path and owned read-only shortcut health sequencing."""

import asyncio
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal

from inkecho import __main__ as entry
from inkecho.config import ConfigStore
from inkecho.platform.hotkeys import ShortcutError
from inkecho.ui.settings import RecordingPage


class Signals(QObject):
    level = Signal(float)


def recording_page(tmp_path, monkeypatch):
    monkeypatch.setattr("inkecho.audio.Recorder.devices", lambda: [])
    store = ConfigStore(tmp_path / "config")
    store.initialize()
    signals = Signals()
    return RecordingPage(
        SimpleNamespace(store=store, level=signals.level, signals=signals),
        ["/owned/app", "--toggle"],
    )


def test_actual_run_builds_real_window_checks_shortcut_and_quits(
    tmp_path, qt_app, monkeypatch
):
    from inkecho.app import Session
    from inkecho.integration import DesktopIntegration
    from inkecho.ui import window as ui_window

    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.setattr("inkecho.audio.Recorder.devices", lambda: [])
    store = ConfigStore(tmp_path / "config")
    store.initialize()
    initial = {p.name: p.read_bytes() for p in store.root.glob("*.json")}
    observed = []
    windows = []
    initialized = []
    closed = []
    real_window = ui_window.MainWindow
    real_close = Session.close

    async def close_inputs():
        closed.append("inputs")

    monkeypatch.setattr(
        "inkecho.app.keyboard_for_desktop", lambda: SimpleNamespace(aclose=close_inputs)
    )

    def window(*args):
        result = real_window(*args)
        windows.append(result)
        return result

    async def initialize(self):
        initialized.append(self)

    async def close(self):
        await real_close(self)
        closed.append(self)

    def status(_adapter, shortcut, command):
        observed.append((shortcut, list(command)))
        return "启动健康检查完成"

    def forbidden(*_args):
        raise AssertionError("startup_must_not_register_shortcuts")

    monkeypatch.setattr(Session, "initialize", initialize)
    monkeypatch.setattr(Session, "close", close)
    monkeypatch.setattr(ui_window, "MainWindow", window)
    monkeypatch.setattr("inkecho.platform.hotkeys.GnomeShortcuts.status", status)
    monkeypatch.setattr("inkecho.platform.hotkeys.GnomeShortcuts.enable", forbidden)
    monkeypatch.setattr(
        "inkecho.integration.DesktopIntegration",
        lambda executable, args: DesktopIntegration(
            executable,
            args=args,
            data_home=tmp_path / "desktop",
            config_home=tmp_path / "autostart",
        ),
    )
    instance = SimpleNamespace(
        attach=lambda receive: None, close=lambda: closed.append("instance")
    )
    args = SimpleNamespace(
        data_dir=str(tmp_path / "data"),
        background=False,
        screenshot_dir=None,
        quit_after=0.05,
    )
    asyncio.run(entry.run(qt_app, store, instance, args))
    assert len(windows) == 1
    assert len(initialized) == 1
    assert closed == ["inputs", initialized[0], "instance"]
    assert len(observed) == 1
    assert observed[0][0] == store.load_settings().shortcut
    assert observed[0][1][-1] == "--toggle"
    assert windows[0].settings_page.recording.message.text() == "启动健康检查完成"
    assert not initialized[0].ui_tasks
    assert initial == {p.name: p.read_bytes() for p in store.root.glob("*.json")}
    qt_app.processEvents()


@pytest.mark.parametrize("fail", [False, True])
def test_late_health_never_overwrites_new_capture_result(
    tmp_path, qt_app, monkeypatch, fail
):
    page = recording_page(tmp_path, monkeypatch)
    started, release = threading.Event(), threading.Event()

    def status(*_args):
        started.set()
        assert release.wait(5)
        return "old health"

    def enable(*_args):
        if fail:
            raise ShortcutError("synthetic failure")

    monkeypatch.setattr("inkecho.platform.hotkeys.GnomeShortcuts.status", status)
    monkeypatch.setattr("inkecho.platform.hotkeys.GnomeShortcuts.enable", enable)

    async def exercise():
        health = asyncio.create_task(page.check_shortcut())
        assert await asyncio.to_thread(started.wait, 5)
        page.shortcut.click()
        page.message.setText("new capture")
        registration = asyncio.create_task(page.enable("Ctrl+F8"))
        await asyncio.sleep(0)
        release.set()
        await health
        assert page.message.text() == "new capture"
        await registration
        assert "old health" not in page.message.text()
        assert ("未更改" if fail else "保存并启用") in page.message.text()

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        page.close()


def test_health_failure_has_actionable_message_and_no_config_write(
    tmp_path, qt_app, monkeypatch
):
    page = recording_page(tmp_path, monkeypatch)
    before = {p.name: p.read_bytes() for p in page.session.store.root.glob("*.json")}

    def unavailable(*_args):
        raise ShortcutError("private backend detail")

    monkeypatch.setattr("inkecho.platform.hotkeys.GnomeShortcuts.status", unavailable)
    try:
        asyncio.run(page.check_shortcut())
        assert "全局快捷键" in page.message.text()
        assert "private" not in page.message.text()
        assert before == {
            p.name: p.read_bytes() for p in page.session.store.root.glob("*.json")
        }
    finally:
        page.close()


def test_queued_failed_registration_restores_latest_successful_binding(
    tmp_path, qt_app, monkeypatch
):
    page = recording_page(tmp_path, monkeypatch)
    started, release = threading.Event(), threading.Event()
    calls = []
    store = page.session.store
    real_save = store.save_settings

    def enable(_adapter, shortcut, _command):
        calls.append(shortcut)
        if len(calls) == 1:
            started.set()
            assert release.wait(5)

    def save(settings):
        if settings.shortcut == "Ctrl+F9":
            raise OSError("synthetic save failure")
        real_save(settings)

    monkeypatch.setattr("inkecho.platform.hotkeys.GnomeShortcuts.enable", enable)
    monkeypatch.setattr(store, "save_settings", save)

    async def exercise():
        first = asyncio.create_task(page.enable("Ctrl+F8"))
        assert await asyncio.to_thread(started.wait, 5)
        second = asyncio.create_task(page.enable("Ctrl+F9"))
        await asyncio.sleep(0)
        release.set()
        await asyncio.gather(first, second)
        assert calls == ["Ctrl+F8", "Ctrl+F9", "Ctrl+F8"]
        assert store.load_settings().shortcut == "Ctrl+F8"
        assert page.shortcut.text() == "Ctrl+F8"

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        page.close()
