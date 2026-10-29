from pathlib import Path
import subprocess,os,json,time,signal,shutil,hashlib
O=Path('/mnt/output/gtk-begin4-26-r3');O.mkdir(mode=0o700);A=Path('/home/inkecho/inkecho-release-0.10.0-r1/stage/InkEcho-0.10.0-x86_64.AppImage');assert hashlib.sha256(A.read_bytes()).hexdigest()=='ca322f19c6306546698621f4d2301a6a6b03eeb06c6c6be6e9f3d1506f6a5234'
env=dict(os.environ);env.update(DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000')
for l in subprocess.check_output(['systemctl','--user','show-environment'],env=env,text=True).splitlines():
 k,_,v=l.partition('=')
 if k in {'DISPLAY','XAUTHORITY','WAYLAND_DISPLAY','XDG_SESSION_TYPE','XDG_CURRENT_DESKTOP'}:env[k]=v
assert env['XDG_SESSION_TYPE']=='wayland' and 'GNOME'in env['XDG_CURRENT_DESKTOP']
p=subprocess.Popen([str(A),'--appimage-mount'],stdout=(O/'mount.log').open('w'),stderr=(O/'mount.err').open('w'))
try:
 for _ in range(100):
  s=(O/'mount.log').read_text().strip()
  if s and Path(s).is_dir():break
  assert p.poll()is None;time.sleep(.1)
 app=Path(s);assert(app/'usr/bin/python3').is_file()
 (O/'runtime.json').write_text(json.dumps({'interpreter_appimage_sha256':'ca322f19c6306546698621f4d2301a6a6b03eeb06c6c6be6e9f3d1506f6a5234','candidate_source_overlay':True,'session':env['XDG_SESSION_TYPE'],'desktop':env['XDG_CURRENT_DESKTOP'],'addon_sha256':'f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44'},indent=2))
 env.update(APPDIR=str(app),PYTHONHOME=str(app/'usr'),PYTHONPATH=str(app/'packages'),PYTHONNOUSERSITE='1',LD_LIBRARY_PATH=str(app/'usr/lib/inkecho'),PYTHONDONTWRITEBYTECODE='1',QT_QPA_PLATFORM='offscreen',INKECHO_OUTPUT_STAGE='begin4-26-r3')
 Path('/run/user/1000/inkecho-package-gate-0.11.0').mkdir(mode=0o700,exist_ok=True)
 with(O/'suite.log').open('w')as f:r=subprocess.run([str(app/'usr/bin/python3'),'/mnt/input/gtk-begin4-26.py'],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=120)
 (O/'exit.json').write_text(json.dumps({'returncode':r.returncode}));shutil.copytree('/run/user/1000/inkecho-package-gate-0.11.0/fcitx-begin4-26-r3',O/'raw');r.check_returncode()
finally:
 p.terminate();rc=p.wait(timeout=8);(O/'mount-exit.json').write_text(json.dumps({'returncode':rc}))
