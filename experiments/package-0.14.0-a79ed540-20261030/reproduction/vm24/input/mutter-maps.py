from pathlib import Path
import subprocess,sys,json,hashlib,os,time
O=Path('/mnt/output');label=sys.argv[1];assert label in {'control','candidate','restored'}
for _ in range(100):
 r=subprocess.run(['pgrep','-u','1000','-x','gnome-shell'],capture_output=True,text=True)
 ids=r.stdout.split()
 if len(ids)==1:break
 time.sleep(.1)
assert len(ids)==1
pid=int(ids[0]);assert Path('/proc',str(pid),'exe').resolve()==Path('/usr/bin/gnome-shell')
paths=sorted({l.split()[-1]for l in Path('/proc',str(pid),'maps').read_text().splitlines()if 'libmutter' in l and '.so.' in l})
assert len(paths)==5,paths
rows=[];root=(O/(label+'-root')/'mnt/output/mutter-active').resolve() if label!='restored' else Path('/usr')
for name in paths:
 f=Path(name).resolve();assert f.is_relative_to(root),(f,root)
 rows.append({'path':str(f),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
env={l.partition('=')[0]:l.partition('=')[2]for l in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines()if l.partition('=')[0]in {'XDG_SESSION_TYPE','WAYLAND_DISPLAY'}};assert env.get('XDG_SESSION_TYPE')=='wayland'
result={'label':label,'pid':pid,'starttime':Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19],'exe':'/usr/bin/gnome-shell','libraries':rows,'actual_environment':env,'system_library_files_unchanged':hashlib.sha256(Path('/usr/lib/x86_64-linux-gnu/libmutter-14.so.0.0.0').read_bytes()).hexdigest()};(O/('maps-'+label+'.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result))
