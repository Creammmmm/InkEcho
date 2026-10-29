import sys,json
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
p=Path(sys.argv[1]);w=Gtk.Window(title='InkEcho own context research');box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);native=Gtk.Entry();ibus=Gtk.Entry();ibus.set_property('im-module','ibus');simple=Gtk.Entry();simple.set_property('im-module','gtk-im-context-simple');button=Gtk.Button(label='Owned button');fields={'native':native,'ibus':ibus,'simple':simple,'button':button}
for e in fields.values():box.pack_start(e,True,True,0)
w.add(box);w.show_all();w.present();native.grab_focus()
def save():
 q=p.with_suffix('.tmp');q.write_text(json.dumps({'focused':{k:e.has_focus() for k,e in fields.items()},'active':w.is_active()}));q.replace(p)
GLib.timeout_add(50,lambda:(save(),True)[1]);save()
def cmd(_s,c):
 if c&GLib.IOCondition.HUP:Gtk.main_quit();return False
 s=sys.stdin.readline().strip()
 if s=='quit':Gtk.main_quit();return False
 if s in fields:fields[s].grab_focus()
 return True
GLib.io_add_watch(sys.stdin,GLib.IOCondition.IN|GLib.IOCondition.HUP,cmd);GLib.timeout_add_seconds(60,Gtk.main_quit);Gtk.main()
