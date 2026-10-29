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

    def save_layout():
        with open("/tmp/inkecho-wayland-focus/" + name + "-layout.txt", "w") as file:
            file.write(widget.get_layout().get_text())
        return True

    GLib.timeout_add(100, save_layout)
    widget.connect(
        "preedit-changed",
        lambda _entry, text: open(
            "/tmp/inkecho-wayland-focus/" + name + "-preedit.txt", "w"
        ).write(str(len(text))),
    )
    widget.connect(
        "changed",
        lambda e: open("/tmp/inkecho-wayland-focus/" + name + ".txt", "w").write(
            e.get_text()
        ),
    )
GLib.timeout_add_seconds(70, Gtk.main_quit)
Gtk.main()
