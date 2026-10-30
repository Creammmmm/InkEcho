"""Private same-package current-cursor cross-window fixture; no product overlay."""
from pathlib import Path
import asyncio, json, os, subprocess, sys, time, tempfile, hashlib, shutil
sys.path[:0]=['/mnt/input/crosslib','/mnt/input/frozen/scripts/validation','/mnt/input/frozen/scripts/feasibility']
from natural_owned_browser import NaturalOwnedBrowser
from native_guard import save,worker
from host_mixed_wayland_probe import x11_evidence
from x11_acceptance import owned_focus
from native_acceptance import until,keymap_metadata
if '--worker' in sys.argv:
 i=sys.argv.index('--worker');owner=int(sys.argv[i+1]);assert os.getppid()==owner
 import native_guard
 original_guard=native_guard.guard_allowed
 def diagnostic_guard(state,owner,now):
  allowed=original_guard(state,owner,now)
  if not allowed:
   save(Path(sys.argv[i+2]).with_name('guard-rejection.json'),{'state':state,'owner':owner,'now':now,'parent_pid':native_guard.parent_pid(state.get('pid',0)),'process_start':native_guard.process_start(state.get('pid',0))})
  return allowed
 native_guard.guard_allowed=diagnostic_guard
 asyncio.run(worker(Path(sys.argv[i+2]),Path(sys.argv[i+3]),owner));raise SystemExit
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.wayland_keyboard import keyboard_for_desktop
from inkecho.platform.wayland_worker import MutterSession
from inkecho.platform.keyboard import KeyboardError
from inkecho.platform.fcitx5_install import FcitxInstaller
from artifact_scope import audit_package,selected_artifact
A=Path(os.environ['APPDIR']);O=Path('/mnt/output')/os.environ['RUN_LABEL'];O.mkdir(mode=0o700,exist_ok=True);W=Path(tempfile.mkdtemp(prefix='inkecho-cross014-',dir='/tmp'));mode=os.environ.get('OUTPUT_METHOD','auto');start=os.environ.get('START_PLATFORM','wayland');cancel=os.environ.get('CANCEL','0')=='1';fcitx=os.environ.get('WITH_FCITX','0')=='1'
record={'artifact':selected_artifact(Path('/mnt/input/InkEcho.AppImage'),'a79ed5409e6d935ac1d4f4420f06e5ec6bc454fc20bdfe04c6db1e8ed6def055'),'audit':audit_package(A/'packages',Path('/mnt/input/frozen/src'),'0.14.0'),'mode':mode,'start_platform':start,'cancel':cancel,'private_fcitx':fcitx,'scope':'same output_session, explicit prefix-boundary pauses for natural owned-window opening/closing, not throughput or arbitrary applications','rows':[],'targets':[],'cleanup_errors':[]};fixtures=[];r=None;current=None;monitor=None;observer=None;daemon=None;install=None;hints=[];active=True;counts={'press':0,'release':0,'guard_rejections':0};guard=W/'guard.json';nativecounts=W/'counts.json'
def snapshot(f):
 f.assert_owned();d=f.snapshot();assert d is not None;return d
async def monitor_guard():
 while True:
  d=snapshot(current)if current else None;save(guard,{'allowed':bool(d and d['document_focused']and d['field_focused']and current.platform=='wayland'),'backend_confirmed':bool(current and current.platform=='wayland'),'owner_pid':os.getpid(),'pid':current.process.pid if current else 0,'start_ticks':current.started if current else '', 'sampled_at':d['sampled_at']if d else 0});await asyncio.sleep(.02)
async def open_target(platform):
 global current
 f=NaturalOwnedBrowser(W/('browser'+str(len(fixtures))),platform=platform);fixtures.append(f);f.start(reviewed=True);current=f
 await until(lambda:bool((s:=f.snapshot())and s['document_focused']and s['field_focused']and time.monotonic()-s['sampled_at']<.25),'owned_window_not_ready',seconds=12)
 if platform=='wayland':
  proof=f.native_evidence();assert all(v is True for k,v in proof.items()if k!='ozone_platform'),proof
 else:
  proof=x11_evidence(f);assert proof['confirmed'],proof;assert owned_focus(r.keyboard.x11._driver,f)
 assert snapshot(f)['text']=='';record['targets'].append({'platform':platform,'pid':f.process.pid,'argv':f.argv,'protocol':proof});await asyncio.sleep(.25);return f
