import ctypes, os, signal, subprocess, time
import gi
gi.require_version('Gio','2.0')
from gi.repository import Gio,GLib
base=os.environ['INKECHO_STALE_DIR']
def mark(name): print('MONOTONIC_NS',name,time.monotonic_ns(),flush=True)
def read(role):
 try:
  with open('/tmp/inkecho-'+role+'.txt') as f:return f.read()
 except FileNotFoundError:return ''
def wait(predicate):
 until=time.monotonic()+8
 while time.monotonic()<until:
  if predicate():return
  time.sleep(.05)
 raise RuntimeError('timeout')
def spawn(role,module):
 env=os.environ.copy();env.update(GTK_IM_MODULE=module,XMODIFIERS='@im=ibus',GDK_BACKEND='x11',GTK_CSD='0',NO_AT_BRIDGE='1',GIO_USE_VFS='local')
 return subprocess.Popen(['/usr/bin/python3',base+'/window.py',role],env=env)
a=b=None
try:
 a=spawn('A','xim');wait(lambda:read('A').startswith('1|1|'));print('A_initial_focus',read('A'),flush=True)
 bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
 positive=bus.call_sync('org.fcitx.Fcitx5','/inkecho_test','org.fcitx.Fcitx.TestOnly','GuardedProbe',None,GLib.VariantType.new('(u)'),Gio.DBusCallFlags.NONE,3000,None).unpack()[0]
 print('TEST_ADDON_GUARDED_MATCH',positive,flush=True);assert positive==1;mark('initial_match')
 os.kill(a.pid,signal.SIGSTOP)
 wait(lambda:open('/proc/'+str(a.pid)+'/status').read().split('State:')[1].strip().startswith('T'));mark('A_stopped')
 if os.environ.get('INKECHO_STALE_FAULT')=='1':
  print('FAULT_AFTER_STOP',flush=True);time.sleep(3);raise RuntimeError('controlled failure')
 b=spawn('B','simple');wait(lambda:read('B').startswith('1|1|'));print('B_current_focus',read('B'),flush=True);mark('B_focused')
 lib=ctypes.CDLL('libX11.so.6');lib.XOpenDisplay.restype=ctypes.c_void_p;lib.XOpenDisplay.argtypes=[ctypes.c_char_p]
 lib.XGetInputFocus.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_int)]
 display=lib.XOpenDisplay(None);focused=ctypes.c_ulong();revert=ctypes.c_int();lib.XGetInputFocus(display,ctypes.byref(focused),ctypes.byref(revert))
 axid=int(read('A').split('|')[4]);bxid=int(read('B').split('|')[4]);print('X11_focus',focused.value,'A_xid',axid,'B_xid',bxid,flush=True)
 assert focused.value==bxid and focused.value!=axid
 pids=subprocess.check_output([os.environ['INKECHO_BUILD_DIR']+'/inkecho-xres-probe',str(axid),str(bxid)],text=True).strip().split()
 print('XRES_PIDS',pids,'EXPECTED',a.pid,b.pid,flush=True)
 assert [int(p) for p in pids]==[a.pid,b.pid] and a.pid != b.pid
 bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
 ibus_owner=bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','NameHasOwner',GLib.Variant('(s)',('org.freedesktop.IBus',)),GLib.VariantType.new('(b)'),Gio.DBusCallFlags.NONE,3000,None).unpack()[0]
 print('IBUS_BUS_OWNER',ibus_owner,flush=True);assert not ibus_owner
 info=bus.call_sync('org.fcitx.Fcitx5','/inkecho_test','org.fcitx.Fcitx.TestOnly','FocusedInfo',None,GLib.VariantType.new('(s)'),Gio.DBusCallFlags.NONE,3000,None).unpack()[0]
 print('FCITX_CONTEXT_INFO',info,flush=True);assert info.startswith('xim|')
 ctx_xid=bus.call_sync('org.fcitx.Fcitx5','/inkecho_test','org.fcitx.Fcitx.TestOnly','XimWindow',None,GLib.VariantType.new('(u)'),Gio.DBusCallFlags.NONE,3000,None).unpack()[0]
 print('TEST_ONLY_XIM_XID',ctx_xid,'ACTUAL_FOCUS',focused.value,flush=True)
 ctx_pids=subprocess.check_output([os.environ['INKECHO_BUILD_DIR']+'/inkecho-xres-probe',str(ctx_xid),str(focused.value)],text=True).strip().split()
 print('TEST_XIM_AND_FOCUS_PIDS',ctx_pids,flush=True)
 assert [int(p) for p in ctx_pids]==[a.pid,b.pid] and ctx_xid!=focused.value
 guard=bus.call_sync('org.fcitx.Fcitx5','/inkecho_test','org.fcitx.Fcitx.TestOnly','GuardedProbe',None,GLib.VariantType.new('(u)'),Gio.DBusCallFlags.NONE,3000,None).unpack()[0]
 print('TEST_ADDON_GUARDED_PROBE',guard,flush=True);assert guard==0;mark('mismatch_detected')
 print('TEST_GUARD_REJECT_ZERO_ATTEMPTS',True,flush=True)
 token='a'*64;path=os.environ['XDG_RUNTIME_DIR']+'/inkecho-fcitx-candidate.cap';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.write(fd,token.encode());os.close(fd)
 def call(method,signature,values,out):
  r=bus.call_sync('org.fcitx.Fcitx5','/inkecho','org.fcitx.Fcitx.InkEcho1',method,GLib.Variant(signature,values),GLib.VariantType.new(out),Gio.DBusCallFlags.NONE,3000,None).unpack()[0]
  print(method,r,flush=True);return r
 assert call('Begin3','(su)',(token,3),'(b)') is True
 mark('unsafe_commit_requested')
 result=call('Commit','(sus)',(token,0,'测'),'(u)');mark('unsafe_commit_returned')
 time.sleep(1)
 print('B_before_resume',read('B'),flush=True)
 assert read('B').split('|')[:4]==['1','1','','simple']
 for role,child in [('A',a),('B',b)]:
  lines=open('/proc/'+str(child.pid)+'/maps').read().splitlines()
  print(role+'_im_modules',sorted({line.split()[-1] for line in lines if '/immodules/' in line}),flush=True)
 mark('A_resume_requested');os.kill(a.pid,signal.SIGCONT);time.sleep(1.5)
 print('A_after_resume',read('A'),flush=True);print('B_after_resume',read('B'),flush=True)
 mark('final_observation');print('RESULT',result,flush=True)
 assert result==1 and read('A').split('|')[:3]==['0','0','测'] and read('B').split('|')[:4]==['1','1','','simple']
finally:
 for child in (a,b):
  if child and child.poll() is None:
   os.kill(child.pid,signal.SIGCONT);child.terminate()
   try:child.wait(timeout=2)
   except subprocess.TimeoutExpired:child.kill();child.wait()
