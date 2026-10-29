import subprocess,time,json,pathlib
O=pathlib.Path('/tmp/inkecho-begin4-qualification26/output');name='inkecho-begin4-qualification26-20261030'
ssh=['docker','exec',name,'ssh','-T','-i','/secrets/testkey','-p2222','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=/prior/known_hosts','inkecho@127.0.0.1','python3 /mnt/input/launch-gtk.py']
p=subprocess.Popen(ssh,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);done=set();receipts=[];end=time.monotonic()+140
while p.poll() is None and time.monotonic()<end:
 q=O/'gtk-begin4-26-r3-mailbox/key-request.json'
 if q.exists():
  r=json.loads(q.read_text());s=r['sequence']
  if s not in done:
   assert r['owned_active'] and r['owned_focus'] and r['keyval'] in {97,110,105,32},r
   guard='import json,subprocess,pathlib,os; os.environ.update(DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus",XDG_RUNTIME_DIR="/run/user/1000"); os.environ.update(dict(l.split("=",1) for l in subprocess.check_output(["systemctl","--user","show-environment"],text=True).splitlines() if l.startswith(("DISPLAY=","XAUTHORITY=")))); d=json.loads(pathlib.Path("/run/user/1000/inkecho-package-gate-0.11.0/fcitx-begin4-26-r3/actor.json").read_text()); assert d["pid"]=='+str(r['owned_pid'])+' and d["active"] and d["focus"]; assert b"return-gtk-actor.py" in pathlib.Path("/proc/"+str(d["pid"])+"/cmdline").read_bytes(); assert int(subprocess.check_output(["xdotool","getactivewindow","getwindowpid"]))==d["pid"]; print("owned actor current")'
   check=subprocess.run(ssh[:-1]+['python3 -c '+__import__('shlex').quote(guard)],capture_output=True,text=True,timeout=8)
   receipts.append({'request':r,'fresh_actor_guard_returncode':check.returncode,'stdout':check.stdout,'stderr':check.stderr});(O/'gtk-hardware-r3-receipts.json').write_text(json.dumps(receipts,indent=2));assert check.returncode==0
   done.add(s);a=subprocess.run(['docker','exec',name,'python3','/input/qmp-key.py',str(r['keyval'])],capture_output=True,text=True,timeout=8);receipts.append({'request':r,'returncode':a.returncode,'stdout':a.stdout,'stderr':a.stderr});(O/'gtk-hardware-r3-receipts.json').write_text(json.dumps(receipts,indent=2));assert a.returncode==0
   (O/'gtk-begin4-26-r3-mailbox/key-ack.json').write_text(json.dumps({'sequence':s,'qmp_ok':True}))
 time.sleep(.08)
assert p.poll() is not None,'GTK bounded host timeout'
a,b=p.communicate(timeout=3);(O/'gtk-host-r3-exit.json').write_text(json.dumps({'returncode':p.returncode,'stdout':a,'stderr':b},indent=2));print(p.returncode,a,b)
