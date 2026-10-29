import os,sys,subprocess,json,time
from pathlib import Path
import gi
gi.require_version('Gio','2.0');gi.require_version('IBus','1.0');gi.require_version('Atspi','2.0')
from gi.repository import Gio,GLib,IBus,Atspi
p=Path('/home/inkecho/ime-metadata-r3');sys.path.insert(0,str(p));from policy import verdict
os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for l in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=l.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
subprocess.run(['gnome-extensions','enable','inkecho-ibus-metadata-combination@local.invalid'],check=True)
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None);IBus.init();ib=IBus.Bus.new();assert ib.is_connected()
def panel():return json.loads(bus.call_sync('io.github.Creammmmm.InkEcho.MetadataCombination','/io/github/Creammmmm/InkEcho/MetadataCombination','io.github.Creammmmm.InkEcho.MetadataCombination1','Read',None,None,Gio.DBusCallFlags.NO_AUTO_START,2000,None).unpack()[0])
def walk(node,d=0):
 if d>12:return
 yield node
 for i in range(min(node.get_child_count(),64)):
  child=node.get_child_at_index(i)
  if child:yield from walk(child,d+1)
def target(pid):
 root=Atspi.get_desktop(0)
 for i in range(min(root.get_child_count(),128)):
  app=root.get_child_at_index(i)
  if app and app.get_process_id()==pid:
   focused=[e for e in walk(app) if e.get_state_set().contains(Atspi.StateType.FOCUSED)]
   if len(focused)!=1:return {'pid':pid,'focus_count':len(focused)}
   e=focused[0];r={'pid':pid,'focused':True,'editable':e.get_state_set().contains(Atspi.StateType.EDITABLE),'text_interface':e.is_text(),'role':int(e.get_role())}
   if e.is_component():
    for name,coord in [('screen',Atspi.CoordType.SCREEN),('window',Atspi.CoordType.WINDOW)]:
     v=e.get_component_iface().get_extents(coord);r[name]=[v.x,v.y,v.width,v.height]
   return r
 return None
result=p/'owned.json';env=dict(os.environ);env.update(GDK_BACKEND='wayland',GTK_IM_MODULE='ibus');log=(p/'actor.log').open('x');actor=subprocess.Popen(['/usr/bin/python3',str(p/'actor.py'),str(result)],env=env,stdin=subprocess.PIPE,text=True,stdout=log,stderr=subprocess.STDOUT);rows=[]
try:
 for _ in range(100):
  if result.exists() and json.loads(result.read_text()).get('active'):break
  time.sleep(.05)
 for k in ['ibus','simple','button','ibus']:
  actor.stdin.write(k+'\n');actor.stdin.flush();time.sleep(.6)
  first=panel();t=target(actor.pid);current=ib.current_input_context();second=panel();v=verdict(second,t,current) if first['epoch']==second['epoch'] else 'changed'
  row={'case':k,'panel':second,'target':t,'current':current,'verdict':v,'owned':json.loads(result.read_text())};rows.append(row);print(json.dumps(row),flush=True)
finally:
 actor.stdin.write('quit\n');actor.stdin.flush();print(json.dumps({'actor':actor.pid,'exit':actor.wait(timeout=5)}),flush=True);log.close();(p/'rows.json').write_text(json.dumps(rows,indent=2))
