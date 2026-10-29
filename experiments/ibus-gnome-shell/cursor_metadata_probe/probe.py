"""Probe whether panel cursor metadata distinguishes fake focus, privately."""

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
panel.connect("focus-in", lambda _panel, path: events.append(("focus", path)))
panel.connect(
    "set-cursor-location",
    lambda _panel, x, y, w, h: events.append(("cursor", (x, y, w, h))),
)


def pump():
    end = time.monotonic() + 0.4
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


pump()
fake = bus.current_input_context()
client = bus.create_input_context("inkecho-isolated-cursor-metadata")
client.set_capabilities(IBus.Capabilite.FOCUS)
client.focus_in()
pump()
assert bus.current_input_context() == client.get_object_path()
client.set_cursor_location(11, 22, 3, 4)
pump()
print("real events", events, flush=True)
assert ("cursor", (11, 22, 3, 4)) in events
before = len(events)
client.focus_out()
pump()
assert bus.current_input_context() == fake
print("events on fake focus", events[before:], flush=True)
assert ("focus", fake) in events[before:]
assert not any(event[0] == "cursor" for event in events[before:])
print("previous cursor position remains last observed metadata", flush=True)
before = len(events)
client.set_cursor_location(31, 42, 5, 6)
pump()
assert bus.current_input_context() == fake
print("unfocused client cursor update", events[before:], flush=True)
