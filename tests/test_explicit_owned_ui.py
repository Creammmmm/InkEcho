"""The new explicit bounded choice is saved without migrating old V2 users."""

import pytest
from PySide6.QtWidgets import QLabel
from test_ui import window as window


@pytest.mark.parametrize("window", ["wayland"], indirect=True)
def test_explicit_bounded_choice_is_visible_saved_and_deferred(window):
    page = window.settings_page.compatibility
    combo = page.output_method
    old = combo.findData("ibus")
    current = combo.findData("ibus-owned")
    assert old == -1 and current >= 0
    assert "GNOME Wayland" in combo.itemText(current)
    combo.setCurrentIndex(current)
    assert window.session.store.load_settings().output_method == "ibus-owned"
    page.refresh()
    assert "输出时" in page.availability.text()
    assert "不回退" in page.availability.text()
    assert "X11 / XWayland" in page.availability.text()
    assert "原生 Wayland" in page.availability.text()
    labels = [x.text() for x in page.findChildren(QLabel)]
    assert any(
        "IBus（GNOME Wayland）" in text and "无法确认目标是否收到" in text
        for text in labels
    )


@pytest.mark.parametrize("window", ["wayland"], indirect=True)
def test_auto_status_mentions_both_supported_bridges(window):
    page = window.settings_page.compatibility
    page.output_method.setCurrentIndex(page.output_method.findData("auto"))
    page.refresh()
    assert "Fcitx5" in page.availability.text()
    assert "GNOME IBus" in page.availability.text()
    assert "键盘" in page.availability.text()
