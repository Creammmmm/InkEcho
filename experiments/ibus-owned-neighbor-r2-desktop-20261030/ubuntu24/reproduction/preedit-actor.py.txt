from pathlib import Path
import os,json,sys,gi

gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib,Gdk
p=Path(sys.argv[1]);w=Gtk.Window(title='InkEcho owned batch preedit acceptance');e=Gtk.Entry();w.add(e);pre=[''];e.connect('preedit-changed',lambda _e,s:pre.__setitem__(0,s));w.connect('destroy',Gtk.main_quit);w.show_all();e.grab_focus();w.present()
def save():
 p.write_text(json.dumps({'pid':os.getpid(),'display_type':type(Gdk.Display.get_default()).__name__,'active':w.is_active(),'focus':e.has_focus(),'text':e.get_text(),'preedit':pre[0]}));return True
GLib.timeout_add(30,save);Gtk.main()
