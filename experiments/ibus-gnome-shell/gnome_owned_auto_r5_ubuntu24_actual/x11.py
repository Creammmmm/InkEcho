from pathlib import Path
import sys,os,json,subprocess,asyncio,time
p=Path('/home/inkecho/owned-auto24');assert Path('/etc/machine-id').read_text().strip()=='5f18d1e571c14b3ab94646a8664e7595'
os.environ['PYTHONPATH']=str(p/'source')+':/home/inkecho/owned-auto24/deps'
sys.path[:0]=[str(p/'source'),'/home/inkecho/owned-auto24/deps']
os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
from inkecho.platform.ibus_owned_auto import OwnedAutoOutputRouter,probe_owned
from inkecho.platform.output_router import OutputRouterError
from inkecho.platform.keyboard import KeyboardError
from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
from inkecho.platform.ibus_owned import IBusBridge,IBusBridgeError
import gi
gi.require_version('Gio','2.0');from gi.repository import Gio,GLib
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None);n='io.github.Creammmmm.InkEcho.V3Fixture'
def call(m,sig=None,args=None):return bus.call_sync(n,'/io/github/Creammmmm/InkEcho/V3Fixture',n+'1',m,GLib.Variant(sig,args) if sig else None,None,Gio.DBusCallFlags.NO_AUTO_START,2000,None).unpack()
class CountingHybrid(HybridKeyboardInput):
 def __init__(self):super().__init__();self.connects=0
 async def connect(self):self.connects+=1;await super().connect()
async def main():
 result=p/'x11-state.json';env=dict(os.environ);env['GDK_BACKEND']='x11';env['GTK_IM_MODULE']='gtk-im-context-simple'
 log=(p/'x11-actor.log').open('x');actor=subprocess.Popen(['/usr/bin/python3',str(p/'actor.py'),str(result)],env=env,stdin=subprocess.PIPE,text=True,stdout=log,stderr=subprocess.STDOUT);rows=[];r=None
 def state():return json.loads(result.read_text())
 def record(case,**kw):row={'case':case,'state':state(),**kw};rows.append(row);print(json.dumps(row),flush=True)
 try:
  for _ in range(100):
   if result.exists() and state().get('active'):break
   await asyncio.sleep(.05)
  proof=await probe_owned();record('xwayland_probe',proof=proof,pid=actor.pid);assert proof is None
  k=CountingHybrid();r=OwnedAutoOutputRouter(k);await r.prepare_task('auto')
  async with r.output_session():
   assert await r.insert('丙丁',lambda:True,deadline=time.monotonic()+15)==2
   record('xwayland_fallback',selected=r.selected,xonly=k._xonly,keyboard_connects=k.connects)
  await r.aclose();r=None;await asyncio.sleep(.4);assert state()['text']['native']=='丙丁'
  active=True;k=CountingHybrid();r=OwnedAutoOutputRouter(k);await r.prepare_task('auto')
  def stop(_at):
   nonlocal active
   active=False
  try:
   async with r.output_session():await r.insert('戊己',lambda:active,deadline=time.monotonic()+15,on_first_sent=stop)
  except KeyboardError as e:record('xwayland_cancel',code=e.code)
  else:raise AssertionError('cancel accepted')
  await r.aclose();r=None;await asyncio.sleep(1.3);record('xwayland_tail');assert state()['text']['native']=='丙丁戊'
 finally:
  if r:await r.aclose()
  actor.stdin.write('quit\n');actor.stdin.flush();print(json.dumps({'actor':actor.pid,'exit':actor.wait(timeout=5)}),flush=True);log.close();(p/'x11-rows.json').write_text(json.dumps(rows,indent=2))
asyncio.run(main())
