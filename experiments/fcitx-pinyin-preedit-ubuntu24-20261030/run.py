from pathlib import Path
import asyncio,json,os,subprocess,sys,time,hashlib
p=Path.home()/'fcitx-pinyin24';sys.path[:0]=[str(p/'src'),str(p/'deps')]
os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
from inkecho.platform import fcitx5_staging
from inkecho.platform.fcitx5_install import FcitxInstaller
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
from inkecho.platform.output_router import OutputRouterError
from inkecho.platform.keyboard import KeyboardError
expected='acd896aae8ab38ecca2685c0dd8639f2910e841176eadccf59ee4943b158c4de';assert hashlib.sha256((p/'candidate/candidate/libinkecho.so').read_bytes()).hexdigest()==expected
os.umask(0o077)
for folder in [p/'candidate',p/'candidate/candidate']:folder.chmod(0o700)
for file in (p/'candidate').rglob('*'):
 if file.is_file():file.chmod(0o600)
# Authorized test-only qualification override; never written to shared source.
fcitx5_staging.TESTED_CANDIDATE_SHA256=expected
work=p/'actual-pinyin-r6';work.mkdir(mode=0o700);state=work/'actor.json';data=work/'data';data.mkdir(mode=0o700);rows=[];daemon=None;actor=None
os.environ.update(GTK_IM_MODULE='fcitx',QT_IM_MODULE='fcitx',XMODIFIERS='@im=fcitx',XDG_DATA_HOME=str(data),XDG_CONFIG_HOME=str(work/'config'),XDG_CACHE_HOME=str(work/'cache'))
def record(name,**kw):rows.append({'case':name,**kw});(work/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows[-1]),flush=True)
def read():return json.loads(state.read_text())
async def key(value,mods=0):
 actor.stdin.write(json.dumps({'action':'xkey','value':value,'state':mods})+'\n');actor.stdin.flush();await asyncio.sleep(.25)
async def output(text,cancel=False):
 r=DefaultAutoOutputRouter(HybridKeyboardInput());await r.prepare_task('auto');active=True;result={}
 def first(_):
  nonlocal active
  if cancel:active=False
 try:
  async with r.output_session():result['sent']=await r.insert(text,lambda:active,deadline=time.monotonic()+5,on_first_sent=first);result['route']=r.selected
 except (OutputRouterError,KeyboardError) as e:result.update(code=e.code,attempts=getattr(e,'acknowledged_attempts',0),route=r.selected)
 finally:await r.aclose()
 await asyncio.sleep(1.2 if cancel else .4);result['receiver']=read();return result
