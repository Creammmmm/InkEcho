"""Can real FocusInId certify an editor? Only test synthetic IBus clients."""

import os
import subprocess
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected() and bus.set_global_engine("xkb:us::eng")
panel = IBus.PanelService.new(bus.get_connection())
assert bus.request_name(IBus.SERVICE_PANEL, 0) == 1
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


def pump():
    end = time.monotonic() + 0.4
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


try:
    pump()
    disconnected = bus.create_input_context("inkecho-owned-without-widget")
    disconnected.set_capabilities(IBus.Capabilite.FOCUS)
    disconnected.focus_in()
    pump()
    assert bus.current_input_context() == disconnected.get_object_path()
    panel.commit_text(IBus.Text.new_from_string("甲"))
    pump()  # This owned proxy has no editor or commit-text handler.

    control = bus.create_input_context("inkecho-owned-listener")
    control.set_capabilities(IBus.Capabilite.FOCUS)
    received = []
    control.connect("commit-text", lambda _ctx, _text: received.append(True))
    control.focus_in()
    pump()
    panel.commit_text(IBus.Text.new_from_string("乙"))
    pump()
    assert received == [True]
    monitor.terminate()
    out, err = monitor.communicate(timeout=3)
    print("focus-ID metadata:\n" + out, flush=True)
    print("monitor diagnostic:\n" + err, flush=True)
    print("control received synthetic signal:", len(received), flush=True)
    assert "inkecho-owned-without-widget" in out
    assert "inkecho-owned-listener" in out
finally:
    if monitor.poll() is None:
        monitor.terminate()
        monitor.wait(timeout=3)
