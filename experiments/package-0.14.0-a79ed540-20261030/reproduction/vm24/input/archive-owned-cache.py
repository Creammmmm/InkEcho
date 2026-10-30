EXPECTED='93789a02a89fd28021a1c334c05e26e2abd9712573877be9d635e28469a6f894'
from pathlib import Path
import json,hashlib,tarfile,shutil,os
root=Path('/run/user/1000/inkecho-package-gate-0.14.0/appimage_extracted_65a2a2b4e5ecb70b06c1169683b768a6');out=Path('/mnt/output');invpath='usr/share/doc/inkecho/inventory.json'
assert root.is_dir()and not root.is_symlink()and root.stat().st_uid==1000
inventory_bytes=(root/invpath).read_bytes();assert hashlib.sha256(inventory_bytes).hexdigest()==EXPECTED
inv=json.loads(inventory_bytes);expected=dict(inv['files']);expected[invpath]=hashlib.sha256(inventory_bytes).hexdigest()
regular={str(p.relative_to(root))for p in root.rglob('*')if p.is_file()and not p.is_symlink()};assert regular==set(expected)
for name,value in expected.items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==(value['sha256']if isinstance(value,dict)else value),name
for name,value in inv['symlinks'].items():assert (root/name).is_symlink()and str((root/name).readlink())==value,name
refs=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  if proc.stat().st_uid!=1000:continue
  if str(root)in(proc/'maps').read_text():refs.append(proc.name+':maps')
  for fd in(proc/'fd').iterdir():
   try:
    if str(root)in os.readlink(fd):refs.append(proc.name+':fd')
   except OSError:pass
 except(OSError,PermissionError):pass
assert not refs,refs
archive=out/'verified-owned-appimage-cache.tar.gz';assert not archive.exists()
with tarfile.open(archive,'w:gz',compresslevel=1)as tar:tar.add(root,arcname='AppDir',recursive=True)
archive.chmod(0o600);count=0
with tarfile.open(archive,'r:gz')as tar:
 for member in tar:
  if member.isfile():
   name=member.name.removeprefix('AppDir/');data=tar.extractfile(member);value=expected[name];assert hashlib.file_digest(data,'sha256').hexdigest()==(value['sha256']if isinstance(value,dict)else value);count+=1
  elif member.issym():assert inv['symlinks'][member.name.removeprefix('AppDir/')]==member.linkname
assert count==len(expected)
before=shutil.disk_usage('/run/user/1000');digest=hashlib.sha256(archive.read_bytes()).hexdigest();shutil.rmtree(root);after=shutil.disk_usage('/run/user/1000');record={'verified_rebuildable_cache':str(root),'source_inventory_sha256':EXPECTED,'regular_files_verified':count,'active_references':refs,'archive':str(archive),'archive_sha256':digest,'archive_bytes':archive.stat().st_size,'archive_all_regular_and_symlink_payloads_verified':True,'freed_bytes':after.free-before.free,'run_free_after':after.free,'only_verified_cache_removed':True};(out/'cache-cleanup-receipt.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))
