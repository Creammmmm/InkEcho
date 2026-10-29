import os
import subprocess
import time
from pathlib import Path

p = Path("/tmp/inkecho-focus-client")
env = os.environ.copy()
env.update(
    XDG_RUNTIME_DIR="/run/user/1000",
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus",
    DISPLAY=":0",
    XAUTHORITY="/run/user/1000/gdm/Xauthority",
    GDK_BACKEND="x11",
    XMODIFIERS="@im=ibus",
    GIO_USE_VFS="local",
)
addr = subprocess.check_output(["ibus", "address"], env=env, text=True).strip()
mon = subprocess.Popen(
    [
        "stdbuf",
        "-oL",
        "dbus-monitor",
        "--address",
        addr,
        "type='method_call',interface='org.freedesktop.IBus.Engine',member='FocusInId'",
        "type='method_call',interface='org.freedesktop.IBus.Engine',member='FocusIn'",
    ],
    stdout=open(p / "monitor.log", "w"),
    stderr=subprocess.STDOUT,
    env=env,
)
procs = []
try:
    for name, module in [("ibus", "ibus"), ("simple", "gtk-im-context-simple")]:
        e = env.copy()
        e["GTK_IM_MODULE"] = module
        procs.append(
            subprocess.Popen(
                ["/usr/bin/python3", str(p / "target.py"), name, str(p / name)], env=e
            )
        )
    time.sleep(4)
    for index, name in [(0, "ibus"), (1, "simple"), (0, "ibus")]:
        proc = procs[index]
        ids = subprocess.check_output(
            [
                "xdotool",
                "search",
                "--pid",
                str(proc.pid),
                "--onlyvisible",
                "--name",
                "^InkEcho isolated " + name + "$",
            ],
            env=env,
            text=True,
        ).splitlines()
        subprocess.run(
            ["xdotool", "windowactivate", "--sync", ids[-1]], env=env, check=True
        )
        active = subprocess.check_output(
            ["xdotool", "getactivewindow"], env=env, text=True
        ).strip()
        print(name, "active=", active, "expected=", ids[-1], flush=True)
        time.sleep(2)
finally:
    for proc in procs:
        proc.terminate()
    mon.terminate()
    mon.wait(timeout=5)
    print("monitor output:")
    print((p / "monitor.log").read_text())
