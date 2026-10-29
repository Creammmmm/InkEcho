import gi,json,sys,os
from pathlib import Path
gi.require_version('Gtk','3.0');from gi.repository import Gtk,Gdk,GLib
out=Path(sys.argv[1]);window=Gtk.Window(title='InkEcho owned Fcitx guard acceptance');window.set_default_size(600,180);entry=Gtk.TextView();window.add(entry);preedit='';last=[];owned_events=[];cached_display=None;cached_close=None
def snapshot(*_):
 out.write_text(json.dumps({'pid':os.getpid(),'active':window.is_active(),'focus':entry.is_focus(),'text':entry.get_buffer().get_text(entry.get_buffer().get_start_iter(),entry.get_buffer().get_end_iter(),True),'preedit_length':len(preedit),'key_results':last,'module':entry.get_property('im-module'),'owned_events':owned_events}));return True
def changed(_entry,text):
 global preedit
 preedit=text;snapshot()
entry.connect('preedit-changed',changed);entry.get_buffer().connect('changed',snapshot);window.connect('notify::is-active',snapshot)
def observed(_entry,event):
 owned_events.append({'type':str(event.type),'keyval':event.keyval,'hardware_keycode':event.hardware_keycode});snapshot();return False
entry.connect('key-press-event',observed);entry.connect('key-release-event',observed)
def command(fd,cond):
 global cached_display,cached_close
 line=sys.stdin.readline().strip()
 if not line or line=='quit':Gtk.main_quit();return False
 row=json.loads(line)
 if row['action']=='xkey':
  import ctypes as C,ctypes.util
  from gi.repository import GdkX11
  assert window.is_active() and entry.is_focus()
  x=C.CDLL(ctypes.util.find_library('X11'));t=C.CDLL(ctypes.util.find_library('Xtst'))
  def bind(lib,name,restype,args):
   f=getattr(lib,name);f.restype=restype;f.argtypes=args;return f
  open_display=bind(x,'XOpenDisplay',C.c_void_p,[C.c_char_p]);close=bind(x,'XCloseDisplay',C.c_int,[C.c_void_p]);focus=bind(x,'XGetInputFocus',C.c_int,[C.c_void_p,C.POINTER(C.c_ulong),C.POINTER(C.c_int)]);tree=bind(x,'XQueryTree',C.c_int,[C.c_void_p,C.c_ulong,C.POINTER(C.c_ulong),C.POINTER(C.c_ulong),C.POINTER(C.c_void_p),C.POINTER(C.c_uint)]);free=bind(x,'XFree',C.c_int,[C.c_void_p]);code=bind(x,'XKeysymToKeycode',C.c_ubyte,[C.c_void_p,C.c_ulong]);fake=bind(t,'XTestFakeKeyEvent',C.c_int,[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]);flush=bind(x,'XFlush',C.c_int,[C.c_void_p]);query=bind(x,'XQueryKeymap',C.c_int,[C.c_void_p,C.c_void_p]);sync=bind(x,'XSync',C.c_int,[C.c_void_p,C.c_int]);
  if cached_display is None:cached_display=open_display(None);cached_close=close
  d=cached_display;assert d;pressed=[]
  try:
   focused=C.c_ulong();revert=C.c_int();focus(d,C.byref(focused),C.byref(revert));current=focused.value;owned=GdkX11.X11Window.get_xid(window.get_window())
   for _ in range(12):
    if current==owned:break
    root=C.c_ulong();parent=C.c_ulong();children=C.c_void_p();count=C.c_uint();assert tree(d,current,C.byref(root),C.byref(parent),C.byref(children),C.byref(count));
    if children:free(children)
    current=parent.value
   assert current==owned,('not_owned_focus',current,owned)
   syms=([65507] if row.get('state',0)&4 else [])+([65505] if row.get('state',0)&1 else [])+[row['value']]
   codes=[code(d,v) for v in syms]
   if not all(codes):last.append({'unmapped_owned_test_key':row['value']});snapshot();return True
   statebytes=C.create_string_buffer(32);query(d,statebytes);assert all(not (statebytes.raw[k//8]&(1<<(k%8))) for k in codes)
   for k in codes:assert fake(d,k,1,0);pressed.append(k)
   for k in reversed(pressed):assert fake(d,k,0,0)
   pressed.clear();sync(d,0);last.append({'keyval':row['value'],'state':row.get('state',0),'owned_xid':owned,'xtest':True})
  finally:
   for k in reversed(pressed):fake(d,k,0,0)
   flush(d)
 elif row['action']=='key':
  value=row['value'];state=row.get('state',0);ok,keys=Gdk.Keymap.get_for_display(Gdk.Display.get_default()).get_entries_for_keyval(value);code=keys[0].keycode if ok else 0
  results=[]
  for kind in [Gdk.EventType.KEY_PRESS,Gdk.EventType.KEY_RELEASE]:
   e=Gdk.Event.new(kind);e.window=entry.get_window();e.send_event=True;e.time=Gdk.CURRENT_TIME;e.keyval=value;e.hardware_keycode=code;e.group=0;e.state=Gdk.ModifierType(state);e.set_device(Gdk.Display.get_default().get_default_seat().get_keyboard());results.append(bool(entry.event(e)))
  last.append({'keyval':value,'state':state,'handled':results})
 elif row['action']=='focus':window.present();entry.grab_focus()
 snapshot();return True
window.connect('destroy',Gtk.main_quit);window.show_all();entry.grab_focus();window.present();GLib.io_add_watch(sys.stdin,GLib.IO_IN,command);GLib.timeout_add(100,snapshot);snapshot();Gtk.main();snapshot()
if cached_display:cached_close(cached_display)
