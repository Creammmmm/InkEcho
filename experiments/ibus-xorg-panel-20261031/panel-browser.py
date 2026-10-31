import asyncio,json,os,subprocess,tempfile,time,shutil,traceback,urllib.request
from pathlib import Path
from websockets.sync.client import connect
from session_product_r2 import probe,_APP
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.wayland_keyboard import keyboard_for_desktop
from inkecho.runtime import ManagedQtEventLoop
O=Path('/mnt/output/panel-browser.json');W=Path(tempfile.mkdtemp(prefix='inkecho-browser-xorg-',dir='/run/user/1000'));R={'complete':False,'cases':[]};browser=None;ws=None;actors=[];env={k:v for k,v in os.environ.items() if k not in {'APPDIR','PYTHONPATH','PYTHONHOME','LD_LIBRARY_PATH','PYTHONNOUSERSITE','QT_PLUGIN_PATH'}};env.pop('WAYLAND_DISPLAY',None)
page=W/'input.html';page.write_text('''<!doctype html><title>InkEcho Xorg Browser</title><textarea id="a" autofocus></textarea><textarea id="b"></textarea><script>window.switchAfterFirst=false;window.log=[];for(const e of [a,b])e.addEventListener('input',()=>{log.push({id:e.id,a:a.value,b:b.value,t:performance.now()});if(window.switchAfterFirst&&e===a){switchAfterFirst=false;b.focus()}});</script>''');url=page.as_uri()
async def main():
 global browser,ws
 profile=W/'profile';profile.mkdir();binary='/opt/inkecho-test-chrome/chrome';R['browser_version']=subprocess.check_output([binary,'--version'],env=env,text=True).strip()
 argv=[binary,'--password-store=basic','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--ozone-platform=x11','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+str(profile),url]
 browser=subprocess.Popen(argv,env=env,stdout=subprocess.DEVNULL,stderr=(O.parent/'chrome-xorg.log').open('w'))
 for _ in range(200):
  if (profile/'DevToolsActivePort').exists():break
  if browser.poll() is not None:raise RuntimeError('chrome exited '+str(browser.returncode))
  await asyncio.sleep(.05)
 else:raise RuntimeError('debug port unavailable')
 port=int((profile/'DevToolsActivePort').read_text().splitlines()[0]);target=None
 for _ in range(100):
  targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list',timeout=2));target=next((x for x in targets if x.get('url')==url),None)
  if target:break
  await asyncio.sleep(.05)
 assert target;ws=connect(target['webSocketDebuggerUrl'],open_timeout=3,close_timeout=3);seq=0
 def cdp(method,params):
  nonlocal seq
  seq+=1;ws.send(json.dumps({'id':seq,'method':method,'params':params}))
  while True:
   x=json.loads(ws.recv(timeout=5))
   if x.get('id')==seq:
    assert 'error' not in x,x;return x['result']
 def js(expression):
  x=cdp('Runtime.evaluate',{'expression':expression,'returnByValue':True});assert 'exceptionDetails' not in x,x;return x.get('result',{}).get('value')
 for case in ('normal','caret-switch','window-switch','cancel'):
  row={'case':case};R['cases'].append(row);actor=None;actor_state=None;actor_window=None
  if case=='window-switch':
   actor_state=W/'window-switch-actor.json';actor_env=dict(env,GDK_BACKEND='x11');actor=subprocess.Popen(['/usr/bin/python3','/mnt/input/preedit-actor.py',str(actor_state)],env=actor_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);actors.append(actor)
   for _ in range(100):
    found=subprocess.run(['xdotool','search','--name','InkEcho owned batch preedit acceptance'],env=env,capture_output=True,text=True)
    if actor_state.exists() and found.returncode==0 and found.stdout.strip():break
    await asyncio.sleep(.05)
   else:raise RuntimeError('second window unavailable')
   actor_window=found.stdout.strip().splitlines()[-1];row['second_before']=json.loads(actor_state.read_text())
  cdp('Page.bringToFront',{});js("a.value='';b.value='';log=[];switchAfterFirst="+('true' if case=='caret-switch' else 'false')+";a.focus();true");await asyncio.sleep(.3)
  row['focus_before']=json.loads(js("JSON.stringify({document:document.hasFocus(),active:document.activeElement.id})"));assert row['focus_before']=={'document':True,'active':'a'}
  keyboard=keyboard_for_desktop();orig=keyboard.connect
  async def wrapped():
   await orig();row['driver']=type(keyboard._driver).__name__
   if case=='window-switch':
    original_send=keyboard._driver.send;switched=False
    def send(window,code,pressed):
     nonlocal switched
     original_send(window,code,pressed)
     if not pressed and not switched:
      switched=True;row['switch_at']=time.monotonic();subprocess.run(['xdotool','windowactivate','--sync',actor_window],env=env,check=True)
      row['active_window_after_switch']=subprocess.check_output(['xdotool','getwindowfocus','getwindowname'],env=env,text=True).strip()
    keyboard._driver.send=send
  keyboard.connect=wrapped;router=DefaultAutoOutputRouter(keyboard)
  try:row['session']=await probe(router,'甲乙丙丁abc123',W/('cfg-'+case),case='cancel' if case=='cancel' else 'synchronous',output_method='ibus')
  except BaseException as e:row['exception']={'type':type(e).__name__,'message':str(e)}
  await asyncio.sleep(1.3);row['observed']=json.loads(js("JSON.stringify({a:a.value,b:b.value,active:document.activeElement.id,focus:document.hasFocus(),log:log})"))
  if actor:
   row['second_after']=json.loads(actor_state.read_text());actor.terminate();actor.wait(timeout=5);row['second_exit']=actor.returncode
 R['complete']=True
try:
 with ManagedQtEventLoop(_APP) as loop:loop.run_until_complete(main())
except BaseException as e:R['error']={'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()}
finally:
 for actor in actors:
  if actor.poll() is None:actor.terminate();actor.wait(timeout=5)
 if ws:ws.close()
 if browser:
  browser.terminate()
  try:browser.wait(timeout=8)
  except subprocess.TimeoutExpired:browser.kill();browser.wait()
  R['browser_exit']=browser.returncode
 O.write_text(json.dumps(R,ensure_ascii=False,indent=2));shutil.rmtree(W)
 print(json.dumps({'complete':R['complete'],'cases':[{'case':x['case'],'driver':x.get('driver'),'session':x.get('session',{}).get('outcome'),'observed':x.get('observed'),'exception':x.get('exception')} for x in R['cases']],'error':R.get('error')},ensure_ascii=False),flush=True)
