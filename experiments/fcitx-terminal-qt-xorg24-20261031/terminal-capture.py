import os, sys, termios, tty
path=sys.argv[1]
fd=sys.stdin.fileno(); old=termios.tcgetattr(fd)
try:
 tty.setraw(fd)
 with open(path,'ab',buffering=0) as output:
  while True:
   data=os.read(fd,4096)
   if not data: break
   output.write(data)
finally:termios.tcsetattr(fd,termios.TCSADRAIN,old)
