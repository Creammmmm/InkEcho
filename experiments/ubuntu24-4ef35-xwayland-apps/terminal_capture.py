import os,sys,tty,traceback
try:
 fd=sys.stdin.fileno(); tty.setraw(fd)
 os.write(1,b'\033]0;InkEcho isolated terminal\007')
 with open('/tmp/xw-terminal-received','wb',buffering=0) as f:
  while True:
   b=os.read(fd,1024)
   if not b: break
   f.write(b)
except BaseException:
 open('/tmp/xw-tty-error','w').write(traceback.format_exc())
