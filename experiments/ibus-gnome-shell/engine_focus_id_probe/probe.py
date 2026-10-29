"""Inspect synthetic focus-ID messages on two isolated IBus engines."""

import os
import subprocess
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
rules = [
    "type='method_call',interface='org.freedesktop.IBus.Engine',"
    f"member='{member}',eavesdrop='true'"
    for member in ("FocusIn", "FocusInId", "FocusOutId")
]
monitor = subprocess.Popen(
    ["stdbuf", "-oL", "dbus-monitor", "--address", os.environ["IBUS_ADDRESS"], *rules],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
try:
    time.sleep(0.5)
    engines = os.environ.get("INKECHO_TEST_ENGINES", "xkb:us::eng,libpinyin")
    for engine in engines.split(","):
        ok = bus.set_global_engine(engine)
        print("selected in isolated daemon", engine, ok, flush=True)
        if not ok:
            continue
        ctx = bus.create_input_context("inkecho-focus-id-" + engine)
        ctx.set_capabilities(IBus.Capabilite.FOCUS)
        ctx.focus_in()
        time.sleep(0.5)
        assert bus.current_input_context() == ctx.get_object_path()
        print("focused owned context", engine, ctx.get_object_path(), flush=True)
        print("isolated bus names", bus.list_names(), flush=True)
        ctx.focus_out()
        time.sleep(0.5)
        ctx.destroy()
    monitor.terminate()
    out, err = monitor.communicate(timeout=2)
    print("selected focus messages:\n" + out, flush=True)
    print("monitor diagnostic:\n" + err, flush=True)
finally:
    if monitor.poll() is None:
        monitor.terminate()
        monitor.wait(timeout=2)
