import os,subprocess,time,pathlib,json
p=pathlib.Path.home()/'inkecho-session-xorg24';a=pathlib.Path.home()/'inkecho-candidate-0.10.0-input-r1/InkEcho-0.10.0-x86_64.AppImage';env=dict(os.environ);env.update(DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000')
for line in subprocess.check_output(['systemctl','--user','show-environment'],env=env,text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','XAUTHORITY','WAYLAND_DISPLAY','XDG_SESSION_TYPE','XDG_CURRENT_DESKTOP'}:env[k]=v
assert env.get('XDG_SESSION_TYPE')=='x11'
with (p/'mount-terminal.log').open('w') as out:
 mount=subprocess.Popen([str(a),'--appimage-mount'],stdout=out,stderr=subprocess.STDOUT)
 try:
  for _ in range(100):
   path=(p/'mount-terminal.log').read_text().strip()
   if path and pathlib.Path(path).is_dir():break
   assert mount.poll() is None;time.sleep(.1)
  app=pathlib.Path(path);env.update(APPDIR=str(app),PYTHONHOME=str(app/'usr'),PYTHONPATH=str(app/'packages'),PYTHONNOUSERSITE='1',LD_LIBRARY_PATH=str(app/'usr/lib/inkecho'),PYTHONDONTWRITEBYTECODE='1',QT_QPA_PLATFORM='offscreen')
  def run(script):return subprocess.run([str(app/'usr/bin/python3'),str(p/script)],env=env,check=True)
  env.update(XMODIFIERS='@im=fcitx',GTK_IM_MODULE='fcitx',QT_IM_MODULE='fcitx');subprocess.run(['pkill','-f','^/usr/libexec/gnome-terminal-server'],check=False);run('setup-login.py');subprocess.run(['systemctl','--user','set-environment','XMODIFIERS=@im=fcitx','GTK_IM_MODULE=fcitx','QT_IM_MODULE=fcitx'],env=env,check=True)
  subprocess.run(['fcitx5','-d','--disable','clipboard'],env=env,check=True);time.sleep(3)
  try:run('qt-suite.py')
  finally:run('cleanup-login.py')
 finally:
  mount.terminate();mount.wait(timeout=8)
