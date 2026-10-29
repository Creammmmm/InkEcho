from pathlib import Path as _AuditPath
import json as _audit_json,hashlib as _audit_hash,sys as _audit_sys
_SR=_AuditPath('/mnt/input/product-r2/src')
_SM=_AuditPath('/mnt/input/product-r2/source-manifest.json')
assert _audit_hash.sha256(_SM.read_bytes()).hexdigest()=='c579575e8eee662403818db5395f9a5d2ceab57b002b9135289bff9910fdccfd'
_SI=_audit_json.loads(_SM.read_text())
assert {p.relative_to(_SR).as_posix()for p in _SR.rglob('*')if p.is_file()}==set(_SI)
assert all(not (_SR/n).is_symlink()and _audit_hash.sha256((_SR/n).read_bytes()).hexdigest()==h for n,h in _SI.items())
_audit_sys.path.insert(0,str(_SR))
"""Actual published-package output router to own offline Chrome fields only."""
from pathlib import Path
import asyncio,json,os,subprocess,sys,time,hashlib
p=Path('/mnt/input');appdir=Path(os.environ['APPDIR']);candidate=Path('/mnt/input/batch-candidate')
os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
from inkecho.platform import fcitx5_staging
from inkecho.platform.fcitx5_install import FcitxInstaller
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.wayland_keyboard import keyboard_for_desktop
from inkecho.platform.output_router import OutputRouterError
from inkecho.platform.keyboard import KeyboardError
from session_product_r2 import probe
expected='f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44';assert hashlib.sha256((candidate/'candidate/libinkecho.so').read_bytes()).hexdigest()==expected
os.umask(0o077)
fcitx5_staging.TESTED_CANDIDATE_SHA256=expected
label=os.environ.get('INKECHO_OUTPUT_STAGE','default');work=Path('/run/user/1000/inkecho-package-gate-0.11.0')/('fcitx-'+label);work.mkdir(mode=0o700);state=work/'actor.json';data=work/'data';data.mkdir(mode=0o700);rows=[];daemon=None;actor=None
os.environ['GDK_BACKEND']='x11'
os.environ.update(GTK_IM_MODULE='fcitx',QT_IM_MODULE='fcitx',XMODIFIERS='@im=fcitx',XDG_DATA_HOME=str(data),XDG_CONFIG_HOME=str(work/'config'),XDG_CACHE_HOME=str(work/'cache'))
def record(name,**kw):rows.append({'case':name,**kw});(work/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows[-1]),flush=True)
def read():return json.loads(state.read_text())
keyseq=0
async def key(value,mods=0):
 global keyseq
 assert mods==0 and value in {97,110,105,32}
 before=read();assert before['active'] and before['focus'],before
 keyseq+=1;share=Path('/mnt/output/gtk-product-r2-mailbox');share.mkdir(mode=0o700,exist_ok=True);request=share/'key-request.json';temporary=share/'key-request.tmp'
 temporary.write_text(json.dumps({'sequence':keyseq,'keyval':value,'owned_pid':before['pid'],'owned_active':before['active'],'owned_focus':before['focus']}));temporary.replace(request)
 for _ in range(150):
  ack=share/'key-ack.json'
  if ack.exists() and json.loads(ack.read_text()).get('sequence')==keyseq:
   assert json.loads(ack.read_text())['qmp_ok'];break
  await asyncio.sleep(.05)
 else:raise RuntimeError('virtual keyboard acknowledgement timeout')
 await asyncio.sleep(.5)
output_index=0
async def output(text,cancel=False):
 global output_index
 output_index+=1
 r=DefaultAutoOutputRouter(keyboard_for_desktop())
 result=await probe(r,text,work/('session-'+str(output_index)),case='cancel'if cancel else'normal')
 result['route_during_dispatch']=[d.get('route_after')for d in result['dispatches']];result['route']=next((r for r in reversed(result['route_during_dispatch'])if r),None)
 result.update(sent=result['reported_characters'],code=result['input_failure'],attempts=result['reported_characters'] or 0,receiver=read())
 await asyncio.sleep(1.3 if cancel else .4);result['receiver']=read();return result
