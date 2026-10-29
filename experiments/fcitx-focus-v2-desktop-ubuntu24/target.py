"""Private fixed-text target; no keyboard simulation or foreign window reads."""
import json, os, sys, time
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, GLib, Gdk
work=Path(sys.argv[1]);work.mkdir(mode=0o700,exist_ok=False)
Gtk.Settings.get_default().set_property('gtk-entry-select-on-focus',False)
window=Gtk.Window(title='InkEcho v2 isolated '+work.name);window.set_default_size(500,150)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);entry=Gtk.Entry();button=Gtk.Button(label='Owned non-text focus')
entry.set_property('im-module','fcitx');box.pack_start(entry,True,True,0);box.pack_start(button,True,True,0);window.add(box)
window.show_all();entry.grab_focus()
context=Gtk.IMMulticontext(); events=[]; expiry=time.monotonic()+240

def save():
    (work/'text.json').write_text(json.dumps({'text':entry.get_text(),'events':events,'at':time.monotonic()}))
def changed(_):
    events.append({'at':time.monotonic(),'text':entry.get_text()});save()
entry.connect('changed',changed)
def capture(name):
    gwindow=window.get_window(); width,height=window.get_size()
    pix=Gdk.pixbuf_get_from_window(gwindow,0,0,width,height)
    if pix:pix.savev(str(work/name),'png',[],[])
def ready():
    capture('ready.png');gwindow=window.get_window()
    xid=gwindow.get_xid() if hasattr(gwindow,'get_xid') else None
    data={'pid':os.getpid(),'start':Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],
          'xid':xid,'display':type(Gdk.Display.get_default()).__name__,'module':entry.get_property('im-module'),'fcitx_module_loaded':'im-fcitx5.so' in Path('/proc/self/maps').read_text(),
          'expires_at':expiry,'public_text_only':True}
    (work/'ready.json').write_text(json.dumps(data,indent=2));save();return False
GLib.timeout_add(200,ready)
def tick():
    for command in ['present','nontext','snapshot']:
        path=work/command
        if path.exists():
            path.unlink()
            if command=='present':window.present()
            elif command=='nontext':button.grab_focus()
            else:capture('snapshot.png')
            (work/(command+'.ack')).write_text(str(time.monotonic()))
    if (work/'stop').exists() or time.monotonic()>expiry:
        save();capture('final.png');Gtk.main_quit();return False
    return True
GLib.timeout_add(20,tick);Gtk.main()
