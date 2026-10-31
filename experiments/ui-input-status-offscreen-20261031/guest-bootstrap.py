import json
import os
import pathlib
import subprocess

for line in subprocess.check_output(
    ["systemctl", "--user", "show-environment"], text=True
).splitlines():
    k, _, v = line.partition("=")
    if k in {
        "DISPLAY",
        "XAUTHORITY",
        "WAYLAND_DISPLAY",
        "XDG_SESSION_TYPE",
        "XDG_CURRENT_DESKTOP",
    }:
        os.environ[k] = v
os.environ.update(
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus",
    XDG_RUNTIME_DIR="/run/user/1000",
)
session = os.environ.get("XDG_SESSION_TYPE")
assert session in ("wayland", "x11"), session
p = subprocess.Popen(
    ["/mnt/input/runtime.AppImage", "--appimage-mount"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
try:
    root = p.stdout.readline().strip()
    assert pathlib.Path(root).is_dir(), root
    env = dict(
        os.environ,
        APPDIR=root,
        PYTHONHOME=root + "/usr",
        PYTHONPATH="/mnt/input/src:" + root + "/packages",
        PYTHONNOUSERSITE="1",
        LD_LIBRARY_PATH=root + "/usr/lib/inkecho",
        QT_PLUGIN_PATH=root + "/packages/PySide6/Qt/plugins",
        QT_QPA_PLATFORM="wayland" if session == "wayland" else "xcb",
        LIBGL_ALWAYS_SOFTWARE="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    run = subprocess.run(
        [root + "/usr/bin/python3", "/mnt/input/ui_probe.py"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    print(
        json.dumps(
            {"returncode": run.returncode, "stdout": run.stdout, "stderr": run.stderr},
            ensure_ascii=False,
        )
    )
    assert run.returncode == 0
finally:
    p.terminate()
    p.wait(timeout=10)
