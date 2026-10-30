from pathlib import Path
import subprocess,json,time,sys
r=Path('/home/lth/github/InkEcho/dist/gnome-bounded-owned-r3-desktop-20261030/vm24');name='inkecho-bounded-owned-r3-24-20261030';o=r/'output/preedit-candidate';rows=[]
command=['python3',str(r/'ssh.py'),'bounded-r3-preedit','env INKECHO_OUTPUT_STAGE=wayland /usr/bin/python3 /mnt/input/launch-preedit.py'];p=subprocess.Popen(command,stdout=(r/'preedit-driver.log').open('w'),stderr=subprocess.STDOUT);last=0
while p.poll()is None:
 q=o/'key-request.json'
 if q.exists():
  v=json.loads(q.read_text())
  if v['sequence']>last:
   assert v['sequence']==last+1 and v['keyval']in [110,105]
   state=v['actor'];assert state['active']and state['focus']and state['display_type']=='GdkWaylandDisplay'
   check=subprocess.run(['python3',str(r/'ssh.py'),'preedit-key-guard-'+str(v['sequence']),f"test $(id -u) = 1000; test $(stat -c %u /proc/{state['pid']}) = 1000; tr '\\0' ' ' < /proc/{state['pid']}/cmdline"],capture_output=True,text=True);assert check.returncode==0 and '/mnt/input/preedit-actor.py'in check.stdout
   result=subprocess.run(['docker','exec',name,'python3','/input/qmp-key.py',str(v['keyval'])],capture_output=True,text=True);assert result.returncode==0;rows.append({'sequence':v['sequence'],'keyval':v['keyval'],'actor_pid':state['pid'],'active':True,'focused':True,'returncode':result.returncode,'stdout':result.stdout});(r/'preedit-hardware-receipts.json').write_text(json.dumps(rows,indent=2));tmp=o/'key-ack.tmp';tmp.write_text(json.dumps({'sequence':v['sequence'],'ok':True}));tmp.replace(o/'key-ack.json');last=v['sequence']
 time.sleep(.05)
rc=p.wait();print(rc);print((r/'preedit-driver.log').read_text());sys.exit(rc)