async def run():
 global r,current,monitor,observer,daemon,install,hints,active
 hints=[x for x in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines()if x.split('=',1)[0]in {'GTK_IM_MODULE','QT_IM_MODULE','XMODIFIERS'}]
 try:
  from chrome_program import audit_program
  record['browser_audit']=audit_program()
  if fcitx:
   subprocess.run(['systemctl','--user','set-environment','GTK_IM_MODULE=fcitx','QT_IM_MODULE=fcitx','XMODIFIERS=@im=fcitx'],check=True)
   install=FcitxInstaller(source=A/'usr/share/inkecho/fcitx5/x86_64');install.install();de=dict(os.environ);de.update(GTK_IM_MODULE='fcitx',QT_IM_MODULE='fcitx',XMODIFIERS='@im=fcitx');daemon=subprocess.Popen(['/usr/bin/fcitx5','-D','--disable','clipboard'],env=de,stdout=(O/'fcitx.log').open('w'),stderr=subprocess.STDOUT);await asyncio.sleep(2);assert daemon.poll()is None;install.enable()
  r=DefaultAutoOutputRouter(keyboard_for_desktop());kb=r.keyboard
  async def spawn(*unused,**options):return await asyncio.create_subprocess_exec(sys.executable,'-B','/mnt/input/cross_runner.py','--worker',str(os.getpid()),str(guard),str(nativecounts),**options)
  kb.native._spawn=spawn
  # Read-only observation of actual Fcitx result; never substitutes a reply.
  factory=r._bridge_factory
  def observed_factory():
   b=factory();orig=b.insert
   async def observed(*a,**k):
    try:return await orig(*a,**k)
    except Exception as e:
     record.setdefault('fcitx_failures',[]).append({'code':getattr(e,'code',None),'accepted':getattr(e,'accepted',None),'uncertain':getattr(e,'uncertain',None),'unsent_offset':getattr(e,'unsent_offset',None)});raise
   b.insert=observed;return b
  r._bridge_factory=observed_factory
  await r.prepare_task(mode);record['prepared_before_targets']=True
  if not kb.x11.connected:await kb.x11.connect()
  driver=kb.x11._driver;mapping_before=repr(driver._mapping());send=kb.x11._send
  def checked_send(window,key,pressed):
   if pressed and (current is None or current.platform!='x11' or not owned_focus(driver,current,window)):
    counts['guard_rejections']+=1;raise KeyboardError('input_cancelled')
   v=send(window,key,pressed);counts['press'if pressed else'release']+=1;return v
  kb.x11._send=checked_send
  try:
   observer=MutterSession();await observer.connect();await observer.authorize();record['native_map_before']=await keymap_metadata(observer)
  except KeyboardError as e:record['native_observer_unavailable']=e.code
  first=await open_target(start);monitor=asyncio.create_task(monitor_guard());deadline=time.monotonic()+30
  async with r.output_session():
   for i,part in enumerate(['甲é','Ω\n','乙丙']):
    if i==1:await open_target('x11'if start=='wayland'else'wayland')
    if i==2:
     fixtures[-1].close();current=first;await until(lambda:bool((s:=first.snapshot())and s['document_focused']and s['field_focused']and time.monotonic()-s['sampled_at']<.25),'original_owned_focus_not_returned',seconds=12);await asyncio.sleep(.25)
    def on_first(_):
     global active
     if cancel and i==1:active=False
    row={'stage':i,'platform':current.platform,'requested_codepoints':[ord(x)for x in part]};record['rows'].append(row)
    try:row['returned_attempts']=await r.insert(part,lambda:active,deadline=deadline,on_first_sent=on_first);row['selected']=r.selected
    except BaseException as e:row['error']={'type':type(e).__name__,'code':getattr(e,'code',None),'attempts':getattr(e,'acknowledged_attempts',None)};record['stopped_at_stage']=i;raise
    await asyncio.sleep(.15);row['received_texts']=[snapshot(f)['text']for f in fixtures if f.process.poll()is None]
 except BaseException as e:record['error']={'type':type(e).__name__,'code':getattr(e,'code',None),'attempts':getattr(e,'acknowledged_attempts',None),'locations':[{'file':Path(x.filename).name,'line':x.lineno}for x in __import__('traceback').extract_tb(e.__traceback__)]}
 finally:
  if r:
   try:await r.aclose()
   except Exception as e:record['cleanup_errors'].append(type(e).__name__)
  before=[snapshot(f)['text']if f.process.poll()is None else (f.snapshot()or{}).get('text')for f in fixtures];await asyncio.sleep(1.3);after=[snapshot(f)['text']if f.process.poll()is None else(f.snapshot()or{}).get('text')for f in fixtures];record['received']=after;record['no_late']=before==after;record['x11_counts']=counts
  if r and r.keyboard.x11._driver is not None:record['x11_map_restored']=repr(r.keyboard.x11._driver._mapping())==mapping_before
  # aclose closes the driver; compare saved map with an independent readonly display.
  if r:
   from inkecho.platform.keyboard import _XDriver
   x=_XDriver();record['x11_map_restored']=repr(x._mapping())==mapping_before;x.close()
  if observer:
   try:
    if record.get('native_map_before'):record['native_map_after']=await keymap_metadata(observer);record['native_map_restored']=record['native_map_before']==record['native_map_after']
    await observer.close()
   except Exception as e:record['cleanup_errors'].append(type(e).__name__)
  if monitor:monitor.cancel();await asyncio.gather(monitor,return_exceptions=True)
  if nativecounts.exists():record['native_counts']=json.loads(nativecounts.read_text())
  if (W/'guard-rejection.json').exists():record['guard_rejection_detail']=json.loads((W/'guard-rejection.json').read_text())
  for f in reversed(fixtures):
   try:
    if f.process.poll()is None:f.close()
    record.setdefault('browser_exits',[]).append(f.process.poll())
   except Exception as e:record['cleanup_errors'].append(type(e).__name__)
  if install and daemon and daemon.poll()is None:install.disable();daemon.terminate();record['fcitx_exit']=daemon.wait(timeout=10)
  subprocess.run(['systemctl','--user','unset-environment','GTK_IM_MODULE','QT_IM_MODULE','XMODIFIERS'],check=True)
  if hints:subprocess.run(['systemctl','--user','set-environment',*hints],check=True)
  record['hints_restored']=[x for x in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines()if x.split('=',1)[0]in {'GTK_IM_MODULE','QT_IM_MODULE','XMODIFIERS'}]==hints
  record['whole_sequence_exact']=not cancel and len(after)==2 and after==['甲é乙丙','Ω\n'];record['module_origins']={k:str(Path(v.__file__).resolve())for k,v in sys.modules.items()if k.startswith('inkecho.')and getattr(v,'__file__',None)};assert all(Path(x).is_relative_to(A/'packages')for x in record['module_origins'].values());save(O/'result.json',record);print(json.dumps({k:record.get(k)for k in ['error','received','whole_sequence_exact','no_late','cleanup_errors']}))
asyncio.run(run())
