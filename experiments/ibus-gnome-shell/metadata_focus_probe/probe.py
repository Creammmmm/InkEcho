import os
import subprocess
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
a = bus.create_input_context("inkecho-isolated-A")
b = bus.create_input_context("inkecho-isolated-B")
assert a and b
for ctx in (a, b):
    ctx.set_capabilities(IBus.Capabilite.FOCUS)
a.focus_in()
time.sleep(0.3)
print("before_monitor", bus.current_input_context(), flush=True)
rules = [
    "type='method_call',interface='org.freedesktop.IBus.InputContext',member='FocusIn',eavesdrop='true'",
    "type='method_call',interface='org.freedesktop.IBus.InputContext',member='FocusOut',eavesdrop='true'",
]
mon = subprocess.Popen(
    ["stdbuf", "-oL", "dbus-monitor", "--address", os.environ["IBUS_ADDRESS"], *rules],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
time.sleep(0.4)
print("already_active_no_new_event", bus.current_input_context(), flush=True)
a.focus_out()
b.focus_in()
time.sleep(0.4)
print("second_context", bus.current_input_context(), flush=True)
b.focus_out()
time.sleep(0.4)
print("fake_context", bus.current_input_context(), flush=True)
a.focus_in()
time.sleep(0.4)
print("refocus_first_context", bus.current_input_context(), flush=True)
a.destroy()
time.sleep(0.4)
print("destroyed_context", bus.current_input_context(), flush=True)
mon.terminate()
out, err = mon.communicate(timeout=2)
print("monitor_stdout:")
print(out)
print("monitor_stderr:")
print(err)
