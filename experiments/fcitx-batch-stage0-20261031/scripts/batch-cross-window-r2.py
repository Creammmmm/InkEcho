from pathlib import Path
import asyncio,json,os,subprocess,sys,time,tempfile,urllib.request
p=Path.home()/'inkecho-paced26final-1031';sys.path[:0]=[str(p/'src'),str(p/'deps')]
os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
from inkecho.platform.fcitx5_install import FcitxInstaller
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
from websockets.sync.client import connect
w=p/'batch-cross-window-r2';w.mkdir(mode=0o700);data=w/'data';data.mkdir(mode=0o700);rows=[];daemon=browser=None
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
  profile=w/'profile';profile.mkdir(mode=0o700);env=dict(os.environ);env.pop('DISPLAY',None);env['WAYLAND_DEBUG']='client'
  args=['/opt/inkecho-qa-chrome/chrome','--password-store=basic','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--ozone-platform=wayland','--enable-wayland-ime','--wayland-text-input-version=3','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+str(profile),page.as_uri()]
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
  trace=(w/'browser.log').read_text(errors='replace');record('wayland_trace',surface='wl_compositor' in trace and 'create_surface' in trace,toplevel='xdg_toplevel' in trace,keyboard='wl_keyboard' in trace and '.enter(' in trace);assert 'wl_compositor' in trace and 'xdg_toplevel' in trace and 'wl_keyboard' in trace
  from inkecho.platform import fcitx5
  original_units=fcitx5.iter_text_units
  second=w/'second.html';second.write_text('<meta charset=utf-8><title>InkEcho second owned window</title><textarea id=b autofocus></textarea>')
  created=cdp('Target.createTarget',{'url':second.as_uri(),'newWindow':True});secondid=created['targetId'];target2=None
  for _ in range(100):
   target2=next((x for x in json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list')) if x.get('id')==secondid and x.get('url')==second.as_uri()),None)
   if target2:break
   await asyncio.sleep(.1)
  assert target2;ws2=connect(target2['webSocketDebuggerUrl'],open_timeout=3);seq2=0
  def cdp2(method,params):
   nonlocal seq2
   seq2+=1;ws2.send(json.dumps({'id':seq2,'method':method,'params':params}))
   while True:
    result= json.loads(ws2.recv(timeout=5))
    if result.get('id')==seq2:assert 'error' not in result;return result['result']
  def js2(expr):return cdp2('Runtime.evaluate',{'expression':expr,'returnByValue':True}).get('result',{}).get('value')
  switch_seq=0
  def hardware_switch():
   nonlocal switch_seq
   switch_seq+=1;share=Path('/mnt/inkecho-output');tmp=share/'switch-request.tmp';tmp.write_text(json.dumps({'sequence':switch_seq}));tmp.replace(share/'switch-request.json')
   until=time.monotonic()+5
   while time.monotonic()<until:
    ack=share/'switch-ack.json'
    if ack.exists():
     data=json.loads(ack.read_text())
     if data.get('sequence')==switch_seq:
      assert data['qmp_ok'];return
    time.sleep(.02)
   raise TimeoutError('switch acknowledgement')
  for batch in (1,2,4,8):
   sample='甲乙丙丁戊己庚辛壬癸'*20
   js2('b.value="";true');js('a.value="";window.switchMode=false;true')
   if not js('document.hasFocus()'): hardware_switch();await asyncio.sleep(.3)
   js('a.focus();true');await asyncio.sleep(.2)
   initial=json.loads(js("JSON.stringify({focus:document.hasFocus(),active:document.activeElement.id})"));assert initial=={'focus':True,'active':'a'}
   fcitx5.iter_text_units=lambda text,n=batch:(text[i:i+n] for i in range(0,len(text),n))
   r=DefaultAutoOutputRouter(HybridKeyboardInput());await r.prepare_task('auto');route=None;error=None;observed=[];start=time.monotonic()
   def first(_):
    nonlocal route
    route=r.selected
    # Deliberately hold this test callback while the owned A window receives
    # its first batch; then activate and verify the distinct owned B window.
    limit=time.monotonic()+3
    while time.monotonic()<limit:
     astate=json.loads(js("JSON.stringify({v:a.value,focus:document.hasFocus()})"))
     if astate['v']:break
     time.sleep(.01)
    assert astate['v'] and astate['focus']
    hardware_switch();js2('b.focus();true')
    while time.monotonic()<limit:
     bstate=json.loads(js2("JSON.stringify({focus:document.hasFocus(),active:document.activeElement.id})"))
     if bstate=={'focus':True,'active':'b'}:break
     time.sleep(.01)
    assert bstate=={'focus':True,'active':'b'};observed.append({'a':astate,'b':bstate,'time':time.monotonic()})
   try:
    async with r.output_session():sent=await r.insert(sample,lambda:True,deadline=start+60,on_first_sent=first);route=r.selected
   except Exception as e:sent=0;error={'kind':type(e).__name__,'code':getattr(e,'code',None)}
   finally:await r.aclose()
   await asyncio.sleep(.5);a=js('a.value');b=js2('b.value');exact=a+b==sample
   record('cross-window',batch=batch,sent=sent,route=route,error=error,exact=exact,a=a,b=b,observed=observed,elapsed=round(time.monotonic()-start,3))
   assert route=='fcitx' and exact and len(a)==batch and bool(b) and observed
  ws2.close()
  fcitx5.iter_text_units=original_units

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
