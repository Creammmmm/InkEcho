"""Diagnose libpinyin in an isolated IBus without desktop or user text."""

import os
import subprocess
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
config = subprocess.Popen(
    ["/usr/libexec/ibus-memconf", "--ibus"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
time.sleep(1)
print("private config startup exit:", config.poll(), flush=True)
engine = subprocess.Popen(
    ["/usr/libexec/ibus-engine-libpinyin", "--ibus"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
m = None
try:
    time.sleep(2)
    print("engine startup exit:", engine.poll(), flush=True)
    if engine.poll() is None:
        selected = bus.set_global_engine("libpinyin")
        print("private select:", selected, flush=True)
        assert selected
        ctx = bus.create_input_context("inkecho-private-libpinyin")
        ctx.set_capabilities(IBus.Capabilite.FOCUS)
        ctx.focus_in()
        time.sleep(0.4)
        assert bus.current_input_context() == ctx.get_object_path()
        rules = [
            "type='method_call',interface='org.freedesktop.IBus.Engine',"
            f"member='{name}',eavesdrop='true'"
            for name in ("FocusIn", "FocusInId", "FocusOutId")
        ]

        def monitor():
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

        m = monitor()
        time.sleep(0.7)
        m.terminate()
        before, monitor_error = m.communicate(timeout=3)
        print("before focus change:", repr(before), flush=True)
        assert not before.strip()
        print("monitor diagnostic:", monitor_error.strip(), flush=True)
        m = monitor()
        time.sleep(0.4)
        ctx.focus_out()
        time.sleep(0.4)
        print("fake current:", bus.current_input_context(), flush=True)
        ctx.focus_in()
        time.sleep(0.4)
        print("real current:", bus.current_input_context(), flush=True)
        m.terminate()
        after, _ = m.communicate(timeout=3)
        print("focus events:\n" + after, flush=True)
        assert after.count("member=FocusIn\n") == 2
        assert "member=FocusInId" not in after
        print("engine still:", bus.get_global_engine().get_name(), flush=True)
finally:
    if m is not None and m.poll() is None:
        m.terminate()
        m.wait(timeout=3)
    if engine.poll() is None:
        engine.terminate()
    out, err = engine.communicate(timeout=5)
    print("stdout:", out, flush=True)
    print("stderr:", err, flush=True)
    if config.poll() is None:
        config.terminate()
    config_out, config_err = config.communicate(timeout=5)
    print("config stdout:", config_out, flush=True)
    print("config stderr:", config_err, flush=True)
