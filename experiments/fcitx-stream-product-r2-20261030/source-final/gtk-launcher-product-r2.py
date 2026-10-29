from pathlib import Path
import os,json,subprocess,shutil
O=Path('/mnt/output/gtk-product-r2');O.mkdir(mode=0o700);A=Path(json.loads(Path('/mnt/output/browser-xorg/mount.json').read_text())['appdir']);env=dict(os.environ);env.update(DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000')
for l in subprocess.check_output(['systemctl','--user','show-environment'],env=env,text=True).splitlines():
 k,_,v=l.partition('=')
 if k in {'DISPLAY','XAUTHORITY','WAYLAND_DISPLAY','XDG_SESSION_TYPE','XDG_CURRENT_DESKTOP'}:env[k]=v
env.update(APPDIR=str(A),PYTHONHOME=str(A/'usr'),PYTHONPATH=str(A/'packages'),PYTHONNOUSERSITE='1',LD_LIBRARY_PATH=str(A/'usr/lib/inkecho'),PYTHONDONTWRITEBYTECODE='1',QT_QPA_PLATFORM='offscreen',INKECHO_OUTPUT_STAGE='product-r2')
with (O/'suite.log').open('w')as f:r=subprocess.run([str(A/'usr/bin/python3'),'/mnt/input/gtk-product-r2.py'],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=120)
(O/'exit.json').write_text(json.dumps({'returncode':r.returncode}));shutil.copytree('/run/user/1000/inkecho-package-gate-0.11.0/fcitx-product-r2',O/'raw');r.check_returncode()
