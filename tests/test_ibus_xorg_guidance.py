import asyncio
from dataclasses import replace

import pytest
from PySide6.QtWidgets import QLabel
from test_ui import window as window

from inkecho.ui import information


@pytest.mark.parametrize("method", ["ibus", "ibus-owned"])
def test_xorg_legacy_ibus_does_not_claim_configuration(window, monkeypatch, method):
    store = window.session.store
    store.save_settings(replace(store.load_settings(), output_method=method))
    page = information.CompatibilityPage(window.session)
    labels = "".join(x.text() for x in page.findChildren(QLabel))
    assert "Fcitx5 仍需要输入桥" in labels
    assert "下一次任务生效" in labels
    assert "此版本尚未提供免扩展" in labels
    assert "下方单独安装" not in labels
    if method == "ibus-owned":
        assert "不适用于 Xorg" in page.availability.text()
    else:
        assert "选择它不会自动安装" in page.availability.text()

    async def prepared():
        return True

    monkeypatch.setattr(window.session, "authorize_input", prepared)
    asyncio.run(page.enable())
    assert "未验证 Xorg IBus" in page.message.text()
    assert store.load_settings().output_method == method
    page.close()
    page.deleteLater()


@pytest.mark.parametrize("window", ["wayland"], indirect=True)
def test_wayland_description_remains(window):
    page = window.settings_page.compatibility
    labels = "".join(x.text() for x in page.findChildren(QLabel))
    assert "Fcitx5 需要额外安装输入桥；IBus 需要手动启用实验性 GNOME 扩展。" in labels
    assert "下方单独安装、启用的 GNOME 自动输入扩展" in labels
    assert "此版本尚未提供免扩展" not in labels
