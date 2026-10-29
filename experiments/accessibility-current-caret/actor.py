import os,sys,json
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
root=Path(sys.argv[1]);w=Gtk.Window(title='InkEcho isolated live caret')
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);a=Gtk.Entry();b=Gtk.Entry();button=Gtk.Button(label='No text')
for widget in [a,b,button]:box.pack_start(widget,True,True,0)
w.add(box);race=False

def save():
 (root/'owned-state.json').write_text(json.dumps({'a':a.get_text(),'b':b.get_text(),'focus_a':a.has_focus(),'focus_b':b.has_focus(),'focus_button':button.has_focus()}))

def insert(_e,*_args):
 global race
 if race:
  race=False;b.grab_focus();save()
a.connect('insert-text',insert)
for widget in [a,b]:widget.connect('changed',lambda *_:save())
for widget in [a,b,button]:widget.connect('focus-in-event',lambda *_:GLib.idle_add(lambda:save()))
w.show_all();w.present();a.grab_focus();save()

def command(_s,condition):
 global race
 if condition & GLib.IOCondition.HUP:Gtk.main_quit();return False
 value=sys.stdin.readline().strip()
 if value=='quit':Gtk.main_quit();return False
 if value=='a':a.grab_focus();a.select_region(0,0)
 elif value=='b':b.grab_focus();b.select_region(0,0)
 elif value=='button':button.grab_focus()
 elif value=='selection':a.grab_focus();a.select_region(0,1)
 elif value=='race':a.grab_focus();a.select_region(0,0);race=True
 save();return True
GLib.io_add_watch(sys.stdin,GLib.IOCondition.IN|GLib.IOCondition.HUP,command)
GLib.timeout_add_seconds(90,Gtk.main_quit);Gtk.main()
