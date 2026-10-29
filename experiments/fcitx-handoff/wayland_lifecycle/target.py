from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

root = Path("/tmp/wayland-lifecycle")
window = Gtk.Window(title="InkEcho isolated lifecycle")
entry = Gtk.Entry()
window.add(entry)


def changed(widget):
    (root / "text").write_text(widget.get_text())


def focused(widget, event):
    (root / "focused").write_text("yes")
    return False


entry.connect("changed", changed)
entry.connect("focus-in-event", focused)
window.show_all()
window.present()
entry.grab_focus()
GLib.timeout_add_seconds(45, Gtk.main_quit)
Gtk.main()
