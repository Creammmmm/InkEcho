#!/usr/bin/env python3
"""Owned VTE terminal: the child only collects bytes, never starts a shell."""

import json
import os
import signal
import sys
from pathlib import Path


def collect(output):
    import tty

    tty.setraw(0)
    data = b""
    while True:
        output.write_text(
            json.dumps(
                {"raw_hex": data.hex(), "text": data.decode("utf-8", errors="replace")}
            )
        )
        part = os.read(0, 4096)
        if not part:
            return
        data += part


def fixture(output):
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Vte", "2.91")
    from gi.repository import GLib, Gtk, Vte

    child_pid = None
    window = Gtk.Window(title="InkEcho owned raw terminal fixture")
    window.set_default_size(640, 360)
    window.connect("destroy", Gtk.main_quit)
    terminal = Vte.Terminal()

    def spawned(_terminal, pid, error, _data):
        nonlocal child_pid
        if error is not None:
            window.destroy()
        else:
            child_pid = pid

    terminal.spawn_async(
        Vte.PtyFlags.DEFAULT,
        None,
        ["/usr/bin/python3", str(Path(__file__).resolve()), "--child", str(output)],
        [],
        GLib.SpawnFlags.DEFAULT,
        None,
        None,
        -1,
        None,
        spawned,
        None,
    )
    window.add(terminal)
    window.show_all()
    terminal.grab_focus()
    window.present()
    signal.signal(signal.SIGTERM, lambda *_: GLib.idle_add(window.destroy))
    try:
        Gtk.main()
    finally:
        if child_pid is not None:
            try:
                os.kill(child_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


if __name__ == "__main__":
    if sys.argv[1] == "--child":
        collect(Path(sys.argv[2]))
    else:
        fixture(Path(sys.argv[1]))
