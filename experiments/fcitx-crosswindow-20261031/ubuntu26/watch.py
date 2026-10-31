import pathlib,time,subprocess,sys,json
r=pathlib.Path(__file__).resolve().parent/'output';last='';end=time.monotonic()+180
while time.monotonic()<end:
 p=r/'request'
 if p.exists():
  token=p.read_text()
  if token!=last:
   p=subprocess.run(['docker','exec','inkecho-crosswindow26','python3','/input/qmp-switch.py'],capture_output=True,text=True)
   if p.returncode:print(json.dumps({'token':token,'exit':p.returncode,'stderr':p.stderr}),flush=True);sys.exit(p.returncode)
   (r/'ack').write_text(token);last=token;print(json.dumps({'ack':token}),flush=True)
 time.sleep(.02)
raise SystemExit('watcher timeout')
