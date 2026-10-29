"""Observe late FocusOut from an old private IBus context, without text."""

import os
import subprocess
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
panel = IBus.PanelService.new(bus.get_connection())
assert bus.request_name(IBus.SERVICE_PANEL, 0) == 1
events = []
panel.connect("focus-in", lambda _panel, path: events.append(("in", path)))
panel.connect("focus-out", lambda _panel, path: events.append(("out", path)))


def pump():
    end = time.monotonic() + 0.4
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


def context(name):
    ctx = bus.create_input_context(name)
    ctx.set_capabilities(IBus.Capabilite.FOCUS)
    return ctx


pump()
fake = bus.current_input_context()
a = context("inkecho-old")
b = context("inkecho-new")
a.focus_in()
pump()
print("after A in", bus.current_input_context(), flush=True)
b.focus_in()
pump()
print("after B in", bus.current_input_context(), flush=True)
assert bus.current_input_context() == b.get_object_path()
rule = (
    "type='method_call',interface='org.freedesktop.IBus.InputContext',"
    "member='FocusOut',eavesdrop='true'"
)
monitor = subprocess.Popen(
    ["stdbuf", "-oL", "dbus-monitor", "--address", os.environ["IBUS_ADDRESS"], rule],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
time.sleep(0.4)
before = len(events)
a.focus_out()
pump()
current = bus.current_input_context()
print("after late A out", current, "fake", fake, flush=True)
print("panel events", events[before:], flush=True)
print("new B remains current", current == b.get_object_path(), flush=True)
monitor.terminate()
out, err = monitor.communicate(timeout=3)
print("client method monitor:\n" + out, flush=True)
print("monitor diagnostic:\n" + err, flush=True)
assert a.get_object_path() in out and "member=FocusOut" in out
assert current == b.get_object_path()
