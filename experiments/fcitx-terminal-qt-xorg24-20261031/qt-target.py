import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication,QPlainTextEdit
app=QApplication([]);w=QPlainTextEdit();w.setWindowTitle(sys.argv[1]);path=Path(sys.argv[2]);path.write_text('');w.textChanged.connect(lambda:path.write_text(w.toPlainText()));w.show();w.activateWindow();w.setFocus();sys.exit(app.exec())
