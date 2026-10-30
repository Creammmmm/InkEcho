import ctypes
import os
import sys
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GdkX11', '3.0')
from gi.repository import Gtk, GLib
role=sys.argv[1]
if role == 'B': Gtk.Settings.get_default().set_property('gtk-im-module','simple')
w=Gtk.Window(type=Gtk.WindowType.POPUP); e=Gtk.Entry(); w.add(e);w.show_all();e.grab_focus()
def focus():
    lib=ctypes.CDLL('libX11.so.6');lib.XOpenDisplay.restype=ctypes.c_void_p;lib.XOpenDisplay.argtypes=[ctypes.c_char_p]
    lib.XSetInputFocus.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];lib.XFlush.argtypes=[ctypes.c_void_p]
    d=lib.XOpenDisplay(None);lib.XSetInputFocus(d,w.get_window().get_xid(),1,0);lib.XFlush(d)
    GLib.timeout_add(500, report);return False
def report():
    with open('/tmp/inkecho-'+role+'.txt','w') as f: f.write(f"{int(w.has_toplevel_focus())}|{int(e.has_focus())}|{e.get_text()}|{Gtk.Settings.get_default().get_property('gtk-im-module')}|{w.get_window().get_xid()}")
    return True
GLib.timeout_add(200,focus);Gtk.main()
