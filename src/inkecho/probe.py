"""Small stage-zero window to verify the packaged Qt runtime."""

import argparse
import json
import os
import platform
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from inkecho import __version__


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--screenshot")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("InkEcho Feasibility Probe")
    window = QWidget()
    window.setWindowTitle("InkEcho · Stage 0")
    window.resize(560, 320)
    layout = QVBoxLayout(window)
    layout.setContentsMargins(32, 28, 32, 28)
    title = QLabel("InkEcho")
    title.setStyleSheet("font-size: 30px; font-weight: 600;")
    layout.addWidget(title)
    layout.addWidget(QLabel(f"Runtime feasibility probe · {__version__}"))
    layout.addWidget(
        QLabel(f"Linux / {app.platformName()} / Python {platform.python_version()}")
    )
    details = QLabel(
        "This package verifies the desktop runtime.\n\n"
        "Voice transcription is not implemented in this stage.\n"
        "No audio is recorded and no clipboard is accessed."
    )
    details.setWordWrap(True)
    layout.addWidget(details)
    layout.addStretch()
    close = QPushButton("Close probe")
    close.clicked.connect(window.close)
    layout.addWidget(close)
    window.show()

    def finish() -> None:
        if args.screenshot:
            if not window.grab().save(args.screenshot):
                app.exit(1)
                return
        print(
            json.dumps(
                {
                    "version": __version__,
                    "platform": app.platformName(),
                    "visible": window.isVisible(),
                    "packaged": bool(os.getenv("APPDIR")),
                    "python": sys.executable,
                }
            ),
            flush=True,
        )
        if args.smoke_test:
            app.quit()

    QTimer.singleShot(800, finish)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
