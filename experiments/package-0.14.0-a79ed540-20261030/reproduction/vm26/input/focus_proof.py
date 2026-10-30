"""Read-only X11 proof for one caller-owned Chrome window, never DOM emulation."""
import ctypes as C
import ctypes.util
import json
import os
import re
import subprocess
from pathlib import Path


def inspect(xid, *, browser_pid, browser_exe, profile, env=None):
    """Sample OS focus; caller separately takes a fresh document.hasFocus sample."""
    xid = int(xid)
    browser_pid = int(browser_pid)
    env = dict(os.environ if env is None else env)
    exe = Path(browser_exe).resolve(strict=True)
    assert Path(f"/proc/{browser_pid}/exe").resolve(strict=True) == exe
    cmd = Path(f"/proc/{browser_pid}/cmdline").read_bytes().split(b"\0")
    assert os.fsencode("--user-data-dir=" + str(profile)) in cmd
    start = Path(f"/proc/{browser_pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    def prop(*args):
        return subprocess.check_output(["xprop", *args], env=env, text=True, timeout=3)
    own = prop("-id", str(xid), "_NET_WM_PID", "WM_CLASS", "_NET_WM_NAME")
    match = re.search(r"_NET_WM_PID\(CARDINAL\)\s*=\s*(\d+)", own)
    assert match and int(match[1]) == browser_pid
    root = prop("-root", "_NET_ACTIVE_WINDOW")
    active_match = re.search(r"window id # (0x[0-9a-fA-F]+)", root)
    active = int(active_match[1], 16) if active_match else None
    x = C.CDLL(ctypes.util.find_library("X11"))
    def bind(name, restype, args):
        f = getattr(x, name); f.restype = restype; f.argtypes = args; return f
    opened = bind("XOpenDisplay", C.c_void_p, [C.c_char_p])
    closed = bind("XCloseDisplay", C.c_int, [C.c_void_p])
    focused = bind("XGetInputFocus", C.c_int, [C.c_void_p, C.POINTER(C.c_ulong), C.POINTER(C.c_int)])
    tree = bind("XQueryTree", C.c_int, [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_ulong), C.POINTER(C.c_void_p), C.POINTER(C.c_uint)])
    free = bind("XFree", C.c_int, [C.c_void_p])
    d = opened(os.fsencode(env["DISPLAY"])); assert d
    try:
        f = C.c_ulong(); rev = C.c_int(); focused(d, C.byref(f), C.byref(rev))
        chain = [f.value]
        for _ in range(20):
            current = chain[-1]
            if current in (0, 1) or current == xid: break
            root_x = C.c_ulong(); parent = C.c_ulong(); children = C.c_void_p(); n = C.c_uint()
            assert tree(d, current, C.byref(root_x), C.byref(parent), C.byref(children), C.byref(n))
            if children: free(children)
            if parent.value == current or not parent.value: break
            chain.append(parent.value)
    finally:
        closed(d)
    return {"owned_xid": xid, "pid": browser_pid, "pid_start": start,
            "exe": str(exe), "profile": str(profile), "properties": own,
            "net_active_window": active, "input_focus_chain": chain,
            "active_matches": active == xid, "input_focus_owned": xid in chain}
