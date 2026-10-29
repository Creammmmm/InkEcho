import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

name = sys.argv[1]
window = Gtk.Window(title="InkEcho isolated " + name)
widget = Gtk.Button(label="No text") if name == "button" else Gtk.Entry()
window.add(widget)
window.show_all()
widget.grab_focus()
if name != "button":
    widget.connect(
        "changed",
        lambda e: open("/tmp/inkecho-wayland-focus/" + name + ".txt", "w").write(
            e.get_text()
        ),
    )
GLib.timeout_add_seconds(70, Gtk.main_quit)
Gtk.main()
