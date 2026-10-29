from pathlib import Path
import os,sys,subprocess,json
p=Path('/home/inkecho/default-session26');a=Path('/home/inkecho/inkecho-release-0.10.0-r1/extracted-r1/squashfs-root');assert Path('/etc/machine-id').read_text().strip()=='80d223263a5e4ed1b8749d7f30116d5f'
env=os.environ.copy();env.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for line in subprocess.check_output(['systemctl','--user','show-environment'],env=env,text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:env[k]=v
for key in ['XDG_CACHE_HOME','XDG_STATE_HOME']:
 d=p/key.lower();d.mkdir(mode=0o700,exist_ok=True);env[key]=str(d)
env.pop('XDG_CONFIG_HOME',None)
env.update(APPDIR=str(a),PYTHONHOME=str(a/'usr'),PYTHONPATH=str(p/'source')+':'+str(a/'packages'),LD_LIBRARY_PATH=str(a/'usr/lib/inkecho'),QT_PLUGIN_PATH=str(a/'packages/PySide6/Qt/plugins'),QT_QPA_PLATFORM='offscreen',PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1')
child=subprocess.Popen([str(a/'usr/bin/python3'),str(p/'session_run.py')],env=env);print(json.dumps({'sender_pid':child.pid,'interpreter':str(a/'usr/bin/python3')}),flush=True);code=child.wait(timeout=120);print(json.dumps({'sender_exit':code}),flush=True);raise SystemExit(code)
