from pathlib import Path
import sys,os,json,subprocess,asyncio,time
p=Path('/home/inkecho/owned-e2e');assert Path('/etc/machine-id').read_text().strip()=='80d223263a5e4ed1b8749d7f30116d5f'
sys.path[:0]=[str(p/'source'),'/home/inkecho/inkecho-release-0.10.0-r1/extracted-r1/squashfs-root/packages']
os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
from inkecho.platform.ibus_owned import IBusBridge,IBusBridgeError
import gi
gi.require_version('Gio','2.0');from gi.repository import Gio,GLib
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None);n='io.github.Creammmmm.InkEcho.V3Fixture'
def call(m,sig=None,args=None):return bus.call_sync(n,'/io/github/Creammmmm/InkEcho/V3Fixture',n+'1',m,GLib.Variant(sig,args) if sig else None,None,Gio.DBusCallFlags.NO_AUTO_START,2000,None).unpack()
async def main():
 result=p/'state.json';env=dict(os.environ);env['GDK_BACKEND']='wayland';env.pop('GTK_IM_MODULE',None)
 log=(p/'actor.log').open('x');actor=subprocess.Popen(['/usr/bin/python3',str(p/'actor.py'),str(result)],env=env,stdin=subprocess.PIPE,text=True,stdout=log,stderr=subprocess.STDOUT);bridge=None;rows=[]
 engine=subprocess.check_output(['ibus','engine'],text=True).strip()
 def state():return json.loads(result.read_text())
 def record(case,**kw):
  row={'case':case,'state':state(),**kw};rows.append(row);print(json.dumps(row),flush=True)
 async def focus(field):actor.stdin.write(field+'\n');actor.stdin.flush();await asyncio.sleep(.3)
 try:
  for _ in range(100):
   if result.exists() and state().get('active'):break
   await asyncio.sleep(.05)
  assert call('Arm','(u)',[actor.pid])==(True,)
  bridge=IBusBridge();await bridge.connect();record('authenticated',owner=bridge._client._owner,pid=actor.pid)
  assert await bridge.insert('甲',lambda:True,deadline=time.monotonic()+5)==1
  assert await bridge.insert('乙',lambda:True,deadline=time.monotonic()+5)==1
  await asyncio.sleep(.4);record('normal_fragments',sequence=bridge._client._sequence);assert state()['text']['native']=='甲乙';await bridge.aclose();bridge=None
  await focus('simple');bridge=IBusBridge();await bridge.connect()
  try:await bridge.insert('丙',lambda:True,deadline=time.monotonic()+5)
  except IBusBridgeError as e:record('known_zero',code=e.code,sequence=bridge._client._sequence);assert e.code=='no_service' and bridge._client._sequence==0
  else:raise AssertionError('unsupported target sent')
  await bridge.close_after_no_service();bridge=None
  await focus('native');bridge=IBusBridge();await bridge.connect();assert await bridge.insert('丁',lambda:True,deadline=time.monotonic()+5)==1
  try:await bridge.insert('戊',lambda:False,deadline=time.monotonic()+5)
  except IBusBridgeError as e:record('cancel_after_first',code=e.code);assert e.code=='cancelled'
  else:raise AssertionError('cancel accepted')
  await bridge.aclose();bridge=None;await asyncio.sleep(1.3);record('cancel_tail');assert state()['text']['native']=='甲乙丁'
  subprocess.run(['ibus','engine','libpinyin'],check=True);await asyncio.sleep(.4)
  assert call('Key','(u)',[110])==(True,);assert call('Key','(u)',[105])==(True,);await asyncio.sleep(.4);assert call('Read')==(True,True)
  bridge=IBusBridge();await bridge.connect()
  try:await bridge.insert('己',lambda:True,deadline=time.monotonic()+5)
  except IBusBridgeError as e:record('live_preedit',code=e.code,sequence=bridge._client._sequence,preedit=call('Read'));assert e.code=='delivery_unknown' and bridge._client._sequence==0
  else:raise AssertionError('composition overwritten')
  await bridge.aclose();bridge=None;assert call('Read')==(True,True);assert call('Key','(u)',[32])==(True,);await asyncio.sleep(.5);record('preedit_preserved');assert state()['text']['native']=='甲乙丁你'
 finally:
  if bridge:await bridge.aclose()
  subprocess.run(['ibus','engine',engine],check=False)
  actor.stdin.write('quit\n');actor.stdin.flush();print(json.dumps({'actor':actor.pid,'exit':actor.wait(timeout=5),'restored_engine':subprocess.check_output(['ibus','engine'],text=True).strip()}),flush=True);log.close();(p/'rows.json').write_text(json.dumps(rows,indent=2))
asyncio.run(main())
