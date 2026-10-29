import os,json,time,subprocess
from pathlib import Path
import gi
gi.require_version('Gio','2.0');gi.require_version('IBus','1.0')
from gi.repository import Gio,GLib,IBus
p=Path('/home/inkecho/owned-context');assert Path('/etc/machine-id').read_text().strip()=='80d223263a5e4ed1b8749d7f30116d5f'
os.environ.update(XDG_RUNTIME_DIR='/run/user/1000',DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus')
for l in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=l.partition('=')
 if k in {'DISPLAY','WAYLAND_DISPLAY','XAUTHORITY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'}:os.environ[k]=v
subprocess.run(['gnome-extensions','enable','inkecho-gnome-owned-context@local.invalid'],check=True)
bus=Gio.bus_get_sync(Gio.BusType.SESSION,None);N='io.github.Creammmmm.InkEcho.GnomeOwnedContext';P='/io/github/Creammmmm/InkEcho/GnomeOwnedContext'
def rpc(dest,path,iface,member,params=None):return bus.call_sync(dest,path,iface,member,params,None,Gio.DBusCallFlags.NONE,2000,None).unpack()
for _ in range(40):
 try:
  rpc('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetNameOwner',GLib.Variant('(s)',(N,)));break
 except GLib.Error:time.sleep(.05)
owner=rpc('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetNameOwner',GLib.Variant('(s)',(N,)))[0];pid=rpc('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','GetConnectionUnixProcessID',GLib.Variant('(s)',(owner,)))[0];exe=Path(f'/proc/{pid}/exe').resolve();assert str(exe)=='/usr/bin/gnome-shell' and exe.stat().st_uid==0;print(json.dumps({'trusted_shell_pid':pid,'unique_owner':owner,'exe':str(exe)}),flush=True)
env=dict(os.environ);env['GDK_BACKEND']='wayland';env.pop('GTK_IM_MODULE',None);result=p/'owned.json';log=(p/'actor.log').open('x');actor=subprocess.Popen(['/usr/bin/python3',str(p/'actor.py'),str(result)],env=env,stdin=subprocess.PIPE,text=True,stdout=log,stderr=subprocess.STDOUT);rows=[];spoof=None;IBus.init();ib=IBus.Bus.new();assert ib.is_connected()
def record(case):
 value=json.loads(rpc(N,P,N+'1','Read')[0]);value['case']=case;value['owned']=json.loads(result.read_text());assert value.get('pid')==actor.pid;rows.append(value);print(json.dumps(value),flush=True);return value
try:
 for _ in range(100):
  if result.exists() and json.loads(result.read_text()).get('active'):break
  time.sleep(.05)
 for field in ['native','ibus','simple','button','native']:
  actor.stdin.write(field+'\n');actor.stdin.flush();time.sleep(.4);record(field)
 spoof=ib.create_input_context('gnome-shell');spoof.set_capabilities(IBus.Capabilite.FOCUS);spoof.focus_in();time.sleep(.4);record('spoof_client_name')
 spoof.focus_out();spoof.destroy();spoof=None
 for field in ['button','native']:
  actor.stdin.write(field+'\n');actor.stdin.flush();time.sleep(.4)
 record('native_restored')
finally:
 if spoof:spoof.focus_out();spoof.destroy()
 actor.stdin.write('quit\n');actor.stdin.flush();print(json.dumps({'actor':actor.pid,'exit':actor.wait(timeout=5)}),flush=True);log.close();(p/'rows.json').write_text(json.dumps(rows,indent=2))
