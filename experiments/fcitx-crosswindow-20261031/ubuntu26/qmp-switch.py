import socket,json
s=socket.create_connection(('127.0.0.1',4444));f=s.makefile('rwb');f.readline()
for c in [{'execute':'qmp_capabilities'},{'execute':'screendump','arguments':{'filename':'/output/screen.ppm'}},{'execute':'send-key','arguments':{'keys':[{'type':'qcode','data':'alt'},{'type':'qcode','data':'tab'}],'hold-time':120}}]:
 f.write((json.dumps(c)+'\n').encode());f.flush()
 while True:
  v=json.loads(f.readline())
  if 'error' in v:raise RuntimeError(v)
  if 'return' in v:break