async def main():
 global daemon,actor
 install=FcitxInstaller(source=candidate,data_home=data)
 hints=[line for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines() if line.split('=',1)[0] in {'XMODIFIERS','GTK_IM_MODULE','QT_IM_MODULE'}]
 (work/'hints-before.json').write_text(json.dumps(hints))
 try:
  subprocess.run(['systemctl','--user','set-environment','XMODIFIERS=@im=fcitx','GTK_IM_MODULE=fcitx','QT_IM_MODULE=fcitx'],check=True)
  install.install();record('staged',sha=expected,test_only_override=True,session=os.environ.get('XDG_SESSION_TYPE'))
  env=dict(os.environ);env.update(XDG_DATA_HOME=str(data),XDG_CONFIG_HOME=str(work/'config'),XDG_CACHE_HOME=str(work/'cache'))
  config=work/'config/fcitx5';config.mkdir(parents=True,mode=0o700,exist_ok=True)
  (config/'profile').write_text('[Groups/0]\nName=Default\nDefault Layout=us\nDefaultIM=pinyin\n\n[Groups/0/Items/0]\nName=keyboard-us\nLayout=\n\n[Groups/0/Items/1]\nName=pinyin\nLayout=\n\n[GroupOrder]\n0=Default\n')
  daemon_env=dict(env)
  for k in ['PYTHONHOME','PYTHONPATH','LD_LIBRARY_PATH','QT_PLUGIN_PATH']:daemon_env.pop(k,None)
  daemon=subprocess.Popen(['/usr/bin/fcitx5','-D','--disable','clipboard'],env=daemon_env,stdout=(work/'fcitx.log').open('w'),stderr=subprocess.STDOUT);await asyncio.sleep(2);assert daemon.poll() is None;install.enable()
  actor_env=dict(daemon_env);actor_env['GDK_BACKEND']='x11'
  actor=subprocess.Popen(['/usr/bin/python3',str(p/'return-gtk-actor.py'),str(state)],env=actor_env,stdin=subprocess.PIPE,text=True,stdout=(work/'actor.log').open('w'),stderr=subprocess.STDOUT)
  await asyncio.sleep(.3)
  ids=subprocess.check_output(['xdotool','search','--all','--onlyvisible','--pid',str(actor.pid),'--name','^InkEcho owned Fcitx guard acceptance$'],env=actor_env,text=True).split();assert len(ids)==1,ids
  subprocess.run(['xdotool','windowactivate','--sync',ids[0]],env=actor_env,check=True,timeout=5)
  record('owned_activation',pid=actor.pid,xid=int(ids[0]),fixture_only=True)
  for _ in range(100):
   if state.exists() and read()['active'] and read()['focus']:break
   if actor.poll() is not None:raise RuntimeError('actor exited')
   await asyncio.sleep(.1)
  assert read()['active'] and read()['focus'],read();record('ready',receiver=read())
  frontend=[line.split()[-1] for line in Path('/proc',str(actor.pid),'maps').read_text().splitlines() if 'im-fcitx5' in line]
  record('frontend_loaded',paths=sorted(set(frontend)));assert frontend
  normal=await output('甲乙');record('normal',**normal);assert normal.get('sent')==2 and normal['route']=='fcitx' and read()['text']=='甲乙'
  subprocess.run(['/usr/bin/fcitx5-remote','-s','keyboard-us'],check=True)
  subprocess.run(['/usr/bin/fcitx5-remote','-c'],check=True)
  await asyncio.sleep(.5);await key(ord('a'));await asyncio.sleep(1)
  control=read();record('virtual_hardware_control',receiver=control)
  assert control['text']=='甲乙a' and any(e['keyval']==ord('a') for e in control['owned_events']),control
  subprocess.run(['/usr/bin/fcitx5-remote','-s','pinyin'],check=True)
  subprocess.run(['/usr/bin/fcitx5-remote','-o'],check=True)
  engine=subprocess.check_output(['/usr/bin/fcitx5-remote','-n'],text=True).strip();record('active_engine',engine=engine);assert engine=='pinyin';await asyncio.sleep(.6)
  await key(ord('n'))
  firstkey=read();record('first_pinyin_key',receiver=firstkey)
  if firstkey['preedit_length']==0:
   assert firstkey['text'] in {'甲乙a','甲乙an'},firstkey
   await key(ord('n'))
  else:assert firstkey['preedit_length']==1 and firstkey['text']=='甲乙a',firstkey
  await key(ord('i'))
  for _ in range(30):
   if read()['preedit_length']>0:break
   await asyncio.sleep(.1)
  before=read();record('real_preedit_before',receiver=before);assert before['preedit_length']==2 and before['text'] in {'甲乙a','甲乙an'},before
  guard_keys=list(before['owned_events']);guarded=await output('\n庚');record('guarded_during_pinyin',**guarded)
  assert read()['owned_events']==guard_keys;assert guarded.get('code')=='fcitx_composition_active' and read()['text']==before['text'] and read()['preedit_length']==before['preedit_length'],guarded
  await key(32);await asyncio.sleep(.5)
  finished=read();record('user_finished_composition',receiver=finished);assert finished['preedit_length']==0 and finished['text']==before['text']+'你',finished
  composed=finished['text']
  lf=await output('\n庚');record('gtk_stream_lf_neighbor',**lf);assert lf.get('sent')==2 and read()['text']==composed+'\n庚';composed+='\n庚'
  returns=[e for e in read()['owned_events'] if e['keyval']==65293];assert len(returns)==0,returns
  cancelled=await output('\n庚辛',True);record('cancel_after_prefix',**cancelled);assert read()['text']==composed+'\n庚' and cancelled.get('attempts')==2
  record('normal_cancel_passed',value=True,preedit_verified=True)
  actor.stdin.write('quit\n');actor.stdin.flush();record('actor_exit_before_pipeline',exit=actor.wait(timeout=5));actor=None
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
  import shutil
  shutil.copytree(work,Path('/mnt/output')/('fcitx-raw-'+label),dirs_exist_ok=True)
asyncio.run(main())
