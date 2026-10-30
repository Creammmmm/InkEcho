from pathlib import Path
import subprocess,os,sys,json,hashlib,time
O=Path('/mnt/output');assert os.getuid()==1000 and Path('/etc/os-release').read_text().find('VERSION_ID="24.04"')>=0
assert 'inkecho_output /mnt/output 9p' in Path('/proc/mounts').read_text()
active=O/'mutter-active';drop=Path.home()/'.config/systemd/user/org.gnome.Shell@wayland.service.d/90-inkecho-mutter-lab.conf'
content='[Service]\nEnvironment="LD_LIBRARY_PATH=/mnt/output/mutter-active/lib/x86_64-linux-gnu:/mnt/output/mutter-active/lib/x86_64-linux-gnu/mutter-14"\nEnvironment="GI_TYPELIB_PATH=/mnt/output/mutter-active/lib/x86_64-linux-gnu/mutter-14"\n'
legacy_content=content
content='[Service]\nExecStart=\nExecStart=/usr/bin/sudo -n --preserve-env=NOTIFY_SOCKET,XDG_RUNTIME_DIR,XDG_SESSION_TYPE,XDG_SESSION_ID /mnt/input/private-mutter-namespace.sh\nNotifyAccess=all\n'
action=sys.argv[1];assert action in {'control','retry-control','candidate','restore'}
if action=='control':assert not drop.exists() and not active.exists() and not active.is_symlink()
if action=='retry-control':assert drop.read_text()==legacy_content and active.is_symlink() and 'control-root' in str(active.resolve())
if action=='candidate':assert drop.read_text()==content and active.is_symlink() and 'control-root' in str(active.resolve())
if action=='restore':assert drop.read_text()==content and active.is_symlink()
if action!='restore':
 chosen='control' if action=='retry-control' else action
 root=O/(chosen+'-root');manifest=json.loads((O/(chosen+'-files.json')).read_text())
 for name,r in manifest.items():
  if '/libmutter' in name and '.so.' in name:
   p=root/name;assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
subprocess.run(['sudo','-n','systemctl','stop','gdm3'],check=True)
for _ in range(100):
 r=subprocess.run(['pgrep','-u','1000','-x','gnome-shell'],capture_output=True,text=True)
 if r.returncode==1:break
 time.sleep(.1)
else:raise RuntimeError('normal GDM stop left user Shell alive')
if action=='restore':drop.unlink();active.unlink()
else:
 if action in {'control','retry-control'}:drop.parent.mkdir(parents=True,exist_ok=True);drop.write_text(content)
 temp=O/'mutter-active-next';assert not temp.exists() and not temp.is_symlink();temp.symlink_to(O/(chosen+'-root')/'mnt/output/mutter-active');temp.replace(active)
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
subprocess.run(['sudo','-n','systemctl','start','gdm3'],check=True)
(O/('switch-'+action+'.json')).write_text(json.dumps({'action':action,'private_dropin':str(drop),'active_target':str(active.resolve())if active.exists()else None,'system_mutter_files_untouched':True,'normal_gdm_stop_start':True},indent=2));print(action+' private session switch requested')
