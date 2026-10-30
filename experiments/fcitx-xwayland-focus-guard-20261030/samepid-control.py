import ctypes,os,signal,subprocess,time
import gi
gi.require_version('Gio','2.0')
from gi.repository import Gio,GLib
p=None
def mark(name): print('MONOTONIC_NS',name,time.monotonic_ns(),flush=True)
def wait(f):
 end=time.monotonic()+8
 while time.monotonic()<end:
  try:
   v=f()
   if v:return v
  except FileNotFoundError:pass
  time.sleep(.05)
 raise RuntimeError('timeout')
def data():
 with open('/tmp/samepid-state.txt') as f:v=f.read().split('|')
 return v if len(v)==4 and v[2:]==['1','1'] else None
try:
 env=os.environ.copy();env.update(GTK_IM_MODULE='xim',XMODIFIERS='@im=ibus',GDK_BACKEND='x11',GTK_CSD='0',NO_AT_BRIDGE='1',GIO_USE_VFS='local')
 p=subprocess.Popen(['/usr/bin/python3',os.environ['INKECHO_STALE_DIR']+'/samepid-window.py'],env=env)
 v=wait(data);a,b=int(v[0]),int(v[1]);bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
 def call(name):return bus.call_sync('org.fcitx.Fcitx5','/inkecho_test','org.fcitx.Fcitx.TestOnly',name,None,GLib.VariantType.new('(u)'),Gio.DBusCallFlags.NONE,3000,None).unpack()[0]
 initial=call('AncestorProbe');print('INITIAL_ANCESTOR',initial,flush=True);assert initial==1;mark('initial_match')
 print('INITIAL_GUARD',call('GuardedProbe'),flush=True)
 os.kill(p.pid,signal.SIGSTOP);wait(lambda:open('/proc/'+str(p.pid)+'/status').read().split('State:')[1].strip().startswith('T'));mark('client_stopped')
 if os.environ.get('INKECHO_STALE_FAULT')=='1':
  print('FAULT_AFTER_STOP',flush=True);time.sleep(3);raise RuntimeError('controlled failure')
 lib=ctypes.CDLL('libX11.so.6');lib.XOpenDisplay.restype=ctypes.c_void_p;lib.XOpenDisplay.argtypes=[ctypes.c_char_p];lib.XSetInputFocus.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];lib.XGetInputFocus.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_int)];lib.XFlush.argtypes=[ctypes.c_void_p]
 d=lib.XOpenDisplay(None);lib.XSetInputFocus(d,b,1,0);lib.XFlush(d);cur=ctypes.c_ulong();revert=ctypes.c_int();lib.XGetInputFocus(d,ctypes.byref(cur),ctypes.byref(revert));old=call('XimWindow');guard=call('GuardedProbe')
 ids=subprocess.check_output([os.environ['INKECHO_BUILD_DIR']+'/inkecho-xres-probe',str(old),str(cur.value)],text=True).strip().split()
 mark('B_focus_observed');print('WINDOWS',a,b,'FOCUS',cur.value,'XIM',old,'PIDS',ids,'PID',p.pid,'GUARD',guard,flush=True)
 assert cur.value==b and old!=b and [int(x) for x in ids]==[p.pid,p.pid] and guard==1
 ancestor=call('AncestorProbe');print('ANCESTOR_GUARD',ancestor,flush=True);assert ancestor==0;mark('mismatch_detected')
 print('SAME_PID_GUARD_FALSE_POSITIVE',True,flush=True)
finally:
 if p and p.poll() is None:
  os.kill(p.pid,signal.SIGCONT);p.terminate()
  try:p.wait(timeout=2)
  except subprocess.TimeoutExpired:p.kill();p.wait()
