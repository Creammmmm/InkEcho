from pathlib import Path
import os,sys,json,subprocess,asyncio,time,hashlib
p=Path('/home/inkecho/default-session26')
from PySide6.QtCore import QCoreApplication
qt=QCoreApplication([])
import inkecho.app as appmodule
from inkecho.app import Session
from inkecho.config import ConfigStore
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.output_router import OutputRouterError
from inkecho.platform.keyboard import KeyboardError
from inkecho.platform.owned_installation import installation_state,UUID
from inkecho.platform.owned_extension import OwnedExtensionManager
assert Path(appmodule.__file__).is_relative_to(p/'source')
clean=dict(os.environ)
for key in ['PYTHONHOME','PYTHONPATH','LD_LIBRARY_PATH','QT_PLUGIN_PATH','APPDIR']:clean.pop(key,None)
clean['PATH']='/usr/bin:/bin'
def cli(*args):return subprocess.run(args,env=clean,capture_output=True,text=True,check=True).stdout.strip()
def control(method,*args):return json.loads(cli('/usr/bin/python3',str(p/'control.py'),method,*map(str,args)))
def setting(key,value):cli('/usr/bin/gsettings','set','org.gnome.shell',key,value)
def switches():return {key:cli('/usr/bin/gsettings','get','org.gnome.shell',key) for key in ['enabled-extensions','disabled-extensions','disable-user-extensions']}
rows=[];actor=None;log=None;session=None;serial=0
async def receiver(backend):
 global actor,log,statefile
 statefile=p/(backend+'-state.json');env=dict(clean);env['GDK_BACKEND']=backend;env.pop('GTK_IM_MODULE',None)
 if backend=='x11':env['GTK_IM_MODULE']='gtk-im-context-simple'
 log=(p/(backend+'-actor.log')).open('x');actor=subprocess.Popen(['/usr/bin/python3',str(p/'actor.py'),str(statefile)],env=env,stdin=subprocess.PIPE,text=True,stdout=log,stderr=subprocess.STDOUT)
 for _ in range(100):
  if statefile.exists() and json.loads(statefile.read_text()).get('active'):break
  qt.processEvents();await asyncio.sleep(.05)
 assert json.loads(statefile.read_text())['active']
def record(case,**kw):
 row={'case':case,'state':json.loads(statefile.read_text()),**kw};rows.append(row);print(json.dumps(row),flush=True)
async def close_receiver():
 global actor,log
 if actor:
  actor.stdin.write('quit\n');actor.stdin.flush();print(json.dumps({'actor':actor.pid,'exit':actor.wait(timeout=5)}),flush=True);actor=None;log.close()
def new_session():
 global serial,session
 serial+=1;session=Session(store=ConfigStore(p/('private-session-'+str(serial))))
 assert type(session.inputs) is DefaultAutoOutputRouter
 assert session.settings.output_method=='auto'
 return session
async def deliver(text,cancel=False):
 s=new_session();epoch=s.epoch
 assert await s.authorize_input(s.settings.output_method)
 def first(_at):
  if cancel:s.cancel()
 code=None
 try:
  async with s.inputs.output_session():
   count=await s.inputs.insert(text,lambda:s.epoch==epoch,deadline=time.monotonic()+15,on_first_sent=first)
   record('selected',router=type(s.inputs).__name__,selected=s.inputs.selected,count=count)
 except KeyboardError as error:
  code=error.code;record('output_diagnostic',code=code,attempts=getattr(error,'acknowledged_attempts',0))
 finally:
  await s.close()
  globals()['session']=None
 return code
async def main():
 engine=cli('/usr/bin/ibus','engine')
 try:
  print(json.dumps({'app_source':appmodule.__file__,'app_sha256':hashlib.sha256(Path(appmodule.__file__).read_bytes()).hexdigest(),'python':sys.version,'default_router':appmodule.OutputRouter.__name__}),flush=True)
  OwnedExtensionManager().enable();cli('/usr/bin/gnome-extensions','enable','inkecho-v3-fixture@local.invalid');await asyncio.sleep(.3)
  assert await installation_state()=='enabled'
  await receiver('wayland');assert control('Arm',actor.pid)==[True]
  assert await deliver('甲乙')=='ibus_delivery_unknown';await asyncio.sleep(.4);record('installed_native',installation=await installation_state(),switches=switches());assert json.loads(statefile.read_text())['text']['native']=='甲乙'
  assert await deliver('丙丁',cancel=True) in {'ibus_cancelled','input_cancelled'};await asyncio.sleep(1.3);record('session_cancel_tail');assert json.loads(statefile.read_text())['text']['native']=='甲乙丙'
  subprocess.run(['/usr/bin/ibus','engine','libpinyin'],env=clean,capture_output=True);await asyncio.sleep(.4);assert cli('/usr/bin/ibus','engine')=='libpinyin'
  assert control('Key',110)==[True];assert control('Key',105)==[True];await asyncio.sleep(.4);assert control('Read')==[True,True]
  assert await deliver('戊')=='ibus_delivery_unknown';assert control('Read')==[True,True];assert control('Key',32)==[True];await asyncio.sleep(.5);record('session_preedit_preserved');assert json.loads(statefile.read_text())['text']['native']=='甲乙丙你'
  cli('/usr/bin/ibus','engine',engine);await close_receiver();await receiver('x11')
  setting('disabled-extensions',repr([UUID]));await asyncio.sleep(.4);assert await installation_state()=='disabled'
  assert await deliver('己庚') is None;await asyncio.sleep(.4);record('disabled_list_fallback',installation=await installation_state(),switches=switches());assert json.loads(statefile.read_text())['text']['native']=='己庚'
  setting('disabled-extensions','[]');setting('disable-user-extensions','true');await asyncio.sleep(.4);assert await installation_state()=='disabled'
  assert await deliver('辛') is None;await asyncio.sleep(.4);record('global_disabled_fallback',installation=await installation_state(),switches=switches());assert json.loads(statefile.read_text())['text']['native']=='己庚辛'
  setting('disable-user-extensions','false');OwnedExtensionManager().enable();await asyncio.sleep(.4);assert await installation_state()=='enabled'
  assert await deliver('壬癸') is None;await asyncio.sleep(.4);record('enabled_xwayland_fallback',installation=await installation_state());assert json.loads(statefile.read_text())['text']['native']=='己庚辛壬癸'
 finally:
  if session:await session.close()
  subprocess.run(['/usr/bin/ibus','engine',engine],env=clean,capture_output=True)
  await close_receiver();(p/'rows.json').write_text(json.dumps(rows,indent=2))
asyncio.run(main())
