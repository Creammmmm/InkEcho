import sys,json
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
root=Path(sys.argv[2]);name=sys.argv[1];w=Gtk.Window(title='InkEcho isolated '+name)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);a=Gtk.Entry();b=Gtk.Entry();box.pack_start(a,True,True,0);box.pack_start(b,True,True,0);w.add(box);intra=False

def save():
 (root/(name+'.json')).write_text(json.dumps({'a':a.get_text(),'b':b.get_text(),'focus_a':a.has_focus(),'focus_b':b.has_focus()}))

def insert(*_args):
 global intra
 if intra:intra=False;b.grab_focus();save()
a.connect('insert-text',insert)
for e in [a,b]:e.connect('changed',lambda *_:save())
w.show_all();w.present();a.grab_focus();save()

def command(_s,condition):
 global intra
 if condition & GLib.IOCondition.HUP:Gtk.main_quit();return False
 value=sys.stdin.readline().strip()
 if value=='quit':Gtk.main_quit();return False
 if value=='a':a.grab_focus();a.set_position(-1);a.select_region(-1,-1)
 if value=='intra':a.grab_focus();a.set_position(-1);a.select_region(-1,-1);intra=True
 save();return True
GLib.io_add_watch(sys.stdin,GLib.IOCondition.IN|GLib.IOCondition.HUP,command)
GLib.timeout_add_seconds(120,Gtk.main_quit);Gtk.main()
