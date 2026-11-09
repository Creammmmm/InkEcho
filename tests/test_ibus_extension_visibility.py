import asyncio
from dataclasses import replace

import pytest
from PySide6.QtWidgets import QPushButton
from test_ui import window as window

from inkecho.ui import information


@pytest.mark.parametrize("session", ["x11", "wayland"])
@pytest.mark.parametrize("method", ["auto", "ibus", "ibus-owned"])
def test_extension_controls_follow_session_without_migration(
    window, monkeypatch, session, method
):
    store = window.session.store
    store.save_settings(replace(store.load_settings(), output_method=method))
    before = store.load_settings()
    real = information.detect_desktop()
    monkeypatch.setattr(
        information,
        "detect_desktop",
        lambda: replace(real, session=session, desktop="ubuntu:GNOME"),
    )

    def no_write(*args, **kwargs):
        raise AssertionError("page construction must not write settings")

    with monkeypatch.context() as scope:
        scope.setattr(store, "save_settings", no_write)
        page = information.CompatibilityPage(window.session)
    assert store.load_settings() == before
    assert page.output_method.currentData() == method
    assert any("扩展" in b.text() for b in page.findChildren(QPushButton)) == (
        session == "wayland"
    )
    assert hasattr(page, "ibus_extension") == (
        session == "wayland" and method == "ibus"
    )
    assert hasattr(page, "owned_extension") == (session == "wayland")
    assert (page.output_method.findData("ibus") >= 0) == (method == "ibus")
    assert (page.output_method.findData("ibus-owned") >= 0) == (
        session == "wayland" or method == "ibus-owned"
    )
    buttons = [b.text() for b in page.findChildren(QPushButton)]
    assert "安装实验扩展" not in buttons
    assert "启用实验扩展" not in buttons
    assert "安装自动输入扩展" not in buttons
    assert "启用自动输入扩展" not in buttons
    assert buttons.count("配置 IBus 输入桥") == (session == "wayland")
    if session == "x11":
        asyncio.run(page.owned_action("configure"))
    assert ("停用旧版 IBus 扩展" in buttons) == (
        session == "wayland" and method == "ibus"
    )
    assert page.receiver_wait.value() == 40
    page.receiver_wait.setValue(80)
    assert store.load_settings().receiver_feedback_wait_ms == 80
    page.close()
    page.deleteLater()


@pytest.mark.parametrize("desktop", ["KDE", "X-GNOME", "unknown"])
@pytest.mark.parametrize("method", ["auto", "ibus", "ibus-owned"])
def test_other_desktops_keep_saved_choice_without_extension_controls(
    window, monkeypatch, desktop, method
):
    store = window.session.store
    store.save_settings(replace(store.load_settings(), output_method=method))
    actual = information.detect_desktop()
    monkeypatch.setattr(
        information,
        "detect_desktop",
        lambda: replace(actual, session="wayland", desktop=desktop),
    )
    page = information.CompatibilityPage(window.session)
    assert page.output_method.currentData() == method
    assert not hasattr(page, "owned_extension")
    assert not hasattr(page, "ibus_extension")
    assert (page.output_method.findData("ibus-owned") >= 0) == (method == "ibus-owned")
    if method == "auto":
        assert "GNOME IBus" not in page.availability.text()
    else:
        assert "未确认可用" in page.availability.text()
    page.close()
    page.deleteLater()


@pytest.mark.parametrize("method", ["ibus", "ibus-owned"])
def test_save_failure_retains_concurrently_persisted_hidden_choice(
    window, monkeypatch, method
):
    page = window.settings_page.compatibility
    store = window.session.store
    original = store.save_settings

    def concurrent_write(settings):
        original(replace(settings, output_method=method))
        raise OSError("post-write failure")

    monkeypatch.setattr(store, "save_settings", concurrent_write)
    page.output_method.setCurrentIndex(page.output_method.findData("keyboard"))
    assert store.load_settings().output_method == method
    assert page.output_method.currentData() == method
    assert "无法保存" in page.message.text()
