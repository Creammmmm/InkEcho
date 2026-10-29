from pathlib import Path
import os,subprocess,time,json
import gi
gi.require_version('Gio','2.0')
from gi.repository import Gio,GLib
p=Path('/home/inkecho/ime-order-probe');os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for l in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=l.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
assert os.environ['XDG_SESSION_TYPE']=='wayland'
subprocess.run(['gnome-extensions','enable','inkecho-ime-order-probe@local.invalid'],check=True)
print(subprocess.check_output(['gnome-extensions','info','inkecho-ime-order-probe@local.invalid'],text=True),flush=True)
actor=p/'actor.py';s=actor.read_text().replace('GLib.timeout_add_seconds(180,Gtk.main_quit)',"GLib.timeout_add(50,lambda:Gtk.main_quit() if (root/'stop').exists() else True)\nGLib.timeout_add_seconds(90,Gtk.main_quit)");actor.write_text(s)
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None);name='io.github.Creammmmm.InkEcho.IMOrderProbe';path='/io/github/Creammmmm/InkEcho/IMOrderProbe'
def call(m,sig,args):return bus.call_sync(name,path,name+'1',m,GLib.Variant(sig,args),None,Gio.DBusCallFlags.NO_AUTO_START,2000,None).unpack()
def text(kind):
 f=p/(kind+'.txt');return f.read_text() if f.exists() else ''
children=[];logs=[];rows=[]
try:
 for kind,backend in [('wayland','wayland'),('simple','x11')]:
  env=dict(os.environ);env['GDK_BACKEND']=backend
  if kind=='simple':env['GTK_IM_MODULE']='gtk-im-context-simple'
  else:env.pop('GTK_IM_MODULE',None)
  log=(p/(kind+'-actor.log')).open('x');logs.append(log);children.append(subprocess.Popen(['/usr/bin/python3',str(actor),kind,str(p)],env=env,stdout=log,stderr=subprocess.STDOUT))
 time.sleep(2);a,b=children
 assert a.poll() is None and b.poll() is None
 print(json.dumps({'owned_pids':[a.pid,b.pid],'starts':[Path(f'/proc/{c.pid}/stat').read_text().rsplit(')',1)[1].split()[19] for c in children]}),flush=True)
 for trial in range(5):
  for mode in ['stable','inline','idle','contended']:
   assert call('Activate','(u)',[a.pid])==(True,);time.sleep(.15)
   before=[text('wayland'),text('simple')]
   result=call('Test','(suu)',[mode,a.pid,b.pid]);time.sleep(.2)
   after=[text('wayland'),text('simple')]
   r={'trial':trial,'mode':mode,'result':result,'delta_a':len(after[0])-len(before[0]),'delta_b':len(after[1])-len(before[1]),'before_counts':[len(v) for v in before],'after_counts':[len(v) for v in after]};rows.append(r);print(json.dumps(r),flush=True)
finally:
 (p/'stop').touch();exits=[]
 for c in children:
  try:exits.append({'pid':c.pid,'exit':c.wait(timeout=5)})
  except subprocess.TimeoutExpired:exits.append({'pid':c.pid,'still_running':True})
 for f in logs:f.close()
 (p/'rows.json').write_text(json.dumps(rows,indent=2));print(json.dumps({'exits':exits}),flush=True)
