"""Observe capability metadata from one synthetic isolated GTK entry."""

import os
import subprocess
import time
from pathlib import Path

import gi

gi.require_version("IBus", "1.0")
from gi.repository import IBus  # noqa: E402

runtime = Path(os.environ["XDG_RUNTIME_DIR"])
assert str(runtime).startswith("/tmp/inkecho-ibus-lab.")
assert os.environ["IBUS_ADDRESS"].startswith(f"unix:path={Path.home()}/")
display = subprocess.Popen(
    ["broadwayd", "--unixsocket", str(runtime / "broadway5.socket"), ":5"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
monitor = actor = None
try:
    time.sleep(0.5)
    assert display.poll() is None
    rule = (
        "type='method_call',interface='org.freedesktop.IBus.InputContext',"
        "member='SetCapabilities',eavesdrop='true'"
    )
    monitor = subprocess.Popen(
        [
            "stdbuf",
            "-oL",
            "dbus-monitor",
            "--address",
            os.environ["IBUS_ADDRESS"],
            rule,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(0.5)
    env = os.environ.copy()
    env.update(GDK_BACKEND="broadway", BROADWAY_DISPLAY=":5", GTK_IM_MODULE="ibus")
    actor = subprocess.Popen(
        ["/usr/bin/python3", str(Path(__file__).with_name("actor.py"))],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = actor.communicate(timeout=8)
    print("actor exit:", actor.returncode, "diagnostic:", err, flush=True)
    assert actor.returncode == 0
    IBus.init()
    bus = IBus.Bus.new()
    assert bus.is_connected()
    fake = bus.create_input_context("gtk3-im:inkecho-capability-test")
    fake.set_capabilities(41)
    fake.focus_in()
    time.sleep(0.4)
    assert bus.current_input_context() == fake.get_object_path()
    monitor.terminate()
    out, err = monitor.communicate(timeout=3)
    print("capability metadata:\n" + out, flush=True)
    print("monitor diagnostic:\n" + err, flush=True)
    assert out.count("member=SetCapabilities") == 2
    assert out.count("uint32 41") == 2
    print("widget and no-widget context advertised identical flags", flush=True)
finally:
    for process in (actor, monitor, display):
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=3)
