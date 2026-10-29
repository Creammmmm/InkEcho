"""Disposable X11 guest only: fixed mapping lifetime under paused GTK client."""

import ctypes
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/tmp/static-map")
mode = sys.argv[1]
assert mode in ("held", "early_restore")
out = ROOT / "simple"
out.unlink(missing_ok=True)
env = dict(os.environ, GTK_IM_MODULE="gtk-im-context-simple")
proc = subprocess.Popen(
    ["/usr/bin/python3", str(ROOT / "target.py"), "simple", str(out)], env=env
)
paused = False
old = None
try:
    time.sleep(3)
    ids = subprocess.check_output(
        [
            "xdotool",
            "search",
            "--pid",
            str(proc.pid),
            "--onlyvisible",
            "--name",
            "^InkEcho isolated simple$",
        ],
        text=True,
    ).splitlines()
    xid = ids[-1]
    subprocess.run(["xdotool", "windowactivate", "--sync", xid], check=True, timeout=5)
    time.sleep(0.5)
    assert (
        subprocess.check_output(["xdotool", "getactivewindow"], text=True).strip()
        == xid
    )

    def listing():
        return subprocess.check_output(["xmodmap", "-pke"], text=True)

    initial = listing()
    lines = initial.splitlines()
    rows = {}
    for line in lines:
        match = re.fullmatch(r"keycode\s+(\d+)\s*=\s*(.*)", line)
        if match and not match[2].strip():
            rows[int(match[1])] = line
    pair = next((n for n in sorted(rows) if n + 1 in rows), None)
    assert pair is not None, "no two empty adjacent slots"
    old = [rows[pair], rows[pair + 1]]

    def setmap(commands):
        for value in commands:
            subprocess.run(["xmodmap", "-e", value], check=True)

    def restore():
        setmap(old)

    setmap([f"keycode {pair} = U7532", f"keycode {pair + 1} = U4E59"])
    time.sleep(0.3)
    os.kill(proc.pid, signal.SIGSTOP)
    paused = True
    x = ctypes.CDLL("libX11.so.6")
    xt = ctypes.CDLL("libXtst.so.6")
    p = ctypes.c_void_p
    x.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x.XOpenDisplay.restype = p
    x.XSync.argtypes = [p, ctypes.c_int]
    x.XCloseDisplay.argtypes = [p]
    xt.XTestFakeKeyEvent.argtypes = [p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    display = x.XOpenDisplay(None)
    assert display
    for code in (pair, pair + 1):
        for pressed in (1, 0):
            assert xt.XTestFakeKeyEvent(display, code, pressed, 0)
            x.XSync(display, 0)
    if mode == "early_restore":
        restore()
    os.kill(proc.pid, signal.SIGCONT)
    paused = False
    time.sleep(1)
    value = out.read_text() if out.exists() else ""
    if mode == "held":
        restore()
    old = None
    after = listing()
    x.XCloseDisplay(display)
    result = {
        "mode": mode,
        "text": value,
        "codes": [pair, pair + 1],
        "map_equal": initial == after,
        "initial_sha256": hashlib.sha256(initial.encode()).hexdigest(),
        "after_sha256": hashlib.sha256(after.encode()).hexdigest(),
        "receiver_paused_during_send": True,
        "expected": "甲乙",
    }
    print(json.dumps(result, ensure_ascii=False), flush=True)
    assert result["map_equal"]
finally:
    if paused:
        os.kill(proc.pid, signal.SIGCONT)
    if old:
        for value in old:
            subprocess.run(["xmodmap", "-e", value], check=False)
    proc.terminate()
    proc.wait(timeout=5)
