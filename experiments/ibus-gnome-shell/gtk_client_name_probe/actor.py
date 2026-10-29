"""Start an isolated GTK IBus IM context; no user or synthetic text."""

import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

GLib.set_prgname("inkecho-synthetic-same-name")
assert Gtk.init_check()[0]
context = Gtk.IMMulticontext.new()
context.focus_in()
end = time.monotonic() + 3
while time.monotonic() < end:
    while GLib.MainContext.default().pending():
        GLib.MainContext.default().iteration(False)
    time.sleep(0.01)
