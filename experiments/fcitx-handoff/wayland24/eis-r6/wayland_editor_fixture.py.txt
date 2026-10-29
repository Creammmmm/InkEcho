#!/usr/bin/env python3
"""Owned GTK application for the private native Wayland input probe."""

import json
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

events = Path(sys.argv[2]) if len(sys.argv) > 2 else None
state = Path(sys.argv[3]) if len(sys.argv) > 3 else None
output = None if sys.argv[1] == "-" else Path(sys.argv[1])
application = Gtk.Application(
    application_id="io.github.Creammmmm.InkEcho.InputFixture",
    flags=Gio.ApplicationFlags.NON_UNIQUE,
)


def activate(app):
    window = Gtk.ApplicationWindow(application=app)
    window.set_title("InkEcho owned Wayland input fixture")
    window.set_default_size(640, 360)
    widget = Gtk.TextView()
    buffer = widget.get_buffer()

    def changed(*_):
        start, end = buffer.get_bounds()
        if output is not None:
            output.write_text(json.dumps(buffer.get_text(start, end, True)))

    def key_event(_widget, event):
        if events is not None:
            with events.open("a") as stream:
                stream.write(
                    json.dumps(
                        {
                            "keyval": event.keyval,
                            "hardware_keycode": event.hardware_keycode,
                            "synthetic": bool(event.send_event),
                        }
                    )
                    + "\n"
                )
        return False

    widget.connect("key-press-event", key_event)
    buffer.connect("changed", changed)
    changed()
    window.add(widget)
    window.show_all()
    widget.grab_focus()
    window.present()
    if state is not None:

        def update_state():
            temporary = state.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    {
                        "active": window.is_active(),
                        "focused": widget.has_focus(),
                    }
                )
            )
            temporary.replace(state)
            return True

        GLib.timeout_add(50, update_state)


application.connect("activate", activate)
application.run(sys.argv[:1])
