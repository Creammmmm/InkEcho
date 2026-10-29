"""Controlled cross-focus panel commit on private IBus with synthetic text."""

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


def context(name):
    instance = bus.create_input_context(name)
    instance.set_capabilities(IBus.Capabilite.FOCUS)
    return instance


pump()
fake = bus.current_input_context()
a = context("inkecho-panel-commit-A")
b = context("inkecho-panel-commit-B")
received = []
samples = [IBus.Text.new_from_string(value) for value in ("甲", "乙", "丙")]
a.connect("commit-text", lambda _ctx, _text: received.append("A"))
b.connect("commit-text", lambda _ctx, _text: received.append("B"))
a.focus_in()
pump()
assert bus.current_input_context() == a.get_object_path()
panel.commit_text(samples[0])
pump()
print("focused A receivers", received, flush=True)
assert received == ["A"]
a.focus_out()
b.focus_in()
pump()
assert bus.current_input_context() == b.get_object_path()
panel.commit_text(samples[1])
pump()
print("focused B receivers", received, flush=True)
assert received == ["A", "B"]
b.focus_out()
pump()
assert bus.current_input_context() == fake
panel.commit_text(samples[2])
pump()
print("fake focus receivers", received, flush=True)
assert received == ["A", "B"]
