from pathlib import Path
import os,json,subprocess,shutil,tempfile
out=Path('/mnt/output')/os.environ['INKECHO_OUTPUT_STAGE'];out.mkdir(mode=0o700,exist_ok=True)
env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000')
for line in subprocess.check_output(['systemctl','--user','show-environment'],env=env,text=True).splitlines():
 key,_,value=line.partition('=')
 if key in {'DISPLAY','XAUTHORITY','WAYLAND_DISPLAY','XDG_SESSION_TYPE','XDG_CURRENT_DESKTOP'}:env[key]=value
work=Path(tempfile.mkdtemp(prefix='inkecho-gui014-',dir='/tmp'));env['TMPDIR']=str(work)
command=['/usr/bin/python3','/mnt/input/frozen/scripts/validation/desktop_app_probe.py','--appimage','/mnt/input/InkEcho.AppImage','--output',str(work/'ui')]
with(out/'gui.log').open('w')as log:result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=150)
if(work/'ui').exists():shutil.copytree(work/'ui',out/'ui')
(out/'gui-exit.json').write_text(json.dumps({'returncode':result.returncode,'command':command,'private_guest_ram_output':True,'strict_original_probe':True},indent=2))
print((out/'gui.log').read_text());result.check_returncode()
