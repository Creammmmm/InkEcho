"""Small presentation helpers shared by the settings pages."""

import asyncio

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

STYLE = """
QWidget { font-family: 'Noto Sans CJK SC', 'Noto Sans', sans-serif; font-size: 14px;
 color: #173832; background: #f5f8f7; }
QMainWindow { background: #f5f8f7; }
QLabel#heading { font-size: 28px; font-weight: 700; }
QLabel#muted { color: #67817a; }
QLabel#brand { font-size: 24px; font-weight: 700; color: #187661; }
QFrame#card { background: white; border: 1px solid #dbe7e2; border-radius: 14px; }
QFrame#card QLabel { background: transparent; }
QPushButton { background: white; border: 1px solid #ccddd5; border-radius: 8px;
 padding: 9px 15px; font-weight: 500; }
QPushButton:hover { background: #e6f3ed; border-color: #53a88c; }
QPushButton:disabled { color: #a5b5ad; background: #edf1ef; }
QPushButton#primary { background: #16765f; color: white; border-color: #16765f; }
QPushButton#primary:hover { background: #105e4c; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit { background: white;
 border: 1px solid #ccdcd5; border-radius: 7px; padding: 7px;
 selection-background-color: #b2dfce; }
QListWidget { background: #edf4f0; border: none; outline: none; padding: 8px; }
QListWidget::item { padding: 12px 14px; margin: 3px 0; border-radius: 8px; }
QListWidget::item:selected { background: #d3e9df; color: #155b48; font-weight: 600; }
QCheckBox { spacing: 8px; }
QProgressBar { border: 0; background: #e1ede7; border-radius: 5px; min-height: 10px; }
QProgressBar::chunk { background: #33a981; border-radius: 5px; }
QScrollArea { border: none; }
"""


def label(text: str, *, muted=False) -> QLabel:
    widget = QLabel(text)
    widget.setWordWrap(True)
    if muted:
        widget.setObjectName("muted")
    return widget


def button(text: str, callback, *, primary=False) -> QPushButton:
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("primary")
    widget.clicked.connect(callback)
    return widget


def actions(*buttons) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    for item in buttons:
        layout.addWidget(item)
    layout.addStretch()
    return widget


class Page(QWidget):
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(30, 26, 30, 26)
        self.body.setSpacing(18)
        heading = label(title)
        heading.setObjectName("heading")
        self.body.addWidget(heading)
        self.body.addWidget(label(subtitle, muted=True))
        self.message = label("")
        self.message.setObjectName("muted")

    def finish(self):
        self.body.addWidget(self.message)
        self.body.addStretch()

    def run(self, operation):
        revision = getattr(self, "revision", None)

        async def perform():
            try:
                await operation
            except asyncio.CancelledError:
                if revision == getattr(self, "revision", None):
                    self.message.setText("操作已取消。")
            except Exception as error:
                if revision != getattr(self, "revision", None):
                    return
                from inkecho.app import PROVIDER_LABELS
                from inkecho.config import ConfigError
                from inkecho.providers import ProviderError
                from inkecho.security import CredentialError

                if isinstance(error, ProviderError):
                    self.message.setText(
                        PROVIDER_LABELS.get(
                            error.code, "云端请求失败，请检查服务配置。"
                        )
                    )
                elif isinstance(error, (ConfigError, CredentialError)):
                    self.message.setText(str(error))
                else:
                    self.message.setText("操作未完成，请检查设置与系统服务。")

        if hasattr(self, "session"):
            return self.session.spawn_ui(perform())
        return asyncio.create_task(perform())

    def safe(self, operation):
        try:
            return operation()
        except (ValueError, OSError):
            self.message.setText("配置无法读取或保存，请检查字段与配置文件。")


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(14)
    return frame, layout
