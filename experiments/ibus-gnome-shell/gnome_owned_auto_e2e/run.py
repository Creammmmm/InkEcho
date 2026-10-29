from pathlib import Path
import sys,os,json,subprocess,asyncio,time
p=Path('/home/inkecho/owned-auto');assert Path('/etc/machine-id').read_text().strip()=='80d223263a5e4ed1b8749d7f30116d5f'
sys.path[:0]=[str(p/'source'),'/home/inkecho/inkecho-release-0.10.0-r1/extracted-r1/squashfs-root/packages']
os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
from inkecho.platform.ibus_owned_auto import OwnedAutoOutputRouter,probe_owned
from inkecho.platform.output_router import OutputRouterError
from inkecho.platform.keyboard import KeyboardError
import gi
gi.require_version('Gio','2.0');from gi.repository import Gio,GLib
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None);n='io.github.Creammmmm.InkEcho.V3Fixture'
def call(m,sig=None,args=None):return bus.call_sync(n,'/io/github/Creammmmm/InkEcho/V3Fixture',n+'1',m,GLib.Variant(sig,args) if sig else None,None,Gio.DBusCallFlags.NO_AUTO_START,2000,None).unpack()
class NoSendKeyboard:
 authorized=False
 def __init__(self):self.connects=0;self.sent=0
 async def connect(self):self.connects+=1;raise KeyboardError('unsupported_target')
 async def aclose(self):pass
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
  k=NoSendKeyboard();r=OwnedAutoOutputRouter(k);await r.prepare_task('auto');assert r.selected=='keyboard'
  record('native_probe',proof=await probe_owned())
  try:
   async with r.output_session():
    await r.insert('甲',lambda:True,deadline=time.monotonic()+8);await r.insert('乙',lambda:True,deadline=time.monotonic()+8);record('native_selected',selected=r.selected)
  except OutputRouterError as e:assert e.code=='ibus_delivery_unknown'
  await asyncio.sleep(.4);record('normal',keyboard_connects=k.connects);assert state()['text']['native']=='甲乙' and k.connects==0
  await r.aclose();r=None
  await focus('button');assert await probe_owned() is None
  k=NoSendKeyboard();r=OwnedAutoOutputRouter(k);await r.prepare_task('auto')
  try:
   async with r.output_session():await r.insert('丙',lambda:True,deadline=time.monotonic()+8)
  except KeyboardError as e:record('no_target',code=e.code,keyboard_connects=k.connects);assert e.code=='unsupported_target' and k.connects==1
  else:raise AssertionError('no target accepted')
  await r.aclose();r=None
  await focus('native');active=True
  async def stopped_probe():
   nonlocal active
   proof=await probe_owned();active=False;return proof
  k=NoSendKeyboard();r=OwnedAutoOutputRouter(k,owned_probe=stopped_probe);await r.prepare_task('auto')
  try:
   async with r.output_session():await r.insert('丁',lambda:active,deadline=time.monotonic()+8)
  except OutputRouterError as e:record('cancel_after_detection',code=e.code,keyboard_connects=k.connects);assert e.code=='input_cancelled' and k.connects==0
  else:raise AssertionError('cancel accepted')
  await r.aclose();r=None;await asyncio.sleep(1.3);assert state()['text']['native']=='甲乙'
  switch=subprocess.run(['ibus','engine','libpinyin']);await asyncio.sleep(.4);assert subprocess.check_output(['ibus','engine'],text=True).strip()=='libpinyin'
  for key in [110,105]:assert call('Key','(u)',[key])==(True,)
  await asyncio.sleep(.4);assert call('Read')==(True,True)
  record('blocked_probe',proof=await probe_owned(),preedit=call('Read'),switch_exit=switch.returncode)
  k=NoSendKeyboard();r=OwnedAutoOutputRouter(k);await r.prepare_task('auto')
  try:
   async with r.output_session():await r.insert('戊',lambda:True,deadline=time.monotonic()+8)
  except OutputRouterError as e:record('auto_preedit',code=e.code,keyboard_connects=k.connects);assert e.code=='ibus_delivery_unknown' and k.connects==0
  else:raise AssertionError('composition overwritten')
  await r.aclose();r=None;assert call('Read')==(True,True);assert call('Key','(u)',[32])==(True,);await asyncio.sleep(.5);record('composition_preserved');assert state()['text']['native']=='甲乙你'
 finally:
  if r:await r.aclose()
  subprocess.run(['ibus','engine',engine],check=False);actor.stdin.write('quit\n');actor.stdin.flush();print(json.dumps({'actor':actor.pid,'exit':actor.wait(timeout=5),'engine':subprocess.check_output(['ibus','engine'],text=True).strip()}),flush=True);log.close();(p/'rows.json').write_text(json.dumps(rows,indent=2))
asyncio.run(main())
