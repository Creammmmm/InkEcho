from pathlib import Path
import asyncio,json,os,subprocess,sys,time,tempfile,urllib.request
p=Path.home()/'inkecho-paced24-1031';sys.path[:0]=[str(p/'src'),str(p/'deps')]
os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
from inkecho.platform.fcitx5_install import FcitxInstaller
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
from websockets.sync.client import connect
w=p/'xorg-preedit-r2';w.mkdir(mode=0o700);data=w/'data';data.mkdir(mode=0o700);rows=[];daemon=browser=None
os.environ.update(GTK_IM_MODULE='fcitx',QT_IM_MODULE='fcitx',XMODIFIERS='@im=fcitx')
def record(case,**kw):
 rows.append(dict(case=case,**kw));(w/'results.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows[-1]),flush=True)
async def main():
 global daemon,browser
 (p/'candidate').chmod(0o700);(p/'candidate/candidate').chmod(0o700)
 for item in (p/'candidate').rglob('*'):
  if item.is_file():item.chmod(0o600)
 hints=[x for x in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines() if x.split('=',1)[0] in {'XMODIFIERS','GTK_IM_MODULE','QT_IM_MODULE'}];install=FcitxInstaller(source=p/'candidate')
 try:
  subprocess.run(['systemctl','--user','set-environment','XMODIFIERS=@im=fcitx','GTK_IM_MODULE=fcitx','QT_IM_MODULE=fcitx'],check=True)
  install.enable();record('login_fcitx',debug=subprocess.check_output(['gdbus','call','--session','--dest','org.fcitx.Fcitx5','--object-path','/controller','--method','org.fcitx.Fcitx.Controller1.DebugInfo'],text=True))
  page=w/'owned.html';page.write_text('''<meta charset=utf-8><title>InkEcho own browser</title><textarea id=a autofocus></textarea><textarea id=b></textarea><script>window.events=[];for(const x of [a,b])for(const t of ['keydown','keyup','input','compositionstart','compositionupdate','compositionend','focus'])x.addEventListener(t,e=>events.push({type:t,id:x.id,data:e.data||''}));</script>''')
  profile=w/'profile';profile.mkdir(mode=0o700);env=dict(os.environ);assert os.environ.get('XDG_SESSION_TYPE')=='x11';assert env.get('DISPLAY')
  args=['/opt/inkecho-qa-chrome/chrome','--password-store=basic','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--ozone-platform=x11','--gtk-version=3','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+str(profile),page.as_uri()]
  browser=subprocess.Popen(args,env=env,stdout=subprocess.DEVNULL,stderr=(w/'browser.log').open('w'));record('browser_start',pid=browser.pid,wayland_display=env.get('WAYLAND_DISPLAY'),display_absent='DISPLAY' not in env,args=args)
  for _ in range(120):
   if (profile/'DevToolsActivePort').exists():break
   assert browser.poll() is None,'browser exited';await asyncio.sleep(.1)
  port=int((profile/'DevToolsActivePort').read_text().splitlines()[0]);target=None
  for _ in range(100):
   target=next((x for x in json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list')) if x.get('url')==page.as_uri()),None)
   if target:break
   await asyncio.sleep(.1)
  assert target;ws=connect(target['webSocketDebuggerUrl'],open_timeout=3);seq=0
  def cdp(method,params):
   nonlocal seq
   seq+=1;ws.send(json.dumps({'id':seq,'method':method,'params':params}))
   while True:
    r=json.loads(ws.recv(timeout=5))
    if r.get('id')==seq:assert 'error' not in r;return r['result']
  def js(expr):return cdp('Runtime.evaluate',{'expression':expr,'returnByValue':True}).get('result',{}).get('value')
  cdp('Page.bringToFront',{});js('a.focus();true');await asyncio.sleep(.6)
  state=json.loads(js("JSON.stringify({focus:document.hasFocus(),active:document.activeElement.id})"));record('ready',state=state);assert state=={'focus':True,'active':'a'}
  record('x11_evidence',session=os.environ.get('XDG_SESSION_TYPE'),display=env.get('DISPLAY'),browser_pid=browser.pid)
  subprocess.run(['/usr/bin/fcitx5-remote','-s','pinyin'],check=True);subprocess.run(['/usr/bin/fcitx5-remote','-o'],check=True);await asyncio.sleep(.5)
  async def key(value,sequence):
   own=json.loads(js("JSON.stringify({focus:document.hasFocus(),active:document.activeElement.id})"));assert own=={'focus':True,'active':'a'}
   share=Path('/mnt/inkecho-output');tmp=share/'key-request.tmp';tmp.write_text(json.dumps({'sequence':sequence,'keyval':value,'owned_pid':browser.pid,'owned_active':True,'owned_focus':True}));tmp.replace(share/'key-request.json')
   for _ in range(150):
    ack=share/'key-ack.json'
    if ack.exists() and json.loads(ack.read_text()).get('sequence')==sequence:assert json.loads(ack.read_text())['qmp_ok'];break
    await asyncio.sleep(.05)
   else:raise RuntimeError('QMP acknowledgement timeout')
   await asyncio.sleep(.5)
  subprocess.run(['/usr/bin/fcitx5-remote','-s','keyboard-us'],check=True);await key(97,1);control=json.loads(js("JSON.stringify({value:a.value,events:window.events})"));record('keyboard_control',state=control);assert control['value']=='a';js('a.value="";events.length=0;a.focus();true');subprocess.run(['/usr/bin/fcitx5-remote','-s','pinyin'],check=True);subprocess.run(['/usr/bin/fcitx5-remote','-o'],check=True);await asyncio.sleep(.5);await key(110,2);await key(105,3);await asyncio.sleep(.4)
  before=json.loads(js("JSON.stringify({value:a.value,events:window.events,focus:document.hasFocus(),active:document.activeElement.id})"));record('composition_before',state=before);assert before['value']=='ni' and any(e['type']=='compositionupdate' and e['data'] for e in before['events'])
  guard=DefaultAutoOutputRouter(HybridKeyboardInput());await guard.prepare_task('auto');caught=None
  try:
   async with guard.output_session():
    try:await guard.insert('戊',lambda:True,deadline=time.monotonic()+8)
    except Exception as e:caught={'code':getattr(e,'code',None),'attempts':getattr(e,'acknowledged_attempts',None)};raise
  except Exception as e:
   if caught is None:raise
  finally:await guard.aclose()
  after=json.loads(js("JSON.stringify({value:a.value,events:window.events,focus:document.hasFocus(),active:document.activeElement.id})"));record('composition_guard',error=caught,state=after);assert caught=={'code':'fcitx_composition_active','attempts':0} and after['value']==before['value'] and after['events']==before['events']
  await key(32,4);finished=json.loads(js("JSON.stringify({value:a.value,events:window.events})"));record('composition_finish',state=finished);assert finished['value']=='你'
  r=DefaultAutoOutputRouter(HybridKeyboardInput());await r.prepare_task('auto')
  try:
   async with r.output_session():
    try:sent=await r.insert('甲乙丙',lambda:True,deadline=time.monotonic()+8);route=r.selected;record('output',sent=sent,route=route)
    except Exception as e:record('output_error',kind=type(e).__name__,code=getattr(e,'code',None));raise
  finally:await r.aclose()
  await asyncio.sleep(.5);result=json.loads(js("JSON.stringify({value:a.value,events:window.events,focus:document.hasFocus(),active:document.activeElement.id})"));record('receiver',result=result);assert route=='fcitx' and sent==3 and result['value']=='你甲乙丙'
 finally:
  if browser:
   browser.terminate()
   try:record('browser_exit',exit=browser.wait(timeout=8))
   except subprocess.TimeoutExpired:browser.kill();record('browser_killed',exit=browser.wait(timeout=5))
  if daemon:daemon.terminate();record('daemon_exit',exit=daemon.wait(timeout=5))
  subprocess.run(['systemctl','--user','unset-environment','XMODIFIERS','GTK_IM_MODULE','QT_IM_MODULE'],check=True)
  for x in hints:subprocess.run(['systemctl','--user','set-environment',x],check=True)
  now=[x for x in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines() if x.split('=',1)[0] in {'XMODIFIERS','GTK_IM_MODULE','QT_IM_MODULE'}];record('hints_restored',value=sorted(now)==sorted(hints))
asyncio.run(main())
