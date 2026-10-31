import asyncio,json,os,subprocess,sys,time
from pathlib import Path
p=Path.home()/'inkecho-session-xorg24';sys.path[:0]=[str(p/'src'),str(p/'deps')]
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
async def main():
 env=dict(os.environ)
 for k in ('PYTHONHOME','PYTHONPATH','LD_LIBRARY_PATH','QT_QPA_PLATFORM','QT_PLUGIN_PATH','APPDIR'):env.pop(k,None)
 out=p/'qt6-preedit.json';out.unlink(missing_ok=True);proc=subprocess.Popen(['/usr/bin/python3',str(p/'qt6-preedit-target.py'),str(out)],env=env)
 try:
  await asyncio.sleep(2);wid=subprocess.check_output(['xdotool','search','--onlyvisible','--name','InkEchoQt6Preedit'],text=True).splitlines()[-1];subprocess.run(['xdotool','windowactivate','--sync',wid],check=True);subprocess.run(['fcitx5-remote','-s','pinyin'],check=True);subprocess.run(['fcitx5-remote','-o'],check=True);await asyncio.sleep(.5);subprocess.run(['xdotool','type','--delay','100','ni'],check=True);await asyncio.sleep(1)
  before=json.loads(out.read_text()) if out.exists() else None;print('before',json.dumps(before,ensure_ascii=False),flush=True)
  assert before and before['events'][-1]['preedit'], 'preedit positive control failed'
  r=DefaultAutoOutputRouter(HybridKeyboardInput());await r.prepare_task('auto');caught=None
  try:
   async with r.output_session():
    try:await r.insert('戊',lambda:True,deadline=time.monotonic()+8)
    except Exception as e:caught={'code':getattr(e,'code',None),'attempts':getattr(e,'acknowledged_attempts',None)};raise
  except Exception:
   if caught is None:raise
  finally:await r.aclose()
  after=json.loads(out.read_text());print('guard',caught,'after',json.dumps(after,ensure_ascii=False),flush=True);assert caught=={'code':'fcitx_composition_active','attempts':0} and before==after
  subprocess.run(['xdotool','key','space'],check=True);await asyncio.sleep(.5);finished=json.loads(out.read_text());print('finished',json.dumps(finished,ensure_ascii=False),flush=True);assert finished['text']=='你'
 finally:proc.terminate();proc.wait(timeout=5)
asyncio.run(main())
