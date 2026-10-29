import asyncio, json, tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from inkecho.config import ConfigStore
from inkecho.app import Session
from inkecho.ui.information import CompatibilityPage
app=QApplication([])
with tempfile.TemporaryDirectory(prefix='inkecho-test-') as p:
 store=ConfigStore(Path(p));store.initialize();session=Session(store);page=CompatibilityPage(session)
 print('router',type(session.inputs).__name__,flush=True)
 page.output_method.setCurrentIndex(page.output_method.findData('owned_auto'))
 print('configured',store.load_settings().output_method,flush=True)
 for action in ('install','enable','status'):
  asyncio.run(page.owned_action(action))
  print(json.dumps({'action':action,'message':page.message.text(),'status':page.owned_status.text()},ensure_ascii=False),flush=True)
 page.close()
