"""Exercise only a private experimental Fcitx daemon, with no text target."""

import os
import secrets
import sys
import time
from pathlib import Path

from gi.repository import Gio, GLib

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
owner = bus.call_sync(
    "org.freedesktop.DBus",
    "/org/freedesktop/DBus",
    "org.freedesktop.DBus",
    "GetNameOwner",
    GLib.Variant("(s)", ("org.fcitx.Fcitx5",)),
    GLib.VariantType.new("(s)"),
    Gio.DBusCallFlags.NONE,
    2000,
    None,
).unpack()[0]


def call(method, signature, args, result):
    return bus.call_sync(
        owner,
        "/inkecho",
        "org.fcitx.Fcitx.InkEcho1",
        method,
        GLib.Variant(signature, args),
        GLib.VariantType.new(result),
        Gio.DBusCallFlags.NONE,
        2000,
        None,
    ).unpack()[0]


token = secrets.token_hex(32)
path = Path(os.environ["XDG_RUNTIME_DIR"]) / "inkecho-fcitx-candidate.cap"
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as output:
    output.write(token)
try:
    assert call("Begin", "(s)", (token,), "(b)") is True
    focused = len(sys.argv) > 1
    assert call("Commit", "(sus)", (token, 0, "甲"), "(u)") == (1 if focused else 3)
    assert call("Cancel", "(s)", (token,), "(b)") is True
    assert call("Commit", "(sus)", (token, int(focused), "乙"), "(u)") == 0
    if focused:
        time.sleep(0.5)
        assert Path(sys.argv[1]).read_text() == "甲"
        print("confirmed GTK received 甲, cancel, and post-cancel rejection")
    else:
        print("confirmed no target, cancel, and post-cancel rejection")
finally:
    path.unlink(missing_ok=True)
