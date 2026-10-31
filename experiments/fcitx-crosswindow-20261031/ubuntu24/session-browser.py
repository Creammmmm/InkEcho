from pathlib import Path
import asyncio,json,os,subprocess,sys,time,tempfile,urllib.request
p=Path.home()/'inkecho-session-xorg24';sys.path[:0]=[str(p/'src'),str(p/'deps')]
os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
from inkecho.platform.fcitx5_install import FcitxInstaller
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
from websockets.sync.client import connect
from session_product import probe
w=p/'session-crosswindow-r4';w.mkdir(mode=0o700);data=w/'data';data.mkdir(mode=0o700);rows=[];daemon=browser=None
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
  page=w/'owned.html';page.write_text('''<meta charset=utf-8><title>InkEcho own browser</title><textarea id=a autofocus></textarea><textarea id=b></textarea><script>window.events=[];for(const x of [a,b])for(const t of ['input','compositionstart','compositionupdate','compositionend','focus'])x.addEventListener(t,e=>events.push({type:t,id:x.id,data:e.data||''}));window.switchMode=false;a.addEventListener('input',()=>{if(window.switchMode)b.focus()});</script>''')
  profile=w/'profile';profile.mkdir(mode=0o700);env=dict(os.environ);assert env.get('DISPLAY') and env.get('XDG_SESSION_TYPE') == 'x11'
  args=['/opt/inkecho-qa-chrome/chrome','--no-sandbox','--password-store=basic','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--ozone-platform=x11','--gtk-version=3','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+str(profile),page.as_uri()]
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
  created=cdp('Target.createTarget',{'url':page.as_uri()+'?second','newWindow':True})['targetId']
  for _ in range(100):
   target2=next((x for x in json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list')) if x.get('id')==created),None)
   if target2:break
   await asyncio.sleep(.1)
  assert target2;ws2=connect(target2['webSocketDebuggerUrl'],open_timeout=3);seq2=0
  def cdp2(method,params):
   nonlocal seq2
   seq2+=1;ws2.send(json.dumps({'id':seq2,'method':method,'params':params}))
   while True:
    reply=json.loads(ws2.recv(timeout=5))
    if reply.get('id')==seq2:assert 'error' not in reply;return reply['result']
  def js2(expr):return cdp2('Runtime.evaluate',{'expression':expr,'returnByValue':True}).get('result',{}).get('value')
  js('document.title="InkEchoFirstUnique";true');js2('document.title="InkEchoSecondUnique";true');await asyncio.sleep(.4)
  win1=subprocess.check_output(['xdotool','search','--onlyvisible','--name','InkEchoFirstUnique'],text=True).splitlines()[-1];win2=subprocess.check_output(['xdotool','search','--onlyvisible','--name','InkEchoSecondUnique'],text=True).splitlines()[-1];assert win1!=win2;record('native_windows',first=win1,second=win2)
  record('distinct_browser_windows',first_target=target['id'],second_target=created);assert target['id']!=created
  for mode,case in [('auto','stream'),('fcitx','stream'),('auto','cancel'),('fcitx','cancel')]:
   sample=('甲乙丙丁戊己庚辛壬癸'*20)
   subprocess.run(['xdotool','windowactivate','--sync',win2],check=True);js2('a.value="";events.length=0;a.focus();true');await asyncio.sleep(.3)
   subprocess.run(['xdotool','windowactivate','--sync',win1],check=True);js('a.value="";events.length=0;a.focus();true');await asyncio.sleep(.5)
   initial=[json.loads(js('JSON.stringify({focus:document.hasFocus(),active:document.activeElement.id})')),json.loads(js2('JSON.stringify({focus:document.hasFocus(),active:document.activeElement.id})'))];record('before',mode=mode,scenario=case,windows=initial,fcitx_debug=subprocess.check_output(['gdbus','call','--session','--dest','org.fcitx.Fcitx5','--object-path','/controller','--method','org.fcitx.Fcitx.Controller1.DebugInfo'],text=True));assert initial[0]['focus'] and not initial[1]['focus']
   async def switch():
    await asyncio.sleep(.55)
    before=js('a.value');subprocess.run(['xdotool','windowactivate','--sync',win2],check=True);js2('a.focus();true');await asyncio.sleep(.15)
    active=[json.loads(js('JSON.stringify({focus:document.hasFocus(),active:document.activeElement.id})')),json.loads(js2('JSON.stringify({focus:document.hasFocus(),active:document.activeElement.id})'))]
    record('switch',mode=mode,scenario=case,first_before_switch=before,windows=active);assert not active[0]['focus'] and active[1]['focus']
   switcher=asyncio.create_task(switch());r=DefaultAutoOutputRouter(HybridKeyboardInput());start=time.monotonic()
   result=await probe(r,sample,w/(mode+'-'+case),case=case,output_method=mode);await switcher;await asyncio.sleep(1.3)
   state=[json.loads(js('JSON.stringify({value:a.value,events:events,focus:document.hasFocus()})')),json.loads(js2('JSON.stringify({value:a.value,events:events,focus:document.hasFocus()})'))];actual=state[0]['value']+state[1]['value'];expected=sample if case!='cancel' else sample[:1]
   record('session_crosswindow',mode=mode,scenario=case,elapsed=round(time.monotonic()-start,3),result=result,exact=actual==expected,expected=expected,receivers=state)
   assert actual==expected and result['outcome']==('cancelled' if case=='cancel' else 'succeeded')
   if case=='stream':assert state[0]['value'] and state[1]['value']

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
