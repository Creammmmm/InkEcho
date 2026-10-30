from pathlib import Path
import os,json,subprocess
LABEL=os.environ.get('RUN_LABEL','disabled-fcitx');FIELD=os.environ.get('OWNED_FIELD','textarea');O=Path('/mnt/output/browser24-native012-'+LABEL+'-'+FIELD);O.mkdir(mode=0o700);(O/'mount.json').write_bytes((Path('/mnt/output')/os.environ['INKECHO_OUTPUT_STAGE']/'mount.json').read_bytes());A=Path(json.loads((O/'mount.json').read_text())['appdir']);env=dict(os.environ);env.update(DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000')
for l in subprocess.check_output(['systemctl','--user','show-environment'],env=env,text=True).splitlines():
 k,_,v=l.partition('=')
 if k in {'DISPLAY','XAUTHORITY','WAYLAND_DISPLAY','XDG_SESSION_TYPE','XDG_CURRENT_DESKTOP'}:env[k]=v
env.update(APPDIR=str(A),PYTHONHOME=str(A/'usr'),PYTHONPATH='/mnt/input/candidate-src:'+str(A/'packages'),PYTHONNOUSERSITE='1',LD_LIBRARY_PATH=str(A/'usr/lib/inkecho'),PYTHONDONTWRITEBYTECODE='1',QT_QPA_PLATFORM='offscreen')
with (O/'suite.log').open('w')as f:r=subprocess.run([str(A/'usr/bin/python3'),'/mnt/input/browser-native012.py'],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=150)
(O/'suite-exit.json').write_text(json.dumps({'returncode':r.returncode}));print((O/'suite.log').read_text());r.check_returncode()
