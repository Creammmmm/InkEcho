from pathlib import Path
import os,subprocess,time,json
import gi
gi.require_version('Gio','2.0')
from gi.repository import Gio,GLib
p=Path('/home/inkecho/ime-epoch-probe/r2');os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for l in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=l.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
assert os.environ['XDG_SESSION_TYPE']=='wayland'
subprocess.run(['gnome-extensions','enable','inkecho-ime-epoch-probe@local.invalid'],check=True)
print(subprocess.check_output(['gnome-extensions','info','inkecho-ime-epoch-probe@local.invalid'],text=True),flush=True)
name='io.github.Creammmmm.InkEcho.IMEpochProbe';path='/io/github/Creammmmm/InkEcho/IMEpochProbe';bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
def call(m,sig=None,args=None):return bus.call_sync(name,path,name+'1',m,GLib.Variant(sig,args) if sig else None,None,Gio.DBusCallFlags.NO_AUTO_START,2000,None).unpack()
children=[];logs=[];rows=[]
def state(kind):return json.loads((p/(kind+'.json')).read_text())
def command(child,value):child.stdin.write(value+'\n');child.stdin.flush();time.sleep(.15)
try:
 for kind,backend in [('wayland','wayland'),('simple','x11')]:
  env=dict(os.environ);env['GDK_BACKEND']=backend
  if kind=='simple':env['GTK_IM_MODULE']='gtk-im-context-simple'
  else:env.pop('GTK_IM_MODULE',None)
  log=(p/(kind+'-actor.log')).open('x');logs.append(log);children.append(subprocess.Popen(['/usr/bin/python3',str(p/'actor.py'),kind,str(p)],stdin=subprocess.PIPE,text=True,env=env,stdout=log,stderr=subprocess.STDOUT))
 time.sleep(2);a,b=children;assert a.poll() is None and b.poll() is None
 print(json.dumps({'owned_pids':[a.pid,b.pid],'startticks':[Path(f'/proc/{c.pid}/stat').read_text().rsplit(')',1)[1].split()[19] for c in children]}),flush=True)
 for trial in range(2):
  for mode in ['normal','switch','aba','cancel_rpc','intra']:
   assert call('Activate','(u)',[a.pid])==(True,);command(a,'intra' if mode=='intra' else 'a');time.sleep(.15)
   before=[state('wayland'),state('simple')]
   if mode=='cancel_rpc':
    loop=GLib.MainLoop();box={}
    def done(conn,result,*_):
     try:box['result']=conn.call_finish(result).unpack()
     except Exception as e:box['error']=type(e).__name__
     loop.quit()
    bus.call(name,path,name+'1','Test',GLib.Variant('(suu)',[mode,a.pid,b.pid]),None,Gio.DBusCallFlags.NO_AUTO_START,2000,None,done,None)
    cancellation=call('Cancel')
    if not box:loop.run()
    result=box.get('result',box)
   else:result=call('Test','(suu)',['normal' if mode=='intra' else mode,a.pid,b.pid]);cancellation=None
   time.sleep(.25);after=[state('wayland'),state('simple')]
   r={'trial':trial,'mode':mode,'result':result,'cancel_reply':cancellation,'delta_a':len(after[0]['a'])-len(before[0]['a']),'delta_b':len(after[1]['a'])-len(before[1]['a']),'native_total_delta':sum(len(after[0][k])-len(before[0][k]) for k in ['a','b']),'native_after':after[0],'final_native_focus_a':after[0]['focus_a'],'final_native_focus_b':after[0]['focus_b']};rows.append(r);print(json.dumps(r),flush=True)
finally:
 exits=[]
 for c in children:
  c.stdin.write('quit\n');c.stdin.flush();exits.append({'pid':c.pid,'exit':c.wait(timeout=5)})
 for f in logs:f.close()
 (p/'rows.json').write_text(json.dumps(rows,indent=2));print(json.dumps({'exits':exits}),flush=True)
