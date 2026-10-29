"""Compare focus object identity for two owned windows in an isolated VM."""

import os
import subprocess
import time
from pathlib import Path

root = Path("/tmp/inkecho-wayland-focus")
env = os.environ.copy()
env.update(
    XDG_RUNTIME_DIR="/run/user/1000",
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus",
    WAYLAND_DISPLAY="wayland-0",
    GDK_BACKEND="wayland",
    GIO_USE_VFS="local",
)
env.pop("GTK_IM_MODULE", None)
base = [
    "gdbus",
    "call",
    "--session",
    "--dest",
    "io.github.Creammmmm.InkEcho.FocusObjectProbe",
    "--object-path",
    "/io/github/Creammmmm/InkEcho/FocusObjectProbe",
    "--method",
]
actors = []


def call(method, *args):
    result = subprocess.check_output(
        base + ["io.github.Creammmmm.InkEcho.FocusObjectProbe1." + method, *args],
        env=env,
        text=True,
    ).strip()
    print(method, *args, result, flush=True)
    return result


try:
    for name in ("one", "two"):
        actors.append(
            subprocess.Popen(
                ["/usr/bin/python3", str(root / "actor.py"), name], env=env
            )
        )
    time.sleep(5)
    assert all(actor.poll() is None for actor in actors)
    assert call("Activate", "InkEcho isolated one") == "(true,)"
    time.sleep(0.8)
    first = call("Remember")
    assert "true" in first and "InkEcho isolated one" in first
    assert call("Activate", "InkEcho isolated two") == "(true,)"
    time.sleep(0.8)
    second = call("Compare")
    assert "InkEcho isolated two" in second
    assert call("Activate", "InkEcho isolated one") == "(true,)"
    time.sleep(0.8)
    third = call("Compare")
    assert "InkEcho isolated one" in third
finally:
    for actor in actors:
        actor.terminate()
    for actor in actors:
        actor.wait(timeout=5)
