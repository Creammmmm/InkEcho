import asyncio,hashlib,json,os,subprocess,time
from pathlib import Path
import gi
gi.require_version('Gtk','3.0'); gi.require_version('GdkX11','3.0'); gi.require_version('IBus','1.0')
from gi.repository import Gtk,GdkX11,IBus
from inkecho.platform.ibus import IBusBridge,IBusBridgeError
import inkecho.platform.ibus as module
IBus.init();bus=IBus.Bus.new()
def engine():
 d=bus.get_global_engine();return d.get_name() if d else None
async def pump(s):
 end=time.monotonic()+s
 while time.monotonic()<end:
  while Gtk.events_pending():Gtk.main_iteration_do(False)
  await asyncio.sleep(.01)
async def focus(w,e):
 w.present();e.grab_focus();await pump(.2)
 if os.environ.get('GDK_BACKEND')=='x11':subprocess.run(['xdotool','windowactivate',str(GdkX11.X11Window.get_xid(w.get_window()))],check=True)
 await pump(.5);assert w.is_active() and e.has_focus(),'owned_focus_missing'
async def main():
 report={'passed':False,'synthetic_fixed_text':True,'clipboard':False,'module':module.__file__,'module_sha256':hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),'engine_before':engine()};bridge=None;wins=[]
 try:
  for title in ['InkEcho candidate A','InkEcho candidate B']:
   w=Gtk.Window(title=title);e=Gtk.Entry();w.add(e);w.set_default_size(450,120);w.show_all();wins.append((w,e))
  await pump(.4);await focus(*wins[0]);bridge=IBusBridge();await bridge.connect();await bridge.insert('甲',lambda:True);await pump(.4);assert wins[0][1].get_text()=='甲','first_text_mismatch'
  await focus(*wins[1]);await bridge.insert('乙丙',lambda:True);await pump(.4);assert wins[1][1].get_text()=='乙丙','second_text_mismatch'
  try:await bridge.insert('丁',lambda:False);raise AssertionError('cancel_did_not_stop')
  except IBusBridgeError as error:assert error.code=='cancelled'
  await pump(.4);assert wins[1][1].get_text()=='乙丙';report.update(passed=True,first_codepoints=[ord(c) for c in wins[0][1].get_text()],second_codepoints=[ord(c) for c in wins[1][1].get_text()],cancel_stopped=True)
 except Exception as e:report['error']=type(e).__name__+':'+str(e)
 finally:
  if bridge:await bridge.aclose()
  report['engine_after']=engine();report['engine_unchanged']=report['engine_before']==report['engine_after'];report['capabilities_remaining']=[p.name for p in Path(os.environ['XDG_RUNTIME_DIR']).glob('*cap-*')]
  Path('/mnt/output/input26.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));
  for w,e in wins:w.destroy()
 return report['passed']
raise SystemExit(0 if asyncio.run(main()) else 1)
