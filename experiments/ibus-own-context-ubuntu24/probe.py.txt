"""Focus behavior for a second owned IBus context; synthetic text only."""

import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
panel = IBus.PanelService.new(bus.get_connection())
assert bus.request_name(IBus.SERVICE_PANEL, 0) == 1


def pump():
    end = time.monotonic() + 0.4
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


def context(name, key):
    ctx = bus.create_input_context(name)
    ctx.set_capabilities(IBus.Capabilite.FOCUS)
    ctx.connect("commit-text", lambda _ctx, _text: received.append(key))
    return ctx


received = []
target = context("inkecho-owned-target-proxy", "target")
target.focus_in()
pump()
assert bus.current_input_context() == target.get_object_path()
bridge = context("inkecho-owned-bridge-proxy", "bridge")
pump()
assert bus.current_input_context() == target.get_object_path()
panel.commit_text(IBus.Text.new_from_string("甲"))
pump()
print("unfocused bridge receives", received, flush=True)
assert received == ["target"]
bridge.focus_in()
pump()
assert bus.current_input_context() == bridge.get_object_path()
panel.commit_text(IBus.Text.new_from_string("乙"))
pump()
print("focused bridge receives", received, flush=True)
assert received == ["target", "bridge"]