async def main():
 global daemon,actor
 install=FcitxInstaller(source=p/'candidate',data_home=data)
 hints=[line for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines() if line.split('=',1)[0] in {'XMODIFIERS','GTK_IM_MODULE','QT_IM_MODULE'}]
 (work/'hints-before.json').write_text(json.dumps(hints))
 try:
  subprocess.run(['systemctl','--user','set-environment','XMODIFIERS=@im=fcitx','GTK_IM_MODULE=fcitx','QT_IM_MODULE=fcitx'],check=True)
  install.install();record('staged',sha=expected,test_only_override=True,session=os.environ.get('XDG_SESSION_TYPE'))
  env=dict(os.environ);env.update(XDG_DATA_HOME=str(data),XDG_CONFIG_HOME=str(work/'config'),XDG_CACHE_HOME=str(work/'cache'))
  config=work/'config/fcitx5';config.mkdir(parents=True,mode=0o700,exist_ok=True)
  (config/'profile').write_text('[Groups/0]\nName=Default\nDefault Layout=us\nDefaultIM=pinyin\n\n[Groups/0/Items/0]\nName=keyboard-us\nLayout=\n\n[Groups/0/Items/1]\nName=pinyin\nLayout=\n\n[GroupOrder]\n0=Default\n')
  daemon=subprocess.Popen(['/usr/bin/fcitx5','-D','--disable','clipboard'],env=env,stdout=(work/'fcitx.log').open('w'),stderr=subprocess.STDOUT);await asyncio.sleep(2);assert daemon.poll() is None;install.enable()
  actor=subprocess.Popen(['/usr/bin/python3',str(p/'actor.py'),str(state)],env=os.environ.copy(),stdin=subprocess.PIPE,text=True,stdout=(work/'actor.log').open('w'),stderr=subprocess.STDOUT)
  for _ in range(100):
   if state.exists() and read()['active'] and read()['focus']:break
   if actor.poll() is not None:raise RuntimeError('actor exited')
   await asyncio.sleep(.1)
  assert read()['active'] and read()['focus'],read();record('ready',receiver=read())
  frontend=[line.split()[-1] for line in Path('/proc',str(actor.pid),'maps').read_text().splitlines() if 'im-fcitx5' in line]
  record('frontend_loaded',paths=sorted(set(frontend)));assert frontend
  normal=await output('甲乙');record('normal',**normal);assert normal.get('sent')==2 and normal['route']=='fcitx' and read()['text']=='甲乙'
  subprocess.run(['/usr/bin/fcitx5-remote','-s','pinyin'],check=True)
  subprocess.run(['/usr/bin/fcitx5-remote','-o'],check=True)
  engine=subprocess.check_output(['/usr/bin/fcitx5-remote','-n'],text=True).strip();record('active_engine',engine=engine);assert engine=='pinyin';await asyncio.sleep(.6)
  await key(ord('n'))
  firstkey=read();record('first_pinyin_key',receiver=firstkey)
  if firstkey['preedit_length']==0:
   assert firstkey['text']=='甲乙n',firstkey
   await key(ord('n'))
  else:assert firstkey['preedit_length']==1 and firstkey['text']=='甲乙',firstkey
  await key(ord('i'))
  for _ in range(30):
   if read()['preedit_length']>0:break
   await asyncio.sleep(.1)
  before=read();record('real_preedit_before',receiver=before);assert before['preedit_length']==2 and before['text'] in {'甲乙','甲乙n'},before
  guarded=await output('戊');record('guarded_during_pinyin',**guarded)
  assert guarded.get('code')=='fcitx_composition_active' and read()['text']==before['text'] and read()['preedit_length']==before['preedit_length'],guarded
  await key(32);await asyncio.sleep(.5)
  finished=read();record('user_finished_composition',receiver=finished);assert finished['preedit_length']==0 and finished['text']==before['text']+'你',finished
  composed=finished['text']
  cancelled=await output('己庚',True);record('cancel_after_prefix',**cancelled);assert read()['text']==composed+'己' and cancelled.get('attempts')==1
  record('normal_cancel_passed',value=True,preedit_verified=True)
 finally:
  if actor:
   if actor.poll() is None:actor.stdin.write('quit\n');actor.stdin.flush()
   try:record('actor_exit',exit=actor.wait(timeout=5))
   except subprocess.TimeoutExpired:
    actor.terminate();record('actor_terminated_after_timeout',exit=actor.wait(timeout=5))
  if daemon:
   if daemon.poll() is None:daemon.terminate()
   record('daemon_exit',exit=daemon.wait(timeout=5))
  try:install.disable()
  except Exception as e:record('disable_error',kind=type(e).__name__)
  subprocess.run(['systemctl','--user','unset-environment','XMODIFIERS','GTK_IM_MODULE','QT_IM_MODULE'],check=True)
  for value in hints:subprocess.run(['systemctl','--user','set-environment',value],check=True)
  restored=[line for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines() if line.split('=',1)[0] in {'XMODIFIERS','GTK_IM_MODULE','QT_IM_MODULE'}];record('hints_restored',value=sorted(restored)==sorted(hints));assert sorted(restored)==sorted(hints)
asyncio.run(main())
