import json,os,time
from pathlib import Path
import gi
gi.require_version("Gtk","3.0")
from gi.repository import Gtk,GLib
root=Path(os.environ["INKECHO_PIPELINE_ROOT"]);windows=[];key_events=[];held=set()
def on_key(_widget,event,pressed):
 code=int(event.hardware_keycode);key_events.append({"pressed":pressed,"code":code,"keyval":int(event.keyval)});held.add(code) if pressed else held.discard(code);return False
def write(name,data):
 p=root/name;t=p.with_suffix(".new");t.write_text(json.dumps(data,ensure_ascii=False));t.replace(p)
def text(v):
 b=v.get_buffer();return b.get_text(b.get_start_iter(),b.get_end_iter(),True)
def create(title):
 w=Gtk.Window(title=title);v=Gtk.TextView();w.add(v);v.connect("key-press-event",lambda w,e:on_key(w,e,True));v.connect("key-release-event",lambda w,e:on_key(w,e,False));w.set_default_size(620,260);w.connect("focus-in-event",lambda *_:(v.grab_focus(),False)[1]);v.get_buffer().connect("changed",lambda *_:sample());windows.append((w,v));w.show_all();w.present();v.grab_focus()
def sample():
 if (root/"switch-now").exists() and len(windows)==1:create("InkEcho candidate new current target")
 w,v=windows[-1];write("target.json",{"text":text(v),"key_events":key_events,"held_generated_keys":sorted(held),"first_text":text(windows[0][1]) if len(windows)>1 else "","window_count":len(windows),"active":w.is_active(),"focused":v.has_focus(),"time":time.monotonic()});return True
create("InkEcho candidate owned protocol target");GLib.timeout_add(25,sample);GLib.timeout_add_seconds(90,Gtk.main_quit);Gtk.main()
