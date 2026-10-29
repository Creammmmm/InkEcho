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
    XMODIFIERS="@im=ibus",
    GIO_USE_VFS="local",
)
cmd = [
    "gdbus",
    "call",
    "--session",
    "--dest",
    "io.github.Creammmmm.InkEcho.WaylandFocusProbe",
    "--object-path",
    "/io/github/Creammmmm/InkEcho/WaylandFocusProbe",
    "--method",
]
actors = []
try:
    for name, backend, module in [
        ("wayland", "wayland", None),
        ("button", "wayland", None),
        ("simple", "x11", "gtk-im-context-simple"),
    ]:
        e = env.copy()
        e["GDK_BACKEND"] = backend
        if module:
            e["GTK_IM_MODULE"] = module
        else:
            e.pop("GTK_IM_MODULE", None)
        actors.append(
            subprocess.Popen(["/usr/bin/python3", str(root / "actor.py"), name], env=e)
        )
    time.sleep(5)
    address = (
        subprocess.check_output(["ibus", "address"], env=env, text=True).strip()
        if __import__("shutil").which("ibus")
        else None
    )
    for name in ["wayland", "button", "simple", "wayland", "simple"]:
        print(
            "activate",
            name,
            subprocess.check_output(
                cmd
                + [
                    cmd[-1].replace("--method", "")
                    + "io.github.Creammmmm.InkEcho.WaylandFocusProbe1.Activate",
                    "InkEcho isolated " + name,
                ],
                env=env,
                text=True,
            ).strip(),
            flush=True,
        )
        time.sleep(1)
        print(
            "read",
            name,
            subprocess.check_output(
                cmd + ["io.github.Creammmmm.InkEcho.WaylandFocusProbe1.Read"],
                env=env,
                text=True,
            ).strip(),
            flush=True,
        )
        print(
            "test",
            name,
            subprocess.check_output(
                cmd + ["io.github.Creammmmm.InkEcho.WaylandFocusProbe1.Test", ""],
                env=env,
                text=True,
            ).strip(),
            flush=True,
        )
        time.sleep(0.5)
        f = root / (name + ".txt")
        print("received", name, f.read_text() if f.exists() else "", flush=True)
        for other in ["wayland", "simple"]:
            f = root / (other + ".txt")
            print("contents", other, f.read_text() if f.exists() else "", flush=True)
        if not address:
            continue
        c = subprocess.run(
            [
                "gdbus",
                "call",
                "--address",
                address,
                "--dest",
                "org.freedesktop.IBus",
                "--object-path",
                "/org/freedesktop/IBus",
                "--method",
                "org.freedesktop.IBus.CurrentInputContext",
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        print("current", c.stdout.strip(), flush=True)
finally:
    for a in actors:
        a.terminate()
    for a in actors:
        a.wait(timeout=5)
