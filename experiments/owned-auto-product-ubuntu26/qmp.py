import json,socket,sys,time
s=socket.create_connection(('127.0.0.1',4444),timeout=5); f=s.makefile('rwb',buffering=0)
def read():
 while True:
  line=f.readline()
  if not line: raise EOFError
  value=json.loads(line)
  if 'event' not in value:return value
def cmd(name,args=None):
 data={'execute':name}
 if args is not None:data['arguments']=args
 f.write((json.dumps(data)+'\n').encode()); reply=read()
 if 'error' in reply:raise RuntimeError(reply)
 return reply
read();cmd('qmp_capabilities')
def key(spec):
 cmd('human-monitor-command',{'command-line':'sendkey '+spec});time.sleep(.025)
def write(text):
 keys={' ':'spc','/':'slash','-':'minus','=':'equal',',':'comma','.':'dot','_':'shift-minus'}
 for c in text:
  name=keys.get(c)
  if name is None:name=('shift-'+c.lower()) if c.isupper() else c
  key(name)
if sys.argv[1]=='screenshot':cmd('screendump',{'filename':'/output/screen.ppm'})
elif sys.argv[1]=='run':
 key('esc');key('alt-f2');time.sleep(1);key('ctrl-a');write(sys.argv[2]);key('ret')
else: raise ValueError('invalid command')
