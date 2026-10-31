import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from inkecho.app import Session
from inkecho.config import ConfigStore
from inkecho.integration import DesktopIntegration
from inkecho.logging import DiagnosticLog
from inkecho.statistics import Statistics
from inkecho.ui.widgets import STYLE
from inkecho.ui.window import MainWindow

app = QApplication([])
app.setStyleSheet(STYLE)
with tempfile.TemporaryDirectory(prefix="inkecho-ui-check-") as tmp:
    store = ConfigStore(Path(tmp) / "config")
    store.initialize()
    session = Session(store)
    log = DiagnosticLog(Path(tmp) / "data")
    integration = DesktopIntegration(
        Path(sys.executable),
        data_home=Path(tmp) / "desktop",
        config_home=Path(tmp) / "autostart",
    )
    window = MainWindow(
        session,
        Statistics(Path(tmp) / "statistics.json"),
        log,
        integration,
        [sys.executable, "-m", "inkecho", "--toggle"],
    )
    window.tray.hide()
    window.resize(1100, 900)
    window.show()
    window.navigation.setCurrentRow(3)
    window.settings_page.tabs.setCurrentIndex(3)
    page = window.settings_page.compatibility
    app.processEvents()
    loop = QEventLoop()
    QTimer.singleShot(500, loop.quit)
    loop.exec()
    results = {
        "session": os.getenv("XDG_SESSION_TYPE"),
        "platform": app.platformName(),
        "visible": page.isVisible(),
        "controls": {
            k: {
                "visible": getattr(page, k).isVisible(),
                "geometry": [getattr(page, k).width(), getattr(page, k).height()],
            }
            for k in (
                "output_method",
                "receiver_wait",
                "mapping_wait",
                "feedback_timeout",
            )
        },
        "choices": {},
    }
    for mode in ("auto", "keyboard", "ibus", "fcitx", "ibus-owned"):
        page.output_method.setCurrentIndex(page.output_method.findData(mode))
        page.refresh()
        app.processEvents()
        results["choices"][mode] = {
            "text": page.availability.text(),
            "visible": page.availability.isVisible(),
        }
        window.grab().save("/mnt/output/" + results["session"] + "-" + mode + ".png")
    assert results["visible"] and all(x["visible"] for x in results["choices"].values())
    assert all(
        x["visible"] and x["geometry"][1] > 0 for x in results["controls"].values()
    )
    expected = results["session"] == "x11"
    for mode in ("auto", "keyboard", "ibus"):
        assert (
            "可能中断正在进行的输入法组词" in results["choices"][mode]["text"]
        ) == expected
    for mode in ("fcitx", "ibus-owned"):
        assert "可能中断正在进行的输入法组词" not in results["choices"][mode]["text"]
    if expected:
        assert "模拟键盘" not in results["choices"]["ibus"]["text"]

    class Fake:
        def install(self):
            pass

        def status(self):
            raise RuntimeError("private-test-detail")

    async def maintenance(f):
        f()

    session.run_input_maintenance = maintenance
    page.owned_extension = Fake()
    asyncio.run(page.owned_action("install"))
    results["synthetic_after_install"] = {
        "message": page.message.text(),
        "status": page.owned_status.text(),
    }
    assert (
        "操作已提交" in page.message.text()
        and "状态检查失败" in page.owned_status.text()
    )
    page.owned_status.setText("扩展正在运行")
    asyncio.run(page.owned_action("status"))
    results["synthetic_status_failure"] = {
        "message": page.message.text(),
        "status": page.owned_status.text(),
    }
    assert (
        "状态检查失败" in page.owned_status.text()
        and "private-test-detail" not in page.owned_status.text()
    )
    page.refresh_timer.stop()
    session.timer.stop()
    asyncio.run(session.inputs.aclose())
    window.dispose()
    log.close()
    print(json.dumps(results, ensure_ascii=False))
