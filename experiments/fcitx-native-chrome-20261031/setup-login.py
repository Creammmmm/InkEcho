from pathlib import Path
import json,os,sys,shutil,subprocess
p=Path.home()/'fcitx-native-login-1031';sys.path[:0]=[str(p/'src'),str(p/'deps')];os.environ.update(DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000');os.umask(0o077)
for folder in [p/'candidate',p/'candidate/candidate']:folder.chmod(0o700)
for item in (p/'candidate').rglob('*'):
 if item.is_file():item.chmod(0o600)
from inkecho.platform.fcitx5_install import FcitxInstaller
backup=p/'restore';backup.mkdir();conf=Path.home()/'.config';profile=conf/'fcitx5/profile';shutil.copy2(profile,backup/'profile');auto=conf/'autostart/fcitx5-inkecho-qa.desktop';assert not auto.exists();env=conf/'environment.d/90-inkecho-qa.conf';assert not env.exists();auto.parent.mkdir(mode=0o700,parents=True,exist_ok=True);env.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
profile.write_text('[Groups/0]\nName=Default\nDefault Layout=us\nDefaultIM=pinyin\n\n[Groups/0/Items/0]\nName=keyboard-us\nLayout=\n\n[Groups/0/Items/1]\nName=pinyin\nLayout=\n\n[GroupOrder]\n0=Default\n')
auto.write_text('[Desktop Entry]\nType=Application\nName=InkEcho isolated QA Fcitx\nExec=/usr/bin/fcitx5 -D --disable clipboard\nX-GNOME-Autostart-enabled=true\n')
env.write_text('XMODIFIERS=@im=fcitx\nGTK_IM_MODULE=fcitx\nQT_IM_MODULE=fcitx\n')
i=FcitxInstaller(source=p/'candidate');i.install();(p/'setup-login-result.json').write_text(json.dumps({'installed':True,'auto':str(auto),'environment':str(env),'profile_backup':str(backup/'profile')}));print('guest setup done')
