"""Synthetic preedit and direct-commit check, only inside the disposable VM."""

import os
import subprocess
import time
from pathlib import Path

root = Path("/tmp/inkecho-wayland-focus")
env = os.environ.copy()
env.update(
    XDG_RUNTIME_DIR="/run/user/1000",
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus",
    DISPLAY=":0",
    WAYLAND_DISPLAY="wayland-0",
    GDK_BACKEND="wayland",
    XMODIFIERS="@im=ibus",
    GIO_USE_VFS="local",
)
env.pop("GTK_IM_MODULE", None)
base = [
    "gdbus",
    "call",
    "--session",
    "--dest",
    "io.github.Creammmmm.InkEcho.WaylandFocusProbe",
    "--object-path",
    "/io/github/Creammmmm/InkEcho/WaylandFocusProbe",
    "--method",
]


def call(method, *args):
    result = subprocess.check_output(
        base + ["io.github.Creammmmm.InkEcho.WaylandFocusProbe1." + method, *args],
        env=env,
        text=True,
    ).strip()
    print(method, result, flush=True)
    return result


for name in ("wayland.txt", "wayland-preedit.txt", "wayland-layout.txt"):
    (root / name).unlink(missing_ok=True)
actor = subprocess.Popen(
    ["/usr/bin/python3", str(root / "actor.py"), "wayland"], env=env
)
try:
    time.sleep(4)
    call("Activate", "InkEcho isolated wayland")
    time.sleep(1)
    call("Read")
    call("Preedit")
    time.sleep(1)
    before = root / "wayland-preedit.txt"
    print(
        "preedit length before:", before.read_text() if before.exists() else "unknown"
    )
    layout = root / "wayland-layout.txt"
    print(
        "own synthetic layout before:",
        layout.read_text() if layout.exists() else "unknown",
    )
    call("Test", "")
    time.sleep(1)
    print("preedit length after:", before.read_text() if before.exists() else "unknown")
    print(
        "own synthetic layout after:",
        layout.read_text() if layout.exists() else "unknown",
    )
    text = root / "wayland.txt"
    print("own widget:", text.read_text() if text.exists() else "", flush=True)
finally:
    actor.terminate()
    actor.wait(timeout=5)
