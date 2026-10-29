"""Test private IBus panel submission while its synthetic client is paused."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

marker_dir = Path(os.environ["HOME"])
assert os.environ["INKECHO_ISOLATED_BUS"] == "1"
assert os.environ["IBUS_ADDRESS"].startswith(f"unix:path={marker_dir}/")
IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()

if len(sys.argv) > 1:
    ctx = bus.create_input_context("inkecho-paused-synthetic-client")
    ctx.set_capabilities(IBus.Capabilite.FOCUS)
    ctx.connect("commit-text", lambda _ctx, _text: (marker_dir / "received").touch())
    ctx.focus_in()
    (marker_dir / "ready").write_text(ctx.get_object_path())
    GLib.MainLoop().run()
    sys.exit(0)

panel = IBus.PanelService.new(bus.get_connection())
assert bus.request_name(IBus.SERVICE_PANEL, 0) == 1
child = subprocess.Popen([sys.executable, __file__, "client"])


def wait_until(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if predicate():
            return True
        time.sleep(0.01)
    return False


try:
    assert wait_until(lambda: (marker_dir / "ready").exists())
    path = (marker_dir / "ready").read_text()
    assert wait_until(lambda: bus.current_input_context() == path)
    os.kill(child.pid, signal.SIGSTOP)
    assert wait_until(
        lambda: (
            Path(f"/proc/{child.pid}/status")
            .read_text()
            .split("State:")[1]
            .lstrip()
            .startswith("T")
        )
    )
    start = time.monotonic()
    result = panel.commit_text(IBus.Text.new_from_string("甲"))
    bus.get_connection().flush_sync(None)
    elapsed = time.monotonic() - start
    assert not wait_until(lambda: (marker_dir / "received").exists(), 0.4)
    print(
        f"commit return={result!r} elapsed_ms={elapsed * 1000:.3f} "
        "paused_callback=False",
        flush=True,
    )
    os.kill(child.pid, signal.SIGCONT)
    assert wait_until(lambda: (marker_dir / "received").exists())
    print("resumed_callback=True", flush=True)
finally:
    if child.poll() is None:
        os.kill(child.pid, signal.SIGCONT)
        child.terminate()
        child.wait(timeout=5)
