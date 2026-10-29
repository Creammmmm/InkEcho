"""Owned GTK test target; writes only its fixed synthetic test contents."""

import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

name, output = sys.argv[1:]
window = Gtk.Window(title="InkEcho isolated " + name)
entry = Gtk.Entry()
window.add(entry)
window.show_all()
entry.grab_focus()
context = Gtk.IMMulticontext()
with open(output + ".module", "w", encoding="utf8") as file:
    file.write(str(context.get_context_id()))


def changed(_entry):
    with open(output, "w", encoding="utf8") as file:
        file.write(entry.get_text())


entry.connect("changed", changed)
GLib.timeout_add_seconds(40, Gtk.main_quit)
Gtk.main()
