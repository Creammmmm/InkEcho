import sys,json,os
from pathlib import Path
browser=int(sys.argv[1]);ids=json.loads(sys.argv[2]);root=Path('/opt/inkecho-test-chrome/chrome');assert Path('/proc',str(browser),'exe').resolve()==root;out=[]
for pid in ids:
 assert type(pid)is int and pid>1
 current=pid;chain=[]
 for _ in range(12):
  if current==browser:break
  values=dict(x.split(':',1)for x in Path('/proc',str(current),'status').read_text().splitlines()if ':'in x);chain.append(current);current=int(values['PPid'])
 assert current==browser,('not owned child',pid)
 p=Path('/proc',str(pid));assert(p/'exe').resolve()==root;v=dict(x.split(':',1)for x in(p/'status').read_text().splitlines()if ':'in x)
 out.append({'pid':pid,'owned_parent_chain':chain,'seccomp':v.get('Seccomp','').strip(),'no_new_privs':v.get('NoNewPrivs','').strip(),'namespace_pids':v.get('NSpid','').split()})
print(json.dumps(out))
