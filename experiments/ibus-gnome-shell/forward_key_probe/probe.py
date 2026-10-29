"""Forward only synthetic keys within an isolated IBus and engine."""

import os
import subprocess
import time
from pathlib import Path

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

assert os.environ["INKECHO_ISOLATED_BUS"] == "1"
assert os.environ["IBUS_ADDRESS"].startswith(f"unix:path={Path.home()}/")
IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
panel = IBus.PanelService.new(bus.get_connection())
assert bus.request_name(IBus.SERVICE_PANEL, 0) == 1
config = subprocess.Popen(["/usr/libexec/ibus-memconf", "--ibus"])
engine = subprocess.Popen(["/usr/libexec/ibus-engine-libpinyin", "--ibus"])


def pump(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


try:
    pump(3)
    assert engine.poll() is None and config.poll() is None
    assert bus.set_global_engine("libpinyin")
    ctx = bus.create_input_context("inkecho-forward-key-test")
    ctx.set_capabilities(IBus.Capabilite.FOCUS | IBus.Capabilite.PREEDIT_TEXT)
    events = []
    ctx.connect("update-preedit-text", lambda *_: events.append("preedit"))
    ctx.connect("commit-text", lambda *_: events.append("commit"))
    ctx.focus_in()
    pump(1)
    assert bus.current_input_context() == ctx.get_object_path()
    print("engine:", bus.get_global_engine().get_name(), flush=True)
    print("before:", events, flush=True)
    initial_count = len(events)
    panel.forward_process_key_event(ord("n"), 0, 0)
    pump(1)
    print("after key:", events, flush=True)
    assert events[initial_count:] == ["preedit"]
finally:
    for process in (engine, config):
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)
