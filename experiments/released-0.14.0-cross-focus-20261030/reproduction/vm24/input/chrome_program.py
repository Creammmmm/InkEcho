from pathlib import Path
import json,hashlib,os,stat
ROOT=Path('/opt/inkecho-test-chrome')
def audit_program():
 m=Path('/mnt/input/chrome-software-manifest.json');assert hashlib.sha256(m.read_bytes()).hexdigest()=="208eb4c91aed99ca97bbf68b8d5e7190190ca36d745d10dfdb9130d8de1b4ee4";pins=json.loads(m.read_text())['files'];actual={str(p.relative_to(ROOT))for p in ROOT.rglob('*')if p.is_file()};assert actual==set(pins)
 for n,v in pins.items():
  p=ROOT/n;s=p.lstat();assert stat.S_ISREG(s.st_mode)and s.st_uid==s.st_gid==0 and not(s.st_mode&0o022);assert hashlib.sha256(p.read_bytes()).hexdigest()==v
 assert stat.S_IMODE((ROOT/'chrome-sandbox').stat().st_mode)==0o4755
 return {'root':str(ROOT),'files':len(pins),'manifest_sha256':hashlib.sha256(m.read_bytes()).hexdigest(),'binary_sha256':pins['chrome'],'sandbox_sha256':pins['chrome-sandbox'],'sandbox_uid':0,'sandbox_mode':'4755','sandbox_runtime_acceptance':'requires separate renderer checks'}
def assert_owned_executable(pid):assert Path('/proc',str(pid),'exe').resolve()==ROOT/'chrome'
