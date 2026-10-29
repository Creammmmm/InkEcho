import sys
from pathlib import Path
import gi

gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib
name=sys.argv[1];root=Path(sys.argv[2])
win=Gtk.Window(title='InkEcho isolated '+name)
field=Gtk.Button(label='No text focus') if name=='button' else Gtk.Entry()
win.add(field);win.show_all();field.grab_focus()
if name!='button':
    field.connect('changed',lambda e:(root/(name+'.txt')).write_text(e.get_text()))
    field.connect('preedit-changed',lambda e,s:(root/(name+'-preedit.json')).write_text(__import__('json').dumps({'nonempty':bool(s)})))
GLib.timeout_add_seconds(180,Gtk.main_quit)
Gtk.main()
