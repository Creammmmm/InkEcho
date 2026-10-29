import json,os,time
from pathlib import Path
import gi
gi.require_version("Gtk","3.0")
from gi.repository import Gtk,GLib
root=Path(os.environ["INKECHO_PIPELINE_ROOT"])
w=Gtk.Window(title="InkEcho candidate owned protocol target");v=Gtk.TextView();w.add(v);w.set_default_size(620,260)
def write(name,data):
 p=root/name;t=p.with_suffix(".new");t.write_text(json.dumps(data,ensure_ascii=False));t.replace(p)
def sample():
 b=v.get_buffer();write("target.json",{"text":b.get_text(b.get_start_iter(),b.get_end_iter(),True),"active":w.is_active(),"focused":v.has_focus(),"time":time.monotonic()});return True
w.connect("focus-in-event",lambda *_:(v.grab_focus(),False)[1]);v.get_buffer().connect("changed",lambda *_:sample());w.show_all();w.present();v.grab_focus();GLib.timeout_add(25,sample);GLib.timeout_add_seconds(90,Gtk.main_quit);Gtk.main()
