import http.server,json,os,subprocess,sys,tempfile,threading,time
mode=sys.argv[1]; events=[]
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def do_GET(self):
  self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers(); self.wfile.write(b'''<html><title>InkEcho isolated chrome</title><textarea autofocus id="t"></textarea><script>let t=document.getElementById('t');function emit(k){fetch('/event',{method:'POST',body:JSON.stringify({kind:k,value:t.value,focused:document.hasFocus()&&document.activeElement===t})})} t.oninput=()=>emit('input'); window.onfocus=()=>{t.focus();emit('focus')};setTimeout(()=>{t.focus();emit('focus')},1000);</script></html>''')
 def do_POST(self):
  e=json.loads(self.rfile.read(int(self.headers['Content-Length']))); events.append(e); self.send_response(204); self.end_headers()
s=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler); threading.Thread(target=s.serve_forever,daemon=True).start()
p=tempfile.mkdtemp(prefix='inkecho-xw-chrome-'); c=subprocess.Popen(['/tmp/inkecho-browser/chrome/chrome','--no-sandbox','--disable-background-networking','--disable-sync','--disable-popup-blocking','--no-first-run','--no-default-browser-check','--ozone-platform=x11','--user-data-dir='+p,'http://127.0.0.1:%d/'%s.server_address[1]],stdout=subprocess.DEVNULL,stderr=open('/tmp/xw-chrome-error-'+mode+'.log','w'))
try:
 for i in range(200):
  if i in (30, 70, 120): subprocess.run(['gdbus','call','--session','--dest','io.github.Creammmmm.InkEcho.WaylandFocusProbe','--object-path','/io/github/Creammmmm/InkEcho/WaylandFocusProbe','--method','io.github.Creammmmm.InkEcho.WaylandFocusProbe1.Activate','InkEcho isolated chrome'],capture_output=True)
  if any(e['kind']=='focus' and e['focused'] for e in events): break
  if c.poll() is not None: break
  time.sleep(.05)
 else: pass
 if not any(e['kind']=='focus' and e['focused'] for e in events): print(json.dumps({'mode':mode,'error':'initial_focus_missing','chrome_exit':c.poll(),'events':events}),flush=True); sys.exit(1)
 root='/tmp/xwtest/squashfs-root'; env=os.environ.copy(); env.update(PYTHONHOME=root+'/usr',PYTHONPATH=root+'/packages',LD_LIBRARY_PATH=root+'/usr/lib/inkecho')
 r=subprocess.run([root+'/usr/bin/python3','/tmp/xwtest/sender.py',mode],env=env,capture_output=True,text=True,timeout=30)
 time.sleep(1); print(json.dumps({'mode':mode,'stdout':r.stdout,'stderr':r.stderr[-1500:],'exit':r.returncode,'events':events},ensure_ascii=False),flush=True)
finally:
 c.terminate(); c.wait(timeout=5); s.shutdown()
