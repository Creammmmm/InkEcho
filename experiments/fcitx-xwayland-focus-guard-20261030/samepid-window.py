import ctypes
import gi
gi.require_version('Gtk','3.0')
gi.require_version('GdkX11','3.0')
from gi.repository import Gtk,GLib
windows=[]
for title in ('A','B'):
 w=Gtk.Window(type=Gtk.WindowType.POPUP);e=Gtk.Entry();w.add(e);w.show_all();windows.append((w,e))
windows[0][1].grab_focus()
def start():
 lib=ctypes.CDLL('libX11.so.6');lib.XOpenDisplay.restype=ctypes.c_void_p;lib.XOpenDisplay.argtypes=[ctypes.c_char_p];lib.XSetInputFocus.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];lib.XFlush.argtypes=[ctypes.c_void_p]
 d=lib.XOpenDisplay(None);lib.XSetInputFocus(d,windows[0][0].get_window().get_xid(),1,0);lib.XFlush(d);GLib.timeout_add(500,report);return False
def report():
 with open('/tmp/samepid-state.txt','w') as f:f.write('|'.join([str(w.get_window().get_xid()) for w,e in windows]+[str(int(windows[0][0].has_toplevel_focus())),str(int(windows[0][1].has_focus()))]))
 return True
GLib.timeout_add(200,start);Gtk.main()
