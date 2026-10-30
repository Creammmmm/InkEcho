from pathlib import Path
import json,hashlib,os,shutil,subprocess,ast
assert os.getuid()==1000
u='inkecho-ibus-owned-v5-prototype@local.invalid';root=Path.home()/'.local/share/gnome-shell/extensions'/u;source=Path('/mnt/input/candidate-src/inkecho/platform/ibus_owned_candidate');expected=json.loads(Path('/mnt/input/bounded-r1-assets.json').read_text())
def inventory(path):
 assert not path.is_symlink()
 out={}
 for p in path.iterdir():
  assert p.is_file() and not p.is_symlink() and p.stat().st_uid==1000
  out[p.name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size}
 return out
before=inventory(root);assert before==expected
module=ast.parse(Path('/mnt/input/candidate-src/inkecho/platform/owned_installation.py').read_text());after=ast.literal_eval(next(n.value for n in module.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='FILES'for x in n.targets)));assert inventory(source)==after
stage=root.parent/'.inkecho-r2-stage';held=root.parent/'.inkecho-r1-held';assert not stage.exists() and not held.exists();shutil.copytree(source,stage);assert inventory(stage)==after
subprocess.run(['gnome-extensions','disable',u],check=True);root.rename(held);stage.rename(root);assert inventory(root)==after
Path('/mnt/output/update-bounded-r2.json').write_text(json.dumps({'before':before,'after':after,'explicit_isolated_complete_asset_upgrade':True,'normal_reload_required':True,'held_r1_path':str(held)},indent=2));print('complete r1 verified; complete r2 installed; no protocol text sent')
