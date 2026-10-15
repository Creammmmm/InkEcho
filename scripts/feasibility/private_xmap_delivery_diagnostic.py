"""Test-only fresh X-server mapping reads before production presses; private only."""

import ctypes
import ctypes.util
import json
import os
import re
import time
from pathlib import Path


def install(worker):
    runtime = Path(os.environ["XDG_RUNTIME_DIR"])
    root = runtime.parent
    if (
        root.parent != Path("/tmp")
        or not root.name.startswith("inkecho-isolated-keymap-")
        or runtime.name != "runtime"
        or os.environ.get("DISPLAY")
    ):
        raise RuntimeError("private_mapping_diagnostic_environment_required")
    lib = ctypes.CDLL(ctypes.util.find_library("X11"))
    lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    lib.XOpenDisplay.restype = ctypes.c_void_p
    lib.XGetKeyboardMapping.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ubyte,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_int),
    ]
    lib.XGetKeyboardMapping.restype = ctypes.POINTER(ctypes.c_ulong)
    lib.XFree.argtypes = [ctypes.c_void_p]
    lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
    observations = []
    original = worker.MutterSession.key

    async def key(self, code, pressed, *, newline=False):
        cfg_path = root / "x-server.json"
        if pressed and cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            auth = Path(cfg["XAUTHORITY"]).resolve(strict=True)
            if (
                not re.fullmatch(r":\d+", cfg["DISPLAY"])
                or auth.parent != runtime
                or not auth.name.startswith(".mutter-Xwaylandauth.")
            ):
                raise RuntimeError("private_mapping_diagnostic_identity_mismatch")
            # This new connection reads the server rather than Xlib's cached map.
            os.environ["XAUTHORITY"] = str(auth)
            started = time.monotonic()
            display = lib.XOpenDisplay(os.fsencode(cfg["DISPLAY"]))
            if not display:
                raise RuntimeError("private_mapping_diagnostic_connect_failed")
            try:
                width = ctypes.c_int()
                data = lib.XGetKeyboardMapping(display, 132, 1, ctypes.byref(width))
                if not data:
                    raise RuntimeError("private_mapping_diagnostic_read_failed")
                try:
                    symbols = list(data[: width.value])
                finally:
                    lib.XFree(data)
            finally:
                lib.XCloseDisplay(display)
            observations.append(
                {
                    "press_index": len(observations) + 1,
                    "server_ae13_symbols": symbols,
                    "read_seconds": time.monotonic() - started,
                    "production_evdev_code": code,
                    "newline": newline,
                }
            )
            path = root / "x-delivery-diagnostic.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(observations))
            temporary.replace(path)
        return await original(self, code, pressed, newline=newline)

    worker.MutterSession.key = key
