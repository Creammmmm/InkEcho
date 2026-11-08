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
        information, "detect_desktop", lambda: replace(real, session=session)
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
    assert hasattr(page, "ibus_extension") == (session == "wayland")
    assert hasattr(page, "owned_extension") == (session == "wayland")
    assert page.receiver_wait.value() == 40
    page.receiver_wait.setValue(80)
    assert store.load_settings().receiver_feedback_wait_ms == 80
    page.close()
    page.deleteLater()
