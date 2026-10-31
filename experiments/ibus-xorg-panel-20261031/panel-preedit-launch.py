import hashlib,json,os,shutil,subprocess
from pathlib import Path
app=Path(json.loads(Path('/mnt/output/mount.json').read_text())['appdir']);base=app/'packages';root=Path('/run/user/1000/auto-current-src');root.mkdir(mode=0o700);overlay=root/'packages';overlay.mkdir(mode=0o700)
for item in base.iterdir():
 if item.name=='inkecho':shutil.copytree('/mnt/input/current-src/src/inkecho',overlay/item.name,symlinks=True)
 else:(overlay/item.name).symlink_to(item)
src=Path('/mnt/input/current-src/src/inkecho');dst=overlay/'inkecho';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();files=sorted(str(p.relative_to(src)) for p in src.rglob('*') if p.is_file() and not p.is_symlink());other=sorted(str(p.relative_to(dst)) for p in dst.rglob('*') if p.is_file() and not p.is_symlink());assert files==other and all(sha(src/f)==sha(dst/f) for f in files)
env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000')
for line in subprocess.check_output(['systemctl','--user','show-environment'],env=env,text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','XAUTHORITY','XDG_SESSION_TYPE','XDG_CURRENT_DESKTOP'}:env[k]=v
env.update(APPDIR=str(app),PYTHONHOME=str(app/'usr'),PYTHONPATH=str(overlay)+':/mnt/input',PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',LD_LIBRARY_PATH=str(app/'usr/lib/inkecho'),QT_QPA_PLATFORM='offscreen');print(json.dumps({'artifact_sha':json.loads(Path('/mnt/output/mount.json').read_text())['artifact_sha256'],'source_files':len(files),'router_sha':sha(dst/'platform/ibus_owned_default.py'),'session':env.get('XDG_SESSION_TYPE'),'desktop':env.get('XDG_CURRENT_DESKTOP')}),flush=True)
try:raise SystemExit(subprocess.run([str(app/'usr/bin/python3'),'/mnt/input/panel-preedit.py'],env=env,timeout=180).returncode)
finally:shutil.rmtree(root)
