#!/usr/bin/env python3
"""Owned noneditable/editor windows for current-cursor workflow validation."""

import argparse
import json
import os
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("button", "editor"))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    application = Gtk.Application(
        application_id="io.github.Creammmmm.InkEcho.CurrentCursorFixture",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    def activate(app):
        window = Gtk.ApplicationWindow(application=app)
        window.set_title("InkEcho owned current-cursor validation")
        window.set_default_size(640, 360)
        widget = (
            Gtk.Button(label="Owned noneditable recording target")
            if args.mode == "button"
            else Gtk.TextView()
        )

        def publish():
            text = ""
            if args.mode == "editor":
                buffer = widget.get_buffer()
                text = buffer.get_text(*buffer.get_bounds(), True)
            state = {
                "pid": os.getpid(),
                "mode": args.mode,
                "window_active": window.is_active(),
                "has_focus": widget.has_focus(),
                "sampled_at": time.monotonic(),
                "text": text,
            }
            temporary = args.output.with_suffix(".tmp")
            temporary.write_text(json.dumps(state))
            temporary.replace(args.output)
            return True

        window.add(widget)
        window.show_all()
        widget.grab_focus()
        window.present()
        publish()
        GLib.timeout_add(30, publish)

    application.connect("activate", activate)
    application.run([])


if __name__ == "__main__":
    main()
