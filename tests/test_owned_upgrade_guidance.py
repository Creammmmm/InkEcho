from PySide6.QtWidgets import QLabel
from test_ui import window as window


def test_owned_upgrade_instructions_are_actionable(window):
    page = window.settings_page.compatibility
    guidance = next(
        label.text()
        for label in page.findChildren(QLabel)
        if label.text().startswith("升级旧自动输入扩展：")
    )
    assert "停用自动输入扩展" in guidance
    assert "InkEcho bounded owned context candidate" in guidance
    assert (
        "gnome-extensions uninstall inkecho-ibus-owned-v5-prototype@local.invalid"
        in guidance
    )
    assert "安装自动输入扩展" in guidance and "启用自动输入扩展" in guidance
    assert "重新登录" in guidance and "不会自动卸载或覆盖" in guidance
