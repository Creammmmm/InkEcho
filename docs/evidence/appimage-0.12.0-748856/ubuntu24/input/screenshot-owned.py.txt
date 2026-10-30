import gi,sys
gi.require_version('Gtk','3.0');gi.require_version('Gdk','3.0');gi.require_version('GdkX11','3.0')
from gi.repository import Gtk,Gdk,GdkX11
Gtk.init([]);d=Gdk.Display.get_default();assert d;r=GdkX11.X11Window.foreign_new_for_display(d,int(sys.argv[1]));assert r;image=Gdk.pixbuf_get_from_window(r,0,0,r.get_width(),r.get_height());assert image;image.savev(sys.argv[2],'png',[],[])
