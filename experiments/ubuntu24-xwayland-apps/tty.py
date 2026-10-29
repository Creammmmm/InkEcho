import os,sys,tty
fd=sys.stdin.fileno(); tty.setraw(fd)
with open('/tmp/xw-terminal-received','wb',buffering=0) as f:
 while True:
  b=os.read(fd,1024)
  if not b: break
  f.write(b)
