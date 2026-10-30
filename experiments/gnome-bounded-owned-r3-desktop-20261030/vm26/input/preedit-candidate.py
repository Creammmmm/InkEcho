from pathlib import Path
import os,json,subprocess,asyncio,time,signal,tempfile
from inkecho.platform.ibus_owned_auto import probe_owned
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.wayland_keyboard import keyboard_for_desktop
O=Path('/mnt/output/preedit-candidate');O.mkdir(mode=0o700);W=Path(tempfile.mkdtemp(prefix='inkecho-neighbor-preedit-',dir='/run/user/1000'));state=W/'actor.json';rows=[];p=None;r=None
async def main():
 global p,r
 env={k:v for k,v in os.environ.items()if k not in {'APPDIR','PYTHONPATH','PYTHONHOME','LD_LIBRARY_PATH','PYTHONNOUSERSITE'}};env.update(GDK_BACKEND='wayland');[env.pop(k,None)for k in ['GTK_IM_MODULE','QT_IM_MODULE','XMODIFIERS']]
 before=subprocess.check_output(['gsettings','get','org.gnome.desktop.input-sources','sources'],env=env,text=True).strip();engine=subprocess.check_output(['ibus','engine'],env=env,text=True).strip();report={'sources_before':before,'engine_before':engine,'rows':rows}
 try:
  subprocess.run(['gsettings','set','org.gnome.desktop.input-sources','sources',"[('ibus', 'libpinyin')]"],env=env,check=True)
  s=subprocess.run(['ibus','engine','libpinyin'],env=env,capture_output=True,text=True);report['select']={'returncode':s.returncode,'stdout':s.stdout,'stderr':s.stderr};await asyncio.sleep(2);report['engine_selected']=subprocess.check_output(['ibus','engine'],env=env,text=True).strip();assert report['engine_selected']=='libpinyin'
  p=subprocess.Popen(['/usr/bin/python3','/mnt/input/preedit-actor.py',str(state)],env=env,stdout=(O/'actor.log').open('w'),stderr=subprocess.STDOUT)
  for _ in range(100):
   if state.exists()and (d:=json.loads(state.read_text()))['active']and d['focus']:break
   assert p.poll()is None;await asyncio.sleep(.05)
  else:raise AssertionError('owned actor focus unavailable')
  for seq,key in enumerate([110,105],1):
   d=json.loads(state.read_text());assert d['pid']==p.pid and d['active']and d['focus'];req={'sequence':seq,'keyval':key,'actor':d,'state':str(state),'cmdline':'preedit-actor.py'};tmp=O/'key-request.tmp';tmp.write_text(json.dumps(req));tmp.replace(O/'key-request.json')
   for _ in range(200):
    ack=O/'key-ack.json'
    if ack.exists()and json.loads(ack.read_text()).get('sequence')==seq:assert json.loads(ack.read_text())['ok'];break
    await asyncio.sleep(.05)
   else:raise AssertionError('bounded hardware acknowledgement timed out')
   await asyncio.sleep(.3)
  before_state=json.loads(state.read_text());report['before_output']=before_state;assert bool(before_state['preedit'])and before_state['text']==''
  report['probe']=await probe_owned();assert report['probe']is not None,'owned GNOME scope unavailable';r=DefaultAutoOutputRouter(keyboard_for_desktop());await r.prepare_task('auto')
  try:
   async with r.output_session():await r.insert('甲\n',lambda:True,deadline=time.monotonic()+5)
  except Exception as err:report['output_error']={'kind':type(err).__name__,'code':getattr(err,'code',None)}
  else:raise AssertionError('preedit output unexpectedly accepted')
  await r.aclose();r=None;await asyncio.sleep(1.3);after=json.loads(state.read_text());report['after_output']=after;report['passed']=after['preedit']==before_state['preedit']and after['text']=='';assert report['passed']
 finally:
  if r:await r.aclose()
  if p and p.poll()is None:p.terminate();report['actor_exit']=p.wait(timeout=5)
  subprocess.run(['gsettings','set','org.gnome.desktop.input-sources','sources',before],env=env,check=True);subprocess.run(['ibus','engine',engine],env=env,capture_output=True);report['sources_after']=subprocess.check_output(['gsettings','get','org.gnome.desktop.input-sources','sources'],env=env,text=True).strip();assert report['sources_after']==before;(O/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
asyncio.run(main())
