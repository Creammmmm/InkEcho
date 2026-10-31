import sys,json
from pathlib import Path
from PyQt6.QtWidgets import QApplication,QPlainTextEdit
p=Path(sys.argv[1]);events=[]
class E(QPlainTextEdit):
 def inputMethodEvent(self,e):
  events.append({'preedit':e.preeditString(),'commit':e.commitString()});p.write_text(json.dumps({'events':events,'text':self.toPlainText()},ensure_ascii=False));super().inputMethodEvent(e);p.write_text(json.dumps({'events':events,'text':self.toPlainText()},ensure_ascii=False))
a=QApplication([]);w=E();w.setWindowTitle('InkEchoQt6Preedit');w.show();w.activateWindow();w.setFocus();sys.exit(a.exec())
