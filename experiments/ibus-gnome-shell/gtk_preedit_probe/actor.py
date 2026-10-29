"""Synthetic owned GTK entries in an isolated disposable GNOME session."""

import json
import time

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("IBus", "1.0")
from gi.repository import Gio, GLib, Gtk, IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
engine = bus.get_global_engine().get_name()
assert engine == "libpinyin", engine
connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)


def call(method, sig, args):
    return connection.call_sync(
        "io.github.inkecho.IsolatedPreedit",
        "/io/github/inkecho/IsolatedPreedit",
        "io.github.inkecho.IsolatedPreedit",
        method,
        GLib.Variant(sig, args),
        None,
        Gio.DBusCallFlags.NONE,
        5000,
        None,
    ).unpack()[0]


def pump(seconds=0.6):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


windows = []
for label in ("A", "B"):
    window = Gtk.Window(title=f"InkEcho synthetic preedit {label}")
    entry = Gtk.Entry()
    window.add(entry)
    window.show_all()
    windows.append((window, entry))
pump(1)
a, b = windows
a[0].present()
a[1].grab_focus()
pump(1)
assert a[0].is_active() and a[1].has_focus()
assert call("Key", "(u)", (110,))
assert call("Key", "(u)", (105,))
pump()
before = {"text": a[1].get_text(), "layout": a[1].get_layout().get_text()}
assert before["layout"] != before["text"], before
assert call("Commit", "(s)", ("甲",))
pump()
after = {"text": a[1].get_text(), "layout": a[1].get_layout().get_text()}
assert call("Key", "(u)", (32,))
pump()
after_space = a[1].get_text()
b[0].present()
b[1].grab_focus()
pump(1)
assert b[0].is_active() and b[1].has_focus()
assert call("Commit", "(s)", ("乙",))
pump()
result = {
    "engine_before": engine,
    "engine_after": bus.get_global_engine().get_name(),
    "before": before,
    "after": after,
    "after_space": after_space,
    "a_after_switch": a[1].get_text(),
    "b_after_switch": b[1].get_text(),
}
print(json.dumps(result, ensure_ascii=False), flush=True)
assert result["engine_after"] == engine
assert result["b_after_switch"] == "乙"
