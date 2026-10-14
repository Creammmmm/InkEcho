"""Discover only an existing Xwayland child of the owned private compositor."""

import os
import re
from pathlib import Path

from isolated_browser_fixture import parent_pid, private_environment


def private_xwayland_environment(compositor_pid):
    private_environment()
    if compositor_pid is None or compositor_pid <= 1:
        raise RuntimeError("Owned compositor PID required")
    runtime = Path(os.environ["XDG_RUNTIME_DIR"]).resolve()
    compositor = Path("/proc") / str(compositor_pid)
    command = compositor.joinpath("cmdline").read_bytes().split(b"\0")
    environment = dict(
        entry.split(b"=", 1)
        for entry in compositor.joinpath("environ").read_bytes().split(b"\0")
        if b"=" in entry
    )
    if (
        parent_pid(compositor_pid) != os.getppid()
        or Path(os.fsdecode(command[0])).name != "gnome-shell"
        or b"--wayland-display" not in command
        or command[command.index(b"--wayland-display") + 1]
        != b"inkecho-isolated-keymap"
        or environment.get(b"XDG_RUNTIME_DIR") != os.fsencode(runtime)
        or environment.get(b"DBUS_SESSION_BUS_ADDRESS")
        != os.fsencode(os.environ["DBUS_SESSION_BUS_ADDRESS"])
    ):
        raise RuntimeError("Private compositor identity mismatch")
    children = compositor.joinpath("task", str(compositor_pid), "children")
    found = []
    for child in children.read_text().split():
        pid = int(child)
        try:
            arguments = (
                Path("/proc").joinpath(child, "cmdline").read_bytes().split(b"\0")
            )
            arguments = [os.fsdecode(value) for value in arguments if value]
            if not arguments or Path(arguments[0]).name.lower() != "xwayland":
                continue
            if parent_pid(pid) != compositor_pid:
                continue
        except (FileNotFoundError, ProcessLookupError):
            continue
        if (
            len(arguments) < 2
            or not re.fullmatch(r":\d+", arguments[1])
            or arguments.count("-auth") != 1
            or arguments.index("-auth") + 1 >= len(arguments)
        ):
            raise RuntimeError("Private Xwayland arguments unavailable")
        display = arguments[1]
        auth = Path(arguments[arguments.index("-auth") + 1]).resolve(strict=True)
        if (
            auth.parent != runtime
            or not auth.name.startswith(".mutter-Xwaylandauth.")
            or not auth.is_file()
            or int(Path(f"/tmp/.X{display[1:]}-lock").read_text()) != compositor_pid
        ):
            raise RuntimeError("Private Xwayland display identity mismatch")
        found.append({"DISPLAY": display, "XAUTHORITY": str(auth), "pid": pid})
    if len(found) != 1:
        raise RuntimeError("Exactly one existing private Xwayland child required")
    result = found[0]
    os.environ.update(
        DISPLAY=result["DISPLAY"],
        XAUTHORITY=result["XAUTHORITY"],
        GDK_BACKEND="x11",
    )
    return result
