from pathlib import Path
import sys,os,json,subprocess,asyncio,time
p=Path('/home/inkecho/owned-auto-r5');assert Path('/etc/machine-id').read_text().strip()=='80d223263a5e4ed1b8749d7f30116d5f'
os.environ['PYTHONPATH']=str(p/'source')+':/home/inkecho/inkecho-release-0.10.0-r1/extracted-r1/squashfs-root/packages'
sys.path[:0]=[str(p/'source'),'/home/inkecho/inkecho-release-0.10.0-r1/extracted-r1/squashfs-root/packages']
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
 result=p/'state.json';env=dict(os.environ);env['GDK_BACKEND']='wayland';env.pop('GTK_IM_MODULE',None)
 log=(p/'actor.log').open('x');actor=subprocess.Popen(['/usr/bin/python3',str(p/'actor.py'),str(result)],env=env,stdin=subprocess.PIPE,text=True,stdout=log,stderr=subprocess.STDOUT);rows=[];engine=subprocess.check_output(['ibus','engine'],text=True).strip();r=None
 def state():return json.loads(result.read_text())
 def record(case,**kw):row={'case':case,'state':state(),**kw};rows.append(row);print(json.dumps(row),flush=True)
 async def focus(field):actor.stdin.write(field+'\n');actor.stdin.flush();await asyncio.sleep(.3)
 try:
  for _ in range(100):
   if result.exists() and state().get('active'):break
   await asyncio.sleep(.05)
  assert call('Arm','(u)',[actor.pid])==(True,)
  k=CountingHybrid();r=OwnedAutoOutputRouter(k);await r.prepare_task('auto');assert r.selected=='keyboard'
  record('native_probe',proof=await probe_owned())
  try:
   async with r.output_session():
    await r.insert('甲',lambda:True,deadline=time.monotonic()+8);await r.insert('乙',lambda:True,deadline=time.monotonic()+8);record('native_selected',selected=r.selected)
  except OutputRouterError as e:assert e.code=='ibus_delivery_unknown'
  await asyncio.sleep(.4);record('normal',keyboard_connects=k.connects);assert state()['text']['native']=='甲乙' and k.connects==0
  await r.aclose();r=None
  probe_count=0;failures=[]
  async def switching_probe():
   nonlocal probe_count
   value=await probe_owned();probe_count+=1
   if probe_count==2:await focus('simple')
   return value
  class ObservedOwned(IBusBridge):
   async def insert(self,*args,**kwargs):
    try:return await super().insert(*args,**kwargs)
    except IBusBridgeError as e:failures.append({'code':e.code,'attempts':e.acknowledged_attempts});raise
  k=CountingHybrid();r=OwnedAutoOutputRouter(k,owned_probe=switching_probe,owned_factory=ObservedOwned);await r.prepare_task('auto')
  async with r.output_session():
   assert await r.insert('丙丁',lambda:True,deadline=time.monotonic()+15)==2
   record('real_zero_fallback',selected=r.selected,failures=failures,keyboard_connects=k.connects)
  await asyncio.sleep(.5);record('fallback_actual');assert state()['text']['simple']=='丙丁' and failures==[{'code':'no_service','attempts':0}]
  await r.aclose();r=None
  await focus('native');probe_count=0;active=True;k=CountingHybrid();r=OwnedAutoOutputRouter(k,owned_probe=switching_probe,owned_factory=ObservedOwned);await r.prepare_task('auto')
  def stop_after_first(_at):
   nonlocal active
   active=False
  try:
   async with r.output_session():await r.insert('戊己',lambda:active,deadline=time.monotonic()+15,on_first_sent=stop_after_first)
  except KeyboardError as e:record('fallback_cancel',code=e.code,keyboard_connects=k.connects)
  else:raise AssertionError('fallback cancel accepted')
  await r.aclose();r=None;await asyncio.sleep(1.3);record('fallback_cancel_tail');assert state()['text']['simple']=='丙丁戊'
  await focus('native');active=True
  async def stopped_probe():
   nonlocal active
   proof=await probe_owned();active=False;return proof
  k=CountingHybrid();r=OwnedAutoOutputRouter(k,owned_probe=stopped_probe);await r.prepare_task('auto')
  try:
   async with r.output_session():await r.insert('丁',lambda:active,deadline=time.monotonic()+8)
  except OutputRouterError as e:record('cancel_after_detection',code=e.code,keyboard_connects=k.connects);assert e.code=='input_cancelled' and k.connects==0
  else:raise AssertionError('cancel accepted')
  await r.aclose();r=None;await asyncio.sleep(1.3);assert state()['text']['native']=='甲乙'
  switch=subprocess.run(['ibus','engine','libpinyin']);await asyncio.sleep(.4);assert subprocess.check_output(['ibus','engine'],text=True).strip()=='libpinyin'
  for key in [110,105]:assert call('Key','(u)',[key])==(True,)
  await asyncio.sleep(.4);assert call('Read')==(True,True)
  record('blocked_probe',proof=await probe_owned(),preedit=call('Read'),switch_exit=switch.returncode)
  k=CountingHybrid();r=OwnedAutoOutputRouter(k);await r.prepare_task('auto')
  try:
   async with r.output_session():await r.insert('戊',lambda:True,deadline=time.monotonic()+8)
  except OutputRouterError as e:record('auto_preedit',code=e.code,keyboard_connects=k.connects);assert e.code=='ibus_delivery_unknown' and k.connects==0
  else:raise AssertionError('composition overwritten')
  await r.aclose();r=None;assert call('Read')==(True,True);assert call('Key','(u)',[32])==(True,);await asyncio.sleep(.5);record('composition_preserved');assert state()['text']['native']=='甲乙你'
 finally:
  if r:await r.aclose()
  subprocess.run(['ibus','engine',engine],check=False);actor.stdin.write('quit\n');actor.stdin.flush();print(json.dumps({'actor':actor.pid,'exit':actor.wait(timeout=5),'engine':subprocess.check_output(['ibus','engine'],text=True).strip()}),flush=True);log.close();(p/'rows.json').write_text(json.dumps(rows,indent=2))
asyncio.run(main())
