"""Main desktop window, tray lifecycle and independent configuration pages."""

import os
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QMenu,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from inkecho.core import State
from inkecho.ui.dashboard import HomePage
from inkecho.ui.notifications import DesktopNotifications
from inkecho.ui.overlay_proxy import OverlayProxy, create_overlay
from inkecho.ui.prompts import PromptsPage
from inkecho.ui.providers import ProviderPage
from inkecho.ui.widgets import STYLE, actions, button, label
from inkecho.ui.workspace import HelpPage, ModelsPage, SettingsPage


class RecordingControls(QWidget):
    """A visible stop/cancel entry when the desktop has no tray."""

    def __init__(self, session):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("InkEcho 录音控制")
        self.setStyleSheet(STYLE)
        layout = QHBoxLayout(self)
        self.duration = label("00:00")
        layout.addWidget(self.duration)
        for text, callback in (
            ("结束录音", session.stop_recording),
            ("取消", session.cancel),
        ):
            item = button(text, callback)
            item.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            layout.addWidget(item)
            if text == "结束录音":
                self.stop = item


class ProblemNotice(QWidget):
    """Visible failure detail even when settings are hidden and no tray exists."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowTitle("InkEcho · 操作未完成")
        self.setStyleSheet(STYLE)
        self.setFixedWidth(440)
        body = QVBoxLayout(self)
        self.message = label("")
        body.addWidget(self.message)
        self.dismiss = QTimer(self)
        self.dismiss.setSingleShot(True)
        self.dismiss.timeout.connect(self.hide)

    def present(self, message):
        self.message.setText(message + "\n\n详细状态可在 InkEcho 概览中查看。")
        self.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 24, screen.y() + 48)
        self.show()
        self.dismiss.start(10000)


class MainWindow(QMainWindow):
    quit_requested = Signal()

    def __init__(self, session, stats, log, integration, command):
        super().__init__()
        self.session, self.stats, self.log = session, stats, log
        self.exiting = False
        self.setWindowTitle("InkEcho · 语音输入")
        self.resize(1120, 850)
        self.setMinimumSize(940, 700)
        self.setStyleSheet(STYLE)
        icon_path = Path(__file__).resolve().parents[1] / "assets/inkecho.png"
        self.icon = QIcon(str(icon_path))
        self.setWindowIcon(self.icon)
        QApplication.setWindowIcon(self.icon)
        self.overlay = create_overlay(session.store, self)
        if isinstance(self.overlay, OverlayProxy):
            self.overlay.failed.connect(self.show_status)
        self.problem_notice = ProblemNotice()
        self.wayland = os.environ.get(
            "XDG_SESSION_TYPE"
        ) == "wayland" or QApplication.platformName().startswith("wayland")
        self.notifications = DesktopNotifications(self.notification_action)
        self.controls = RecordingControls(session)
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        navigation = QVBoxLayout(sidebar)
        navigation.setContentsMargins(14, 24, 14, 20)
        brand = label("InkEcho")
        brand.setObjectName("brand")
        brand_icon = label("")
        brand_icon.setPixmap(self.icon.pixmap(44, 44))
        brand_icon.setFixedSize(44, 44)
        navigation.addWidget(actions(brand_icon, brand))
        navigation.addWidget(label("把声音，变成文字。", muted=True))
        self.navigation = QListWidget()
        navigation.addWidget(self.navigation, 1)
        layout.addWidget(sidebar)
        self.stack = QStackedWidget()
        self.home = HomePage(session, stats)
        self.models_page = ModelsPage(session)
        self.settings_page = SettingsPage(
            session, stats, log, integration, command, self.overlay.preview
        )
        self.help_page = HelpPage(session)
        self.pages = [
            self.home,
            self.models_page,
            PromptsPage(session),
            self.settings_page,
            self.help_page,
        ]
        names = ["概览", "模型配置", "润色风格", "设置", "帮助"]
        for name, page in zip(names, self.pages, strict=True):
            self.navigation.addItem(name)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.cancel_action = button("取消当前任务", session.cancel)
        self.cancel_action.hide()
        self.statusBar().addPermanentWidget(self.cancel_action)
        self.navigation.currentRowChanged.connect(self.select_page)
        self.navigation.setCurrentRow(0)
        self.tray = QSystemTrayIcon(self.icon, self)
        menu = QMenu()
        for text, callback in (
            ("打开设置", self.show_window),
            ("开始 / 结束录音", lambda: self.handle_command("toggle")),
            ("取消任务", session.cancel),
            ("退出", self.quit_requested.emit),
        ):
            action = QAction(text, menu)
            action.triggered.connect(callback)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("InkEcho · 语音输入")
        self.tray.activated.connect(
            lambda reason: (
                self.show_window()
                if reason == QSystemTrayIcon.ActivationReason.Trigger
                else None
            )
        )
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        session.status.connect(self.show_status)
        session.problem.connect(self.show_problem)
        session.state_changed.connect(self.update_state)
        if hasattr(session, "preview"):
            session.preview.connect(self.overlay.set_text)
        if hasattr(session, "capture_ready"):
            session.capture_ready.connect(self.overlay.set_capture_ready)
        session.level.connect(self.overlay.set_level)
        session.finished.connect(self.record_statistics)
        session.performance.connect(self.record_performance)
        session.diagnostic.connect(self.record_diagnostic)
        self.recording_started = None
        self.duration_timer = QTimer(self)
        self.duration_timer.setInterval(200)
        self.duration_timer.timeout.connect(self.update_duration)
        session.timer.timeout.connect(self.refresh_cancel_action)

    def refresh_cancel_action(self):
        active = self.session.preparing or self.session.controller.state in {
            State.RECORDING,
            State.TRANSCRIBING,
            State.POLISHING,
            State.INJECTING,
        }
        self.cancel_action.setVisible(active)

    def update_duration(self):
        if self.recording_started is None:
            return
        seconds = int(time.monotonic() - self.recording_started)
        duration = f"{seconds // 60:02}:{seconds % 60:02}"
        self.controls.duration.setText(duration)

    def record_diagnostic(self, code):
        try:
            self.log.record("error", code)
        except (ValueError, OSError):
            self.show_status("诊断日志写入失败，请检查本地数据目录。")

    def record_performance(self, snapshot):
        try:
            self.log.record_performance(snapshot)
        except (ValueError, OSError):
            self.show_status("性能计时写入失败，请检查本地数据目录。")

    def select_page(self, index):
        self.stack.setCurrentIndex(index)
        scroll = self.stack.widget(index)
        QTimer.singleShot(0, lambda: scroll.verticalScrollBar().setValue(0))
        page = self.pages[index]
        if isinstance(page, PromptsPage):
            page.refresh_availability()
        if hasattr(page, "refresh") and not isinstance(
            page, (ProviderPage, PromptsPage)
        ):
            page.safe(page.refresh)

    def show_status(self, message):
        self.statusBar().showMessage(message)
        self.tray.setToolTip("InkEcho · " + message[:70])

    def show_problem(self, message):
        self.show_status(message)
        if self.wayland:
            self.notify(message)
            return
        self.problem_notice.present(message)
        if self.tray.isVisible():
            self.tray.showMessage(
                "InkEcho · 操作未完成",
                message,
                QSystemTrayIcon.MessageIcon.Warning,
                10000,
            )

    def notification_action(self, action, task_id):
        if not self.session.active(task_id):
            return
        if action == "stop" and self.session.controller.state == State.RECORDING:
            self.session.stop_recording()
        elif action == "cancel":
            self.session.cancel()

    def notify(self, message, *, recording=False, processing=False):
        task = self.session.controller.task
        task_id = task.id if task else None
        self.notifications.invalidate_actions()

        async def display():
            available = await self.notifications.show(
                message, recording=recording, processing=processing, task_id=task_id
            )
            if not available:
                self.show_status(
                    message + "\n系统通知不可用；使用托盘菜单，"
                    "或打开设置后在窗口底部取消当前任务。"
                )

        self.session.spawn_ui(display())

    def update_state(self, state):
        from inkecho.app import STATE_LABELS

        if state != "idle":
            self.statusBar().showMessage(STATE_LABELS[State(state)])
        self.cancel_action.setVisible(
            state in {"recording", "transcribing", "polishing", "injecting"}
        )
        if state in {"idle", "recording", "failed", "cancelled", "succeeded"}:
            self.overlay.set_text("")
        if state == "recording":
            self.recording_started = time.monotonic()
            self.update_duration()
            self.duration_timer.start()
        else:
            self.duration_timer.stop()
        try:
            if self.wayland:
                self.overlay.show_state(state)
                self.controls.hide()
                detailed_failure = state == "failed"
                if state != "idle" and not detailed_failure:
                    self.notify(
                        STATE_LABELS[State(state)],
                        recording=state == "recording",
                        processing=state in {"transcribing", "polishing", "injecting"},
                    )
            else:
                self.overlay.show_state(state)
            self.log.record(state)
        except (ValueError, OSError):
            self.show_status("状态记录不可用，请检查本地数据目录。")
        if (
            state in {"recording", "transcribing", "polishing", "injecting"}
            and not self.tray.isVisible()
            and not self.wayland
        ):
            self.controls.stop.setEnabled(state == "recording")
            self.controls.show()
        elif state == "idle":
            self.controls.hide()
        if state == "idle" and not self.tray.isVisible() and not self.wayland:
            QTimer.singleShot(500, self.show_idle_window)

    def show_idle_window(self):
        if self.session.controller.state == State.IDLE and not self.session.preparing:
            self.show_window()

    def record_statistics(self, metrics):
        try:
            self.stats.record(**metrics)
            self.home.refresh()
        except (ValueError, OSError):
            self.show_status("使用统计保存失败；录音与正文未保存。")

    def handle_command(self, command: str):
        if command == "show":
            self.show_window()
        elif command == "cancel":
            self.session.cancel()
        elif command == "quit":
            self.quit_requested.emit()
        elif command == "toggle":
            self.problem_notice.hide()
            self.overlay.hide()
            if self.wayland:
                self.controls.hide()
            # Recording does not inspect focus; keyboard delivery uses focus later.
            self.session.spawn(self.session.toggle())

    def show_window(self):
        self.home.safe(self.home.refresh)
        self.models_page.refresh()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.exiting:
            event.accept()
            return
        event.ignore()
        if self.tray.isVisible():
            self.hide()
        else:
            self.showMinimized()
            self.show_status(
                "当前桌面没有系统托盘，窗口已最小化；可从任务栏或启动器恢复。"
            )

    def dispose(self):
        self.exiting = True
        self.duration_timer.stop()
        self.session.timer.timeout.disconnect(self.refresh_cancel_action)
        self.tray.hide()
        self.overlay.close()
        self.problem_notice.close()
        self.notifications.close()
        self.controls.close()
        self.close()
