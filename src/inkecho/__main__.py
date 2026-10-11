"""Desktop entry point and same-user single-instance commands."""

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QStandardPaths, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox
from qasync import QEventLoop

from inkecho.app import Session
from inkecho.config import ConfigError, ConfigStore
from inkecho.integration import DesktopIntegration
from inkecho.logging import DiagnosticLog
from inkecho.statistics import Statistics
from inkecho.ui.window import MainWindow


class Instance(QObject):
    command = Signal(str)

    def __init__(self, config: Path):
        super().__init__()
        identity = hashlib.sha256(str(config.resolve()).encode()).hexdigest()[:16]
        self.name = f"inkecho-{os.getuid()}-{identity}"
        runtime = Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.RuntimeLocation
            )
        )
        runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = QLockFile(str(runtime / f"{self.name}.lock"))
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self.receive)

    def acquire(self, command: str) -> bool:
        if self.lock.tryLock(0):
            QLocalServer.removeServer(self.name)
            if not self.server.listen(self.name):
                self.lock.unlock()
                raise RuntimeError("无法建立应用本地通信入口。")
            return True
        socket = QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(1000):
            raise RuntimeError("InkEcho 正在启动或本地通信不可用，请稍后重试。")
        socket.write((command + "\n").encode())
        socket.flush()
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        return False

    def receive(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()

            def read(connection=socket):
                if connection.canReadLine():
                    command = (
                        bytes(connection.readLine(64)).decode(errors="replace").strip()
                    )
                    if command in {"show", "toggle", "cancel", "quit"}:
                        self.command.emit(command)
                    connection.disconnectFromServer()

            socket.readyRead.connect(read)
            socket.disconnected.connect(socket.deleteLater)
            read()

    def close(self):
        self.server.close()
        self.lock.unlock()


async def run(app, store, instance, args):
    session = Session(store)
    data_root = Path(args.data_dir) if args.data_dir else None
    stats = Statistics(data_root / "statistics.json" if data_root else None)
    log = DiagnosticLog(data_root)
    appimage = os.environ.get("APPIMAGE")
    executable = Path(appimage) if appimage else Path(sys.executable)
    arguments = () if appimage else ("-m", "inkecho")
    integration = DesktopIntegration(executable, args=arguments)
    command = [str(executable), *arguments, "--toggle"]
    window = None
    try:
        window = MainWindow(session, stats, log, integration, command)
        stopped = asyncio.Event()
        window.quit_requested.connect(stopped.set)
        instance.command.connect(window.handle_command)
        log.record("startup")
        if not args.toggle and (not args.background or not window.tray.isVisible()):
            window.show()
        await session.initialize()
        if args.toggle:
            await session.toggle()
            if not session.controller.task and not window.tray.isVisible():
                window.show()
        if args.screenshot_dir:
            output = Path(args.screenshot_dir)
            output.mkdir(parents=True, exist_ok=True)
            window.show()
            for index in range(len(window.pages)):
                window.navigation.setCurrentRow(index)
                await asyncio.sleep(0.15)
                if not window.grab().save(str(output / f"page-{index + 1:02}.png")):
                    raise RuntimeError("无法保存页面截图。")
            window.navigation.setCurrentRow(0)
            print(
                json.dumps(
                    {
                        "screenshots": len(window.pages),
                        "platform": app.platformName(),
                        "visible": window.isVisible(),
                    }
                ),
                flush=True,
            )
        if args.quit_after is not None:
            asyncio.get_running_loop().call_later(args.quit_after, stopped.set)
        await stopped.wait()
    finally:
        await session.close()
        if window is not None:
            window.dispose()
        try:
            log.record("shutdown")
        finally:
            log.close()
            instance.close()


def main():
    parser = argparse.ArgumentParser(description="InkEcho Linux voice input")
    action = parser.add_mutually_exclusive_group()
    for name in ("show", "toggle", "cancel", "quit", "background"):
        action.add_argument(f"--{name}", action="store_true")
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--screenshot-dir", type=Path)
    parser.add_argument("--quit-after", type=float)
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("InkEcho")
    app.setOrganizationName("InkEcho")
    app.setQuitOnLastWindowClosed(False)
    bundled_font = (
        Path(os.environ.get("APPDIR", "/nonexistent"))
        / "usr/share/fonts/NotoSansCJK-Regular.ttc"
    )
    if bundled_font.is_file():
        QFontDatabase.addApplicationFont(str(bundled_font))
    store = ConfigStore(args.config_dir)
    instance = Instance(store.root)
    command = next(
        (name for name in ("toggle", "cancel", "quit") if getattr(args, name)), "show"
    )
    try:
        if not instance.acquire(command):
            return
        if args.cancel or args.quit:
            instance.close()
            return
        store.initialize()
        with QEventLoop(app) as loop:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run(app, store, instance, args))
    except (ConfigError, OSError, RuntimeError) as error:
        instance.close()
        message = f"启动未完成，原始配置保留。\n配置目录：{store.root}\n\n{error}"
        if args.quit_after is not None or args.screenshot_dir:
            print(message, file=sys.stderr)
        else:
            QMessageBox.critical(None, "InkEcho 无法启动", message)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
