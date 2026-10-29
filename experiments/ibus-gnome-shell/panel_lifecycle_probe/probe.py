import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
panel = IBus.PanelService.new(bus.get_connection())
events = []


def record(_panel, path, signal):
    events.append((signal, path))
    print("event", signal, path, flush=True)


for sig in ("focus-in", "focus-out", "destroy-context"):
    panel.connect(sig, record, sig)
assert bus.request_name(IBus.SERVICE_PANEL, 0) == 1


def pump():
    end = time.monotonic() + 0.5
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


pump()
a = bus.create_input_context("inkecho-panel-A")
a_path = a.get_object_path()
a.set_capabilities(IBus.Capabilite.FOCUS)
b = bus.create_input_context("inkecho-panel-B")
b.set_capabilities(IBus.Capabilite.FOCUS)
a.focus_in()
pump()
a.focus_out()
b.focus_in()
pump()
b.focus_out()
pump()
a.focus_in()
pump()
a.destroy()
pump()
assert ("focus-in", a_path) in events
assert ("focus-out", a_path) in events
assert ("destroy-context", a_path) in events
print("panel lifecycle observations confirmed", flush=True)
