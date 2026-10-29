"""One real native Wayland GTK window, two owned IM entries; no foreign focus."""
import json,os,sys,time
from pathlib import Path
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk,GLib,Gdk
work=Path(sys.argv[1]);work.mkdir(mode=0o700,exist_ok=False)
Gtk.Settings.get_default().set_property('gtk-entry-select-on-focus',False)
window=Gtk.Window(title='InkEcho v2 native Wayland isolated');window.set_default_size(500,180)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL);entries={};events=[];expiry=time.monotonic()+240
for name in ['A','B']:
    entry=Gtk.Entry();entry.set_property('im-module','fcitx');entry.set_placeholder_text('Owned '+name)
    box.pack_start(entry,True,True,0);entries[name]=entry
button=Gtk.Button(label='Owned non-text focus');box.pack_start(button,True,True,0);window.add(box)
window.show_all();entries['A'].grab_focus();window.present()
def save():
    (work/'text.json').write_text(json.dumps({'text':{n:e.get_text() for n,e in entries.items()},'events':events,'at':time.monotonic()}))
def changed(entry,name):events.append({'role':name,'at':time.monotonic(),'text':entry.get_text()});save()
for n,e in entries.items():e.connect('changed',changed,n)
def capture(name):
    try:
        import cairo
        w,h=window.get_size();surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,w,h);window.draw(cairo.Context(surface));surface.write_to_png(str(work/name));return 'owned_widget_draw_not_compositor_capture'
    except Exception as error:return type(error).__name__
def ready():
    method=capture('ready.png')
    data={'pid':os.getpid(),'start':Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],
          'display':type(Gdk.Display.get_default()).__name__,'modules':{n:e.get_property('im-module') for n,e in entries.items()},
          'fcitx_module_loaded':'im-fcitx5.so' in Path('/proc/self/maps').read_text(),
          'expires_at':expiry,'public_text_only':True,'screenshot_method':method,'window_active':window.is_active()}
    (work/'ready.json').write_text(json.dumps(data,indent=2));save();return False
GLib.timeout_add(300,ready)
def tick():
    for role in ['A','B','nontext']:
        p=work/('focus-'+role)
        if p.exists():
            p.unlink();(button if role=='nontext' else entries[role]).grab_focus()
            (work/'focus-ack.json').write_text(json.dumps({'role':role,'active':window.is_active(),'has_focus':(button if role=='nontext' else entries[role]).has_focus(),'at':time.monotonic()}))
    if (work/'stop').exists() or time.monotonic()>expiry:
        save();capture('final.png');Gtk.main_quit();return False
    return True
GLib.timeout_add(20,tick);Gtk.main()
