from pathlib import Path
import os,subprocess,time,json
import gi
gi.require_version('Gio','2.0')
from gi.repository import Gio,GLib
p=Path('/tmp/inkecho-ibus-auto-v3-run-r3');os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for line in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=line.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
assert os.environ['XDG_SESSION_TYPE']=='wayland'
print(subprocess.check_output(['gnome-extensions','info','inkecho-ibus-auto-v3-probe@local.invalid'],text=True),flush=True)
actor=p/'actor.py';s=actor.read_text().replace('GLib.timeout_add_seconds(180,Gtk.main_quit)',"GLib.timeout_add(50, lambda: Gtk.main_quit() if (root/'stop').exists() else True)\nGLib.timeout_add_seconds(120,Gtk.main_quit)");actor.write_text(s)
before=json.loads((p/'before.json').read_text());rows=[];children=[];logs=[]
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None);name='io.github.Creammmmm.InkEcho.OwnedNativeGateV3';path='/io/github/Creammmmm/InkEcho/OwnedNativeGateV3'
def call(m,sig=None,values=None):
 return bus.call_sync(name,path,name+'1',m,GLib.Variant(sig,values) if sig else None,None,Gio.DBusCallFlags.NO_AUTO_START,2000,None).unpack()
def record(case,**extra):
 r={'case':case,'at':time.monotonic(),'read':call('Read'),**extra};rows.append(r);print(json.dumps(r),flush=True)
def activate(child):
 assert call('Activate','(u)',[child.pid])==(True,);time.sleep(.5)
try:
 for kind,backend in [('wayland','wayland'),('button','wayland'),('simple','x11')]:
  env=dict(os.environ);env.update(GDK_BACKEND=backend)
  if kind=='simple':env['GTK_IM_MODULE']='gtk-im-context-simple'
  else:env.pop('GTK_IM_MODULE',None)
  log=(p/(kind+'-actor.log')).open('x');logs.append(log);children.append(subprocess.Popen(['/usr/bin/python3',str(actor),kind,str(p)],env=env,stdout=log,stderr=subprocess.STDOUT))
 time.sleep(2);native,button,simple=children
 for c in children:assert c.poll() is None
 activate(native);print(json.dumps({'owned_pids':[c.pid for c in children],'begin':call('Begin','(u)',[native.pid])}),flush=True)
 activate(button);record('no_text_focus',status=call('Send','(u)',[0]))
 activate(native);record('normal_before');status=call('Send','(u)',[0]);time.sleep(.5);record('normal_after',status=status,owned_text=(p/'wayland.txt').read_text() if (p/'wayland.txt').exists() else '')
 subprocess.run(['ibus','engine','libpinyin'],check=False);time.sleep(.5)
 assert subprocess.check_output(['ibus','engine'],text=True).strip()=='libpinyin'
 assert call('Key','(u)',[110])==(True,);assert call('Key','(u)',[105])==(True,);time.sleep(.6)
 record('preedit_before');status=call('Send','(u)',[1]);time.sleep(.25);record('preedit_after',status=status,owned_text=(p/'wayland.txt').read_text() if (p/'wayland.txt').exists() else '',preedit_metadata=json.loads((p/'wayland-preedit.json').read_text()) if (p/'wayland-preedit.json').exists() else None)
 assert call('Key','(u)',[32])==(True,);time.sleep(.5);record('preedit_finished')
 status=call('SwitchSend','(uu)',[1,simple.pid]);time.sleep(.7);record('switch_after_enqueue',status=status,native_text=(p/'wayland.txt').read_text() if (p/'wayland.txt').exists() else '',simple_text=(p/'simple.txt').read_text() if (p/'simple.txt').exists() else '')
 record('cancel',cancel=call('Cancel'),status=call('Send','(u)',[2]))
finally:
 try:print(json.dumps({'final_cancel':call('Cancel')}),flush=True)
 except Exception as e:print(type(e).__name__,flush=True)
 subprocess.run(['ibus','engine',before['engine']],check=False)
 (p/'stop').touch();exits=[]
 for c in children:
  try:exits.append({'pid':c.pid,'exit':c.wait(timeout=5)})
  except subprocess.TimeoutExpired:exits.append({'pid':c.pid,'still_running':True})
 for log in logs:log.close()
 (p/'rows.json').write_text(json.dumps(rows,indent=2));print(json.dumps({'exits':exits,'engine_after':subprocess.check_output(['ibus','engine'],text=True).strip()}),flush=True)
