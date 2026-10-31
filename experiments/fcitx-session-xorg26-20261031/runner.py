import pathlib, subprocess, os, time, json, hashlib
p=pathlib.Path.home()/'inkecho-session-xorg26'; a=pathlib.Path.home()/'inkecho-release-0.10.0-r1/stage/InkEcho-0.10.0-x86_64.AppImage'
assert hashlib.sha256(a.read_bytes()).hexdigest()=='ca322f19c6306546698621f4d2301a6a6b03eeb06c6c6be6e9f3d1506f6a5234'
env=dict(os.environ); env.update(DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus', XDG_RUNTIME_DIR='/run/user/1000')
for line in subprocess.check_output(['systemctl','--user','show-environment'],env=env,text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','XAUTHORITY','WAYLAND_DISPLAY','XDG_SESSION_TYPE','XDG_CURRENT_DESKTOP'}:env[k]=v
assert env.get('XDG_SESSION_TYPE')=='x11' and 'XFCE' in env.get('XDG_CURRENT_DESKTOP','')
with (p/'mount.log').open('w') as mountlog:
 mount=subprocess.Popen([str(a),'--appimage-mount'],stdout=mountlog,stderr=subprocess.STDOUT)
 try:
  for _ in range(100):
   path=(p/'mount.log').read_text().strip()
   if path and pathlib.Path(path).is_dir():break
   assert mount.poll() is None;time.sleep(.1)
  app=pathlib.Path(path);assert (app/'usr/bin/python3').is_file()
  env.update(APPDIR=str(app),PYTHONHOME=str(app/'usr'),PYTHONPATH=str(app/'packages'),PYTHONNOUSERSITE='1',LD_LIBRARY_PATH=str(app/'usr/lib/inkecho'),PYTHONDONTWRITEBYTECODE='1',QT_QPA_PLATFORM='offscreen')
  with (p/'session-suite.log').open('w') as out: result=subprocess.run([str(app/'usr/bin/python3'),str(p/'session-browser.py')],env=env,stdout=out,stderr=subprocess.STDOUT,timeout=180)
  (p/'session-exit.json').write_text(json.dumps({'returncode':result.returncode,'session':env['XDG_SESSION_TYPE'],'desktop':env['XDG_CURRENT_DESKTOP'],'runtime_sha256':hashlib.sha256(a.read_bytes()).hexdigest()}));result.check_returncode()
 finally:
  mount.terminate();mount.wait(timeout=8)
