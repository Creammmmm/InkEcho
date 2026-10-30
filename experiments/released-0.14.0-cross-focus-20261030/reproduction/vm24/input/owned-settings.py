from pathlib import Path
import gi,os,json,sys,subprocess
from gi.repository import Gio,GLib
os.environ.update(DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000')
s=Gio.Settings.new('org.gnome.shell');keys=['enabled-extensions','disabled-extensions','disable-user-extensions'];u='inkecho-ibus-owned-v5-prototype@local.invalid';before=Path('/mnt/output/extension-settings-before.json');action=sys.argv[1]
def values():return{k:s.get_value(k).unpack()for k in keys}
if action=='save':
 assert not before.exists();before.write_text(json.dumps(values(),indent=2));print(before.read_text())
elif action=='disabled':
 subprocess.run(['gnome-extensions','disable',u],check=True)
elif action=='enabled':
 assert Path('/home/inkecho/.local/share/gnome-shell/extensions',u,'extension.js').is_file()
 s.set_boolean('disable-user-extensions',False);s.set_strv('disabled-extensions',[x for x in s.get_strv('disabled-extensions')if x!=u]);Gio.Settings.sync();subprocess.run(['gnome-extensions','enable',u],check=True)
elif action=='restore':
 b=json.loads(before.read_text())
 for k,v in b.items():s.set_value(k,GLib.Variant('b'if isinstance(v,bool)else'as',v))
 Gio.Settings.sync();assert values()==b
else:raise ValueError(action)
print(json.dumps({'action':action,'values':values(),'info':subprocess.run(['gnome-extensions','info',u],capture_output=True,text=True).stdout},indent=2))
