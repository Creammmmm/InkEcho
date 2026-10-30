import socket,json,sys,time
commands=[{'execute':'qmp_capabilities'}]
if sys.argv[1]=='escape':commands.append({'execute':'send-key','arguments':{'keys':[{'type':'qcode','data':'esc'}],'hold-time':80}})
else:
 key={97:'a',110:'n',105:'i',32:'spc',65293:'ret'}[int(sys.argv[1])];commands.append({'execute':'send-key','arguments':{'keys':[{'type':'qcode','data':key}],'hold-time':80}})
s=socket.create_connection(('127.0.0.1',4444));f=s.makefile('rwb');f.readline()
for command in commands:
 f.write((json.dumps(command)+'\n').encode());f.flush()
 while True:
  r=json.loads(f.readline())
  if 'return'in r:break
  if 'error'in r:raise RuntimeError(r)
print(json.dumps({'ok':True,'key':sys.argv[1]}))
