from pathlib import Path
import json,subprocess,time,os
out=Path('/mnt/output/xorg-session-proof.json');history=[]
for attempt in range(30):
 rows=[]
 for line in subprocess.check_output(['loginctl','list-sessions','--no-legend'],text=True).splitlines():
  ident=line.split()[0];text=subprocess.check_output(['loginctl','show-session',ident,'-p','Name','-p','Seat','-p','Type','-p','State'],text=True);rows.append(dict(x.split('=',1)for x in text.splitlines()if '='in x))
 env=dict(os.environ,DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000');manager=subprocess.check_output(['systemctl','--user','show-environment'],env=env,text=True);xorg=subprocess.run(['pgrep','-x','Xorg'],capture_output=True,text=True)
 good=any(x.get('Name')=='inkecho'and x.get('Seat')=='seat0'and x.get('Type')=='x11'and x.get('State')=='active'for x in rows)and 'XDG_SESSION_TYPE=x11'in manager and xorg.returncode==0
 history.append({'attempt':attempt,'sessions':rows,'environment':{k:v for k,_,v in [x.partition('=')for x in manager.splitlines()]if k in {'XDG_SESSION_TYPE','XDG_CURRENT_DESKTOP','DISPLAY','WAYLAND_DISPLAY'}},'xorg_pids':xorg.stdout.split(),'passed':good});out.write_text(json.dumps(history,indent=2))
 if good:
  subprocess.run(['systemctl','--user','unset-environment','WAYLAND_DISPLAY'],env=env,check=True);print(json.dumps(history[-1]));break
 time.sleep(.5)
else:raise AssertionError('real Xorg session not ready')
