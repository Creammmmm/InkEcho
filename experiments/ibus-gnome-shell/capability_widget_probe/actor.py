"""Own GTK window and entry, with an isolated Broadway display."""

import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

GLib.set_prgname("inkecho-capability-test")
assert Gtk.init_check()[0]
window = Gtk.Window()
entry = Gtk.Entry()
window.add(entry)
window.show_all()
entry.grab_focus()
window.present()
end = time.monotonic() + 4
while time.monotonic() < end:
    while GLib.MainContext.default().pending():
        GLib.MainContext.default().iteration(False)
    time.sleep(0.01)
