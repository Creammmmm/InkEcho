import os,subprocess,gi,sys
from pathlib import Path
os.environ.update(DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1000/bus',XDG_RUNTIME_DIR='/run/user/1000')
for s in subprocess.check_output(['systemctl','--user','show-environment'],text=True).splitlines():
 k,_,v=s.partition('=')
 if k in {'DISPLAY','XAUTHORITY','WAYLAND_DISPLAY','XDG_SESSION_TYPE','XDG_CURRENT_DESKTOP'}:os.environ[k]=v
gi.require_version('Gtk','3.0');gi.require_version('Gdk','3.0')
from gi.repository import Gtk,Gdk
Gtk.init([]);w=Gdk.get_default_root_window();assert w;p=Gdk.pixbuf_get_from_window(w,0,0,w.get_width(),w.get_height());assert p;p.savev(sys.argv[1] if len(sys.argv)>1 else '/mnt/output/browser-xorg/isolated-desktop-state.png','png',[],[])
