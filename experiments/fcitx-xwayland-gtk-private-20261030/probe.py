import ctypes
import os
import sys
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GdkX11', '3.0')
from gi.repository import Gtk, Gdk, GdkX11, Gio, GLib
w = Gtk.Window(type=Gtk.WindowType.POPUP)
e = Gtk.Entry()
w.add(e)
w.show_all()
e.grab_focus()
def check():
    xid = w.get_window().get_xid()
    lib = ctypes.CDLL('libX11.so.6')
    lib.XOpenDisplay.restype = ctypes.c_void_p
    lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    lib.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    lib.XFlush.argtypes = [ctypes.c_void_p]
    d = lib.XOpenDisplay(None)
    lib.XSetInputFocus(d, xid, 1, 0)
    lib.XFlush(d)
    GLib.timeout_add(1000, send)
    return False

def send():
    print('FOCUS',w.has_toplevel_focus(),e.has_focus(),e.is_focus(),flush=True)
    if os.environ.get('INKECHO_FAULT_AFTER_FCITX') == '2':
        print('INJECTED_FAILURE_IN_CLIENT', flush=True)
        import time
        time.sleep(3)
        os._exit(43)
    if not w.has_toplevel_focus() or not e.has_focus(): os._exit(1)
    bus=Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def call(method, signature, values, result):
        r=bus.call_sync('org.fcitx.Fcitx5','/inkecho','org.fcitx.Fcitx.InkEcho1',method,GLib.Variant(signature,values),GLib.VariantType.new(result),Gio.DBusCallFlags.NONE,3000,None)
        print(method,r.unpack(),flush=True)
        return r.unpack()[0]
    result=bus.call_sync('org.fcitx.Fcitx5','/inkecho_test','org.fcitx.Fcitx.TestOnly','Preedit',GLib.Variant('(b)',(sys.argv[1]=='active',)),GLib.VariantType.new('(u)'),Gio.DBusCallFlags.NONE,3000,None)
    print('PREEDIT',result.unpack(),flush=True)
    if result.unpack()[0] != (2 if sys.argv[1]=='active' else 1): os._exit(1)
    token='a'*64
    path=os.path.join(os.environ['XDG_RUNTIME_DIR'],'inkecho-fcitx-candidate.cap')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    os.write(fd,token.encode()); os.close(fd)
    if call('Begin3','(su)',(token,3),'(b)') is not True: os._exit(1)
    if call('Commit','(sus)',(token,0,'测'),'(u)') != (5 if sys.argv[1]=='active' else 1): os._exit(1)
    GLib.timeout_add(500,finish)
    return False

def finish():
    print('GTK_RESULT',repr(e.get_text()),'BACKEND',type(Gdk.Display.get_default()).__name__,flush=True)
    if e.get_text() != ('' if sys.argv[1]=='active' else '测'):
        os._exit(1)
    Gtk.main_quit()
    return False
GLib.timeout_add(1000,check)
Gtk.main()
