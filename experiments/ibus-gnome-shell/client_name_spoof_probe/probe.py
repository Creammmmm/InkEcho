"""Verify IBus client-name metadata is self-asserted in a private session."""

import os
import subprocess
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected() and bus.set_global_engine("xkb:us::eng")
rule = (
    "type='method_call',interface='org.freedesktop.IBus.Engine',"
    "member='FocusInId',eavesdrop='true'"
)
monitor = subprocess.Popen(
    ["stdbuf", "-oL", "dbus-monitor", "--address", os.environ["IBUS_ADDRESS"], rule],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
try:
    time.sleep(0.5)
    # This is an ordinary synthetic client, not the shell.
    ctx = bus.create_input_context("gnome-shell")
    ctx.set_capabilities(IBus.Capabilite.FOCUS)
    ctx.focus_in()
    time.sleep(0.5)
    assert bus.current_input_context() == ctx.get_object_path()
    monitor.terminate()
    out, err = monitor.communicate(timeout=3)
    print("engine focus metadata:\n" + out, flush=True)
    print("monitor diagnostic:\n" + err, flush=True)
    assert 'string "gnome-shell"' in out
    assert ctx.get_object_path() in out
finally:
    if monitor.poll() is None:
        monitor.terminate()
        monitor.wait(timeout=3)
