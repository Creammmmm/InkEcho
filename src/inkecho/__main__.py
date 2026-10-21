"""Desktop entry point and same-user single-instance commands."""

import argparse
import hashlib
import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLockFile, QObject, QStandardPaths, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from inkecho.config import ConfigError, ConfigStore


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
        self.pending_commands = []
        self.attached = False

    def attach(self, handler):
        self.command.connect(handler)
        self.attached = True
        for command in self.pending_commands:
            self.command.emit(command)
        self.pending_commands.clear()

    def acquire(self, command: str, *, allow_start: bool = True) -> bool:
        if self.lock.tryLock(0):
            if not allow_start:
                self.lock.unlock()
                return False
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
                        if self.attached:
                            self.command.emit(command)
                        else:
                            self.pending_commands = [
                                *self.pending_commands[-31:],
                                command,
                            ]
                    connection.disconnectFromServer()

            socket.readyRead.connect(read)
            socket.disconnected.connect(socket.deleteLater)
            read()

    def close(self):
        self.server.close()
        self.lock.unlock()


class StartupCommands:
    """Queue commands to an already starting instance until services are ready."""

    def __init__(self, dispatch):
        self.dispatch = dispatch
        self.ready = False
        self.pending_toggle = False

    def receive(self, command):
        if not self.ready:
            if command == "toggle":
                self.pending_toggle = True
                return
            if command in {"cancel", "quit"}:
                self.pending_toggle = False
        self.dispatch(command)

    def complete(self):
        self.ready = True
        if self.pending_toggle:
            self.pending_toggle = False
            self.dispatch("toggle")


async def run(app, store, instance, args):
    import asyncio
    import json

    from inkecho.app import Session
    from inkecho.integration import DesktopIntegration, IntegrationError
    from inkecho.logging import DiagnosticLog
    from inkecho.statistics import Statistics
    from inkecho.ui.window import MainWindow

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
        if appimage:
            try:
                integration.ensure_running_identity()
            except (IntegrationError, OSError):
                log.record("integration", "integration_failed")
        window = MainWindow(session, stats, log, integration, command)
        stopped = asyncio.Event()
        window.quit_requested.connect(stopped.set)
        commands = StartupCommands(window.handle_command)
        instance.attach(commands.receive)
        log.record("startup")
        if stopped.is_set():
            return
        if not args.background or not window.tray.isVisible():
            window.show()
        await session.initialize()
        if stopped.is_set():
            return
        commands.complete()
        window.settings_page.recording.run(
            window.settings_page.recording.check_shortcut()
        )
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
            await window.notifications.shutdown()
            if hasattr(window.overlay, "shutdown"):
                await window.overlay.shutdown()
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
    command = next(
        (name for name in ("toggle", "cancel", "quit") if getattr(args, name)), "show"
    )
    control = command in {"toggle", "cancel", "quit"}
    if control:
        app = QCoreApplication(["InkEcho"])
    else:
        from PySide6.QtGui import QFontDatabase, QIcon
        from PySide6.QtWidgets import QApplication

        app = QApplication(["InkEcho"])
        app.setDesktopFileName("io.github.Creammmmm.InkEcho")
        app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets/inkecho.png")))
        app.setQuitOnLastWindowClosed(False)
        bundled_font = (
            Path(os.environ.get("APPDIR", "/nonexistent"))
            / "usr/share/fonts/NotoSansCJK-Regular.ttc"
        )
        if bundled_font.is_file():
            QFontDatabase.addApplicationFont(str(bundled_font))
    app.setApplicationName("InkEcho")
    app.setOrganizationName("InkEcho")
    store = ConfigStore(args.config_dir)
    instance = None
    try:
        instance = Instance(store.root)
        if not instance.acquire(command, allow_start=not control):
            return
        import asyncio

        from inkecho.runtime import ManagedQtEventLoop

        store.initialize()
        with ManagedQtEventLoop(app) as loop:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run(app, store, instance, args))
    except (ConfigError, OSError, RuntimeError) as error:
        if instance is not None:
            instance.close()
        if control:
            print("InkEcho 控制命令未送达，请稍后重试。", file=sys.stderr)
            raise SystemExit(1) from None
        message = f"启动未完成，原始配置保留。\n配置目录：{store.root}\n\n{error}"
        if args.quit_after is not None or args.screenshot_dir:
            print(message, file=sys.stderr)
        else:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(None, "InkEcho 无法启动", message)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
