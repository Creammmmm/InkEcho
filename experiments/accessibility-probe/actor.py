"""Owned synthetic GTK entry and button for an isolated desktop only."""

import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

root = Path("/tmp/inkecho-accessibility-probe")
window = Gtk.Window(title="InkEcho isolated accessibility")
layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
entry = Gtk.Entry()
entry.get_accessible().set_name("InkEcho owned entry")
button = Gtk.Button(label="InkEcho owned button")
layout.pack_start(entry, True, True, 0)
layout.pack_start(button, True, True, 0)
window.add(layout)
window.show_all()
window.present()
entry.grab_focus()
entry.connect(
    "changed", lambda value: (root / "own-entry.txt").write_text(value.get_text())
)
(root / "actor-pid").write_text(str(os.getpid()))


def command(_source, condition):
    if condition & GLib.IOCondition.HUP:
        Gtk.main_quit()
        return False
    value = sys.stdin.readline().strip()
    if value == "entry":
        window.present()
        entry.grab_focus()
    elif value == "selection":
        window.present()
        entry.set_text("ABC")
        entry.grab_focus()
        entry.select_region(0, 3)
    elif value == "button":
        window.present()
        button.grab_focus()
    return True


GLib.io_add_watch(sys.stdin, GLib.IOCondition.IN | GLib.IOCondition.HUP, command)
GLib.timeout_add_seconds(60, Gtk.main_quit)
Gtk.main()
