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
import asyncio,base64,hashlib,http.server,json,os,subprocess,sys,tempfile,threading,time,urllib.request
from websockets.sync.client import connect
from inkecho.platform.fcitx5_install import FcitxInstaller
from inkecho.platform.ibus_owned_default import DefaultAutoOutputRouter
from inkecho.platform.wayland_keyboard import keyboard_for_desktop
from session_product_r2 import probe
O=Path('/mnt/output/browser-product-r2');O.mkdir(mode=0o700,exist_ok=True);A=Path(os.environ['APPDIR']);W=Path(tempfile.mkdtemp(prefix='inkecho-browser-',dir='/run/user/1000'));events=[];lock=threading.Lock();rows=[]
SAMPLE='你好 InkEcho，café Ω\n第二行。'
PAGE='''<!doctype html><meta charset=utf-8><title>InkEcho owned Chrome acceptance</title><h1>InkEcho owned offline input</h1><textarea id=a rows=4 cols=60 autofocus></textarea><textarea id=b rows=4 cols=60></textarea><script>window.mode='normal';window.events=[];for(const t of document.querySelectorAll('textarea')){t.addEventListener('input',()=>{events.push({id:t.id,len:t.value.length,type:'input',time:performance.now()});if(mode==='switch'&&t.id==='a')document.getElementById('b').focus();fetch('/event',{method:'POST',body:JSON.stringify({id:t.id,a:a.value,b:b.value,focus:document.hasFocus(),active:document.activeElement.id})});});t.addEventListener('beforeinput',e=>events.push({id:t.id,type:'beforeinput',data:e.data,inputType:e.inputType,time:performance.now()}));for(const k of ['keydown','keyup'])t.addEventListener(k,e=>events.push({id:t.id,type:k,key:e.key,code:e.code,time:performance.now()}));t.addEventListener('focus',()=>events.push({id:t.id,type:'focus',time:performance.now()}));}</script>'''
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(PAGE.encode())
 def do_POST(self):
  v=json.loads(self.rfile.read(int(self.headers['Content-Length'])));v['observed_monotonic']=time.monotonic()
  with lock:events.append(v)
  self.send_response(204);self.end_headers()
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start();port=server.server_address[1]
ce=dict(os.environ)
for k in ['APPDIR','PYTHONHOME','PYTHONPATH','LD_LIBRARY_PATH','QT_PLUGIN_PATH','QT_QPA_PLATFORM','PYTHONNOUSERSITE']:ce.pop(k,None)
ce.update(XDG_CONFIG_HOME=str(W/'config'),XDG_DATA_HOME=str(W/'data'),XDG_CACHE_HOME=str(W/'cache'),GTK_IM_MODULE='fcitx',QT_IM_MODULE='fcitx',XMODIFIERS='@im=fcitx')
page=W/'owned.html';page.write_text(PAGE);target_url=page.as_uri();profile=W/'chrome-profile';profile.mkdir(mode=0o700);chrome=None;daemon=None;hints=[];install=None
async def run():
 global chrome,daemon,hints,install
 hints=[s for s in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines()if s.split('=',1)[0]in {'GTK_IM_MODULE','QT_IM_MODULE','XMODIFIERS'}]
 report={'artifact_sha256':hashlib.sha256(Path('/mnt/input/InkEcho.AppImage').read_bytes()).hexdigest(),'appdir':str(A),'test_scope':'full pinned candidate product source overlay on released AppImage runtime; actual Session/default Router/negotiated bridge, no consumer or bridge-class monkeypatch; local synthetic provider only','browser_profile_new':str(profile),'sandbox_disabled_in_isolated_vm':True,'system':subprocess.check_output(['lsb_release','-ds'],text=True).strip(),'session':os.environ.get('XDG_SESSION_TYPE'),'desktop':os.environ.get('XDG_CURRENT_DESKTOP'),'cases':rows,'failures':[]}
 try:
  assert report['artifact_sha256']=='51d20c74a31beb7f01008378a76876a491fd8a3cdc6b61bda440a79bf11c966f'
  subprocess.run(['systemctl','--user','set-environment','GTK_IM_MODULE=fcitx','QT_IM_MODULE=fcitx','XMODIFIERS=@im=fcitx'],check=True)
  ce['XDG_DATA_HOME']=str(W/'data');Path(ce['XDG_DATA_HOME']).mkdir(mode=0o700);os.environ.update({k:ce[k] for k in ['XDG_DATA_HOME','XDG_CONFIG_HOME','XDG_CACHE_HOME','GTK_IM_MODULE','QT_IM_MODULE','XMODIFIERS']})
  from inkecho.platform import fcitx5_staging
  fcitx5_staging.TESTED_CANDIDATE_SHA256='f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44'
  report['native_candidate_test_only_override']=fcitx5_staging.TESTED_CANDIDATE_SHA256
  install=FcitxInstaller(source=Path('/mnt/input/batch-candidate'),data_home=Path(ce['XDG_DATA_HOME']));install.install()
  daemon=subprocess.Popen(['/usr/bin/fcitx5','-D','--disable','clipboard'],env=ce,stdout=(O/'fcitx.log').open('w'),stderr=subprocess.STDOUT)
  await asyncio.sleep(2);assert daemon.poll()is None;install.enable()
  browser='/opt/inkecho-test-chrome/chrome';manifest=json.loads(Path('/mnt/input/chrome-software-manifest.json').read_text());assert all(hashlib.file_digest((Path(browser).parent/k).open('rb'),'sha256').hexdigest()==v for k,v in manifest['files'].items());report['browser_full_public_manifest_matches']=True;report['browser_version']=subprocess.check_output([browser,'--version'],env=ce,text=True).strip();report['browser_binary_sha256']=hashlib.file_digest(Path(browser).open('rb'),'sha256').hexdigest()
  chrome=subprocess.Popen([browser,'--no-sandbox','--password-store=basic','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--disable-features=OptimizationHints,MediaRouter','--ozone-platform=x11','--gtk-version=3','--remote-debugging-port=0','--remote-allow-origins=*','--user-data-dir='+str(profile),target_url],env=ce,stdout=(O/'chrome.log').open('w'),stderr=subprocess.STDOUT)
  for _ in range(100):
   if (profile/'DevToolsActivePort').exists():break
   assert chrome.poll()is None,'chrome exited';await asyncio.sleep(.1)
  dp=int((profile/'DevToolsActivePort').read_text().splitlines()[0]);target=None
  for _ in range(100):
   targets=json.load(urllib.request.urlopen(f'http://127.0.0.1:{dp}/json/list',timeout=2));target=next((t for t in targets if t.get('url')==target_url),None)
   if target:break
   await asyncio.sleep(.1)
  assert target;ws=connect(target['webSocketDebuggerUrl'],open_timeout=3,close_timeout=3);seq=0
  def cdp(method,params):
   nonlocal seq
   seq+=1;ws.send(json.dumps({'id':seq,'method':method,'params':params}))
   while True:
    r=json.loads(ws.recv(timeout=5))
    if r.get('id')==seq:
     assert 'error'not in r,r;return r['result']
  def js(expr):
   r=cdp('Runtime.evaluate',{'expression':expr,'returnByValue':True});assert 'exceptionDetails'not in r,r;return r.get('result',{}).get('value')
  ids=[]
  for _ in range(300):
   found=subprocess.run(['xdotool','search','--all','--onlyvisible','--name','InkEcho owned Chrome acceptance'],env=ce,text=True,capture_output=True);ids=found.stdout.split()
   if len(ids)==1 and js("document.readyState==='complete'&&!!document.getElementById('a')"):break
   await asyncio.sleep(.1)
  report['startup_document']=js("JSON.stringify({title:document.title,url:location.href,ready:document.readyState,body:document.body.innerText,focus:document.hasFocus()})")
  report['startup_visible_window_ids']=subprocess.run(['xdotool','search','--onlyvisible','--name','.*'],env=ce,text=True,capture_output=True).stdout
  assert len(ids)==1,ids
  xid=int(ids[0]);report['focus_proofs']=[]
  def proof(label):
   checked=subprocess.run(['/usr/bin/python3','/mnt/input/focus-cli.py',str(xid),str(chrome.pid),browser,str(profile)],env=ce,text=True,capture_output=True,timeout=8)
   row={'label':label,'returncode':checked.returncode,'stdout':checked.stdout,'stderr':checked.stderr,'dom':json.loads(js("JSON.stringify({focus:document.hasFocus(),active:document.activeElement.id,url:location.href,visible:document.visibilityState})"))}
   if checked.returncode==0:row['os']=json.loads(checked.stdout)
   report['focus_proofs'].append(row);(O/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));return row
  def good(row):return row['returncode']==0 and row['os']['active_matches']and row['os']['input_focus_owned']and row['dom']['focus']and row['dom']['url']==target_url
  def screenshot(label):
   r=subprocess.run(['/usr/bin/python3','/mnt/input/screenshot-owned.py',str(xid),str(O/(label+'.png'))],env=ce,text=True,capture_output=True,timeout=8)
   report.setdefault('owned_screenshots',[]).append({'label':label,'returncode':r.returncode,'stderr':r.stderr})
  initial=proof('before-activation');assert initial['returncode']==0,'owned browser identity unproven';screenshot('before-activation')
  cdp('Page.bringToFront',{})
  activated=subprocess.run(['xdotool','windowactivate','--sync',str(xid)],env=ce,text=True,capture_output=True,timeout=5);report['fixture_initial_activation']={'xid':xid,'only_before_cases':True,'returncode':activated.returncode,'stdout':activated.stdout,'stderr':activated.stderr}
  js("document.getElementById('a').focus();true")
  await asyncio.sleep(.3);ready=proof('after-activation-dom-focus');screenshot('after-activation')
  if not good(ready):
   subprocess.run(['/usr/bin/python3','/mnt/input/desktop-state.py'],env=ce,check=True,timeout=5)
   (O/'awaiting-fixture-interaction').write_text('No text sent; owned identity verified; awaiting bounded fixture-only real hardware input')
   for _ in range(900):
    if (O/'fixture-interaction-done').exists():break
    await asyncio.sleep(.1)
   ready=proof('after-fixture-hardware-input');screenshot('after-fixture-hardware-input')
  assert good(ready)and ready['dom']['active']=='a','independent OS and DOM focus not established'
  for method in ['auto']:
   for case in ['leading-lf','trailing-lf','pure-three-tail','synchronous','original-fallback','mixed','cancel','pending-cancel','prepare-switch','switch','keyboard-first']:
    sample={'solo-lf':'\n','leading-lf':'\n甲','trailing-lf':'甲\n','two-lf':'\n\n','consecutive-tail':'甲\n\n','pure-three-tail':'甲\n\n\n','synchronous':'甲乙\n\n\n丙\n','original-fallback':'甲乙\n\n\n丙\n','keyboard-first':'甲乙\n','pending-cancel':'甲\n乙'}.get(case,SAMPLE)
    js("window.mode="+json.dumps('switch'if case=='switch'else'normal')+";a.value='';b.value='';events.length=0;a.focus();true")
    await asyncio.sleep(.2);ready=proof(method+'-'+case+'-before-prepare');assert good(ready)and ready['dom']['active']=='a'
    r=DefaultAutoOutputRouter(keyboard_for_desktop());active=True;row={'method':method,'case':case,'sample':sample,'initial_focus':'a'};rows.append(row)
    try:
     def before_produce():
      if case=='prepare-switch':js("b.focus();true")
     result=await probe(r,sample,W/('session-'+case),case=case,before_produce=before_produce,output_method='keyboard'if case=='keyboard-first'else'auto')
     row['session']=result;row['sent']=result['reported_characters'];row['route']=result['route'];row['cancel_requested']=case in {'cancel','pending-cancel'}
     if result['input_failure']:row['error']={'code':result['input_failure']}
    except Exception as e:
     row['error']={'type':type(e).__name__,**{k:getattr(e,k,None)for k in ['code','accepted','acknowledged_attempts','unsent_offset','uncertain']}};row['route']=r.selected
    finally:await r.aclose()
    await asyncio.sleep(.3)
    expr="JSON.stringify({a:a.value,b:b.value,active:document.activeElement.id,focus:document.hasFocus(),events:events})"
    row['first_dom']=json.loads(js(expr));await asyncio.sleep(1.3);row['last_dom']=json.loads(js(expr));d=row['last_dom'];combined=d['a']+d['b'];row['no_late']=row['first_dom']==d
    if case in {'solo-lf','two-lf'}:ok=combined=='' and row.get('sent',0)==0
    elif case=='pending-cancel':ok=combined==''
    elif case in {'leading-lf','trailing-lf','consecutive-tail','pure-three-tail','synchronous','original-fallback','mixed','keyboard-first'}:ok=d['a']==sample and d['b']==''
    elif case=='cancel':ok=bool(combined)and sample.startswith(combined)and len(combined)<len(sample)and row.get('cancel_requested',False)
    elif case=='prepare-switch':ok=d['a']==''and d['b']==sample
    else:ok=bool(d['a'])and bool(d['b'])and combined==sample and d['active']=='b'
    row['passed']=ok and row['no_late']and ('error'not in row if case not in {'cancel','pending-cancel'}else row.get('error',{}).get('code') in {None,'input_cancelled','cancelled','fcitx_cancelled'})
    row['received_lengths']=[len(d['a']),len(d['b'])];(O/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({'method':method,'case':case,'passed':row['passed'],'route':row['route'],'received_lengths':row['received_lengths'],'error':row.get('error')},ensure_ascii=False),flush=True)
    screen=cdp('Page.captureScreenshot',{'format':'png'});(O/(method+'-'+case+'.png')).write_bytes(base64.b64decode(screen['data']))
  ws.close();report['passed']=all(r['passed']for r in rows)
 except Exception as e:
  report['failures'].append({'type':type(e).__name__,'message':str(e)});report['passed']=False;raise
 finally:
  if install and daemon and daemon.poll() is None:
   try:install.disable();report['addon_disabled_before_daemon_stop']=True
   except Exception as e:report['cleanup_install_error']=type(e).__name__
  for p,name in [(chrome,'browser'),(daemon,'fcitx')]:
   if p is not None:
    if p.poll()is None:p.terminate()
    report[name+'_exit']=p.wait(timeout=10)
  subprocess.run(['systemctl','--user','unset-environment','GTK_IM_MODULE','QT_IM_MODULE','XMODIFIERS'],check=True)
  if hints:subprocess.run(['systemctl','--user','set-environment',*hints],check=True)
  report['hints_restored']=[s for s in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines()if s.split('=',1)[0]in {'GTK_IM_MODULE','QT_IM_MODULE','XMODIFIERS'}]==hints
  report['package_module_origins']={k:str(Path(v.__file__).resolve())for k,v in list(sys.modules.items())if k.startswith('inkecho.')and getattr(v,'__file__',None)}
  assert all(Path(v).is_relative_to(_SR)for v in report['package_module_origins'].values())
  (O/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));server.shutdown()
asyncio.run(run())
