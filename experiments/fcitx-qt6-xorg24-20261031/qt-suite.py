import asyncio,json,os,subprocess,sys,time
from pathlib import Path
p=Path.home()/'inkecho-session-xorg24';sys.path[:0]=[str(p/'src'),str(p/'deps')]
os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',GTK_IM_MODULE='fcitx',QT_IM_MODULE='fcitx',XMODIFIERS='@im=fcitx')
for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
from session_product import probe
w=p/'qt-qa';w.mkdir(exist_ok=True);results=[];windows=[]
def log(**r):
 results.append(r);(w/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False),flush=True)
async def main():
 try:
  clean=dict(os.environ);processes=[]
  for key in ('PYTHONHOME','PYTHONPATH','LD_LIBRARY_PATH','QT_QPA_PLATFORM','QT_PLUGIN_PATH','APPDIR'):clean.pop(key,None)
  for n in [1,2]:
   cmd=['/usr/bin/python3',str(p/'qt-target.py'),f'InkEchoQtQA{n}',str(w/f'capture{n}')]
   processes.append(subprocess.Popen(cmd,env=clean))
  await asyncio.sleep(2)
  for n in [1,2]:
   ids=subprocess.check_output(['xdotool','search','--onlyvisible','--name',f'InkEchoQtQA{n}'],text=True).splitlines();windows.append(ids[-1])
  assert windows[0]!=windows[1]
  for mode,case in [('auto','stream'),('auto','cancel')]:
   for win in windows:
    subprocess.run(['xdotool','windowactivate','--sync',win],check=True);subprocess.run(['xdotool','key','ctrl+a','BackSpace'],check=True);await asyncio.sleep(.15)
   subprocess.run(['xdotool','windowactivate','--sync',windows[0]],check=True);await asyncio.sleep(.6)
   assert subprocess.check_output(['xdotool','getwindowfocus'],text=True).strip()==windows[0]
   async def switch():
    await asyncio.sleep(.55);subprocess.run(['xdotool','windowactivate','--sync',windows[1]],check=True)
    focused=subprocess.check_output(['xdotool','getwindowfocus'],text=True).strip();log(case=case,stage='switch',focus_ok=focused==windows[1]);assert focused==windows[1]
   task=asyncio.create_task(switch());sample='甲乙丙丁戊己庚辛壬癸'*20
   result=await probe(DefaultAutoOutputRouter(HybridKeyboardInput()),sample,w/(mode+'-'+case),case=case,output_method=mode);await task;await asyncio.sleep(1.3)
   texts=[(w/f'capture{n}').read_bytes().decode('utf8') for n in [1,2]];expected=sample if case=='stream' else sample[:1];actual=''.join(texts)
   log(case=case,stage='result',route=[d['route_after'] for d in result['dispatches']],protocol=[d['protocol'] for d in result['dispatches']],outcome=result['outcome'],input_failure=result['input_failure'],error_code=result['error_code'],lengths=list(map(len,texts)),actual=actual,exact=actual==expected)
   assert actual==expected and result['outcome']==('succeeded' if case=='stream' else 'cancelled')
   if case=='stream':assert all(texts)
 finally:
  for process in processes:
   process.terminate();process.wait(timeout=5)
asyncio.run(main())
