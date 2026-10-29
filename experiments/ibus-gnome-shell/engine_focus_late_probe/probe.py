"""Late observation of synthetic engine focus IDs in an isolated IBus."""

import os
import subprocess
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected() and bus.set_global_engine("xkb:us::eng")
ctx = bus.create_input_context("inkecho-late-focus-id")
ctx.set_capabilities(IBus.Capabilite.FOCUS)
ctx.focus_in()
time.sleep(0.4)
assert bus.current_input_context() == ctx.get_object_path()
rules = [
    "type='method_call',interface='org.freedesktop.IBus.Engine',"
    f"member='{name}',eavesdrop='true'"
    for name in ("FocusInId", "FocusOutId")
]


def start_monitor():
    return subprocess.Popen(
        [
            "stdbuf",
            "-oL",
            "dbus-monitor",
            "--address",
            os.environ["IBUS_ADDRESS"],
            *rules,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def stop_monitor(monitor):
    monitor.terminate()
    return monitor.communicate(timeout=2)


monitor = start_monitor()
time.sleep(0.7)
out, error = stop_monitor(monitor)
print("after late subscription, before focus change:", repr(out), flush=True)
print("monitor diagnostic:", error.strip(), flush=True)
assert "FocusInId" not in out
monitor = start_monitor()
try:
    time.sleep(0.4)
    ctx.focus_out()
    time.sleep(0.4)
    ctx.focus_in()
    time.sleep(0.4)
    out, error = stop_monitor(monitor)
    print("after focus changes:\n" + out, flush=True)
    assert "FocusInId" in out and "inkecho-late-focus-id" in out
finally:
    if monitor.poll() is None:
        monitor.terminate()
        monitor.wait(timeout=2)
