from pathlib import Path
import os,json,hashlib,shutil,subprocess
os.environ.update(DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000')
import sys
sys.path[:0]=[str(Path(json.loads(Path('/mnt/output/wayland/mount.json').read_text())['appdir'])/'packages')]
from inkecho.platform.owned_installation import installed_directory,verified_installation,FILES,LEGACY_FILES
from inkecho.platform.owned_extension import OwnedExtensionManager
root=installed_directory();out=Path('/mnt/output');old={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size}for p in root.iterdir()if p.is_file()};assert old==LEGACY_FILES and verified_installation()
from inkecho.platform.ibus_extension import ExtensionError
checks={}
for operation in ['install','enable']:
 try:getattr(OwnedExtensionManager(),operation)()
 except ExtensionError as error:checks[operation]={'refused':True,'diagnostic':str(error)}
 else:raise AssertionError('legacy installation unexpectedly accepted')
 assert {p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size}for p in root.iterdir()if p.is_file()}==old
(out/'old-install-upgrade-guard.json').write_text(json.dumps({'checks':checks,'old_assets_unchanged':True},ensure_ascii=False,indent=2))
backup=out/'original-v5-assets';shutil.copytree(root,backup);subprocess.run(['/usr/bin/gnome-extensions','disable',root.name],check=True)
shutil.move(root,str(Path('/run/user/1000')/'original-v5-disabled'))
m=OwnedExtensionManager();m.install();assert verified_installation();new={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size}for p in root.iterdir()if p.is_file()};assert new==FILES
(out/'stage-candidate-extension.json').write_text(json.dumps({'before':old,'after':new,'old_complete':True,'new_complete':True,'explicit_isolated_test_install':True,'runtime_reload_required':True},indent=2));print('explicit candidate install complete; old complete assets preserved; not enabled until normal GNOME reload')
