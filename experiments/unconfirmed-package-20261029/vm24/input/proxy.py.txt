import socket,threading,os
path='/output/ssh.sock'
try: os.unlink(path)
except FileNotFoundError: pass
server=socket.socket(socket.AF_UNIX); server.bind(path); os.chmod(path,0o600); server.listen(4)
def copy(a,b):
 try:
  while data:=a.recv(65536): b.sendall(data)
 except OSError: pass
 finally:
  try:b.shutdown(socket.SHUT_WR)
  except OSError:pass
while True:
 a,_=server.accept()
 try:
  b=socket.create_connection(('127.0.0.1',2222),timeout=10)
  b.settimeout(None)
 except OSError:a.close();continue
 threading.Thread(target=copy,args=(a,b),daemon=True).start();threading.Thread(target=copy,args=(b,a),daemon=True).start()
