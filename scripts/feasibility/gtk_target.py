#!/usr/bin/env python3
"""Disposable GTK editor/terminal; never uses the clipboard or a real shell."""

import argparse
import json
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("kind", choices=("editor", "terminal"))
parser.add_argument("output", type=Path)
args = parser.parse_args()
window = Gtk.Window(title=f"InkEcho isolated {args.kind}")
window.set_default_size(640, 360)
window.connect("destroy", Gtk.main_quit)

if args.kind == "editor":
    widget = Gtk.TextView()
    buffer = widget.get_buffer()

    def changed(*_):
        start, end = buffer.get_bounds()
        args.output.write_text(
            json.dumps(buffer.get_text(start, end, True), ensure_ascii=False)
        )

    buffer.connect("changed", changed)
    changed()
else:
    gi.require_version("Vte", "2.91")
    from gi.repository import Vte

    widget = Vte.Terminal()
    # The child only captures bytes; injected newlines can never execute commands.
    child = (
        "import os,tty,json; from pathlib import Path; "
        "tty.setraw(0); data=b''; p=Path(__import__('sys').argv[1]); "
        'exec("while True:\\n data+=os.read(0,4096)\\n '
        "p.write_text(json.dumps(data.decode('utf-8',errors='replace'),ensure_ascii=False))\")"
    )
    widget.spawn_async(
        Vte.PtyFlags.DEFAULT,
        None,
        ["/usr/bin/python3", "-c", child, str(args.output)],
        [],
        GLib.SpawnFlags.DEFAULT,
        None,
        None,
        -1,
        None,
        None,
        None,
    )
window.add(widget)
window.show_all()
widget.grab_focus()
Gtk.main()
