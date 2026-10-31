from pathlib import Path
import os,sys,shutil,subprocess,json
p=Path.home()/'inkecho-session-xorg24';sys.path[:0]=[str(p/'src'),str(p/'deps')];os.environ.update(DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000')
from inkecho.platform.fcitx5_install import FcitxInstaller
stop=subprocess.run(['/usr/bin/fcitx5-remote','-e'],capture_output=True,text=True);FcitxInstaller(source=p/'candidate').disable();profile=Path.home()/'.config/fcitx5/profile';shutil.copy2(p/'restore/profile',profile)
for path in [Path.home()/'.config/autostart/fcitx5-inkecho-qa.desktop',Path.home()/'.config/environment.d/90-inkecho-qa.conf']:
 assert path.exists() and path.is_file() and not path.is_symlink();path.unlink()
(p/'cleanup-login.json').write_text(json.dumps({'fcitx_exit_command':stop.returncode,'profile_restored':profile.read_bytes()==(p/'restore/profile').read_bytes(),'addon_absent':not (Path.home()/'.local/share/fcitx5/addon/inkecho.conf').exists(),'autostart_absent':True,'environment_file_absent':True},indent=2));print((p/'cleanup-login.json').read_text())
