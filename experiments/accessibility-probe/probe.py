"""Only inspect our owned GTK process and submit synthetic text via AT-SPI."""

import os
import subprocess
import time
from pathlib import Path

import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi  # noqa: E402

root = Path("/tmp/inkecho-accessibility-probe")
for name in ("actor-pid", "own-entry.txt"):
    (root / name).unlink(missing_ok=True)
env = os.environ.copy()
env.update(
    XDG_RUNTIME_DIR="/run/user/1000",
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/1000/bus",
    WAYLAND_DISPLAY="wayland-0",
    GDK_BACKEND="wayland",
    GIO_USE_VFS="local",
)
os.environ.update(env)
actor = subprocess.Popen(
    ["/usr/bin/python3", str(root / "actor.py")],
    env=env,
    stdin=subprocess.PIPE,
    text=True,
)


def walk(node):
    yield node
    for index in range(node.get_child_count()):
        child = node.get_child_at_index(index)
        if child:
            yield from walk(child)


try:
    time.sleep(4)
    assert actor.poll() is None
    pid = int((root / "actor-pid").read_text())
    desktop = Atspi.get_desktop(0)
    owned = None
    for app in (
        desktop.get_child_at_index(i) for i in range(desktop.get_child_count())
    ):
        if app and app.get_process_id() == pid:
            owned = app
            break
    if not owned:
        print("owned application not exposed to AT-SPI", flush=True)
    else:
        entries = [
            item for item in walk(owned) if item.get_name() == "InkEcho owned entry"
        ]
        assert len(entries) == 1
        entry = entries[0]
        print("entry focused", entry.get_state_set().contains(Atspi.StateType.FOCUSED))
        text = entry.get_text_iface()
        editable = entry.get_editable_text_iface()
        print("has editable and caret", bool(editable), bool(text), flush=True)
        if (
            editable
            and text
            and entry.get_state_set().contains(Atspi.StateType.FOCUSED)
        ):
            offset = text.get_caret_offset()  # Position only, never read content.
            synthetic = "甲乙"
            accepted = editable.insert_text(
                offset, synthetic, len(synthetic.encode("utf-8"))
            )
            time.sleep(0.3)
            print("insert response", accepted, flush=True)
            result = root / "own-entry.txt"
            print(
                "owned widget result",
                result.read_text() if result.exists() else "",
                flush=True,
            )
            actor.stdin.write("button\n")
            actor.stdin.flush()
            time.sleep(0.5)
            print(
                "entry focused after button",
                entry.get_state_set().contains(Atspi.StateType.FOCUSED),
            )
            actor.stdin.write("selection\n")
            actor.stdin.flush()
            time.sleep(0.5)
            print("selection count", text.get_n_selections(), flush=True)
            position = text.get_caret_offset()
            accepted = editable.insert_text(position, "甲", len("甲".encode()))
            time.sleep(0.3)
            print("selected insert response", accepted, flush=True)
            print(
                "owned selected result",
                result.read_text() if result.exists() else "",
                flush=True,
            )
finally:
    actor.terminate()
    actor.wait(timeout=5)
