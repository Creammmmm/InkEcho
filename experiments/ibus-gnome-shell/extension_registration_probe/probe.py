"""Compare named IBus panel extensions only inside a private bus."""

import os
import subprocess
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
connection = bus.get_connection()
seen = {"custom": [], "emoji": []}


def make_panel(path, name, kind):
    panel = IBus.PanelService(connection=connection, object_path=path)
    panel.connect("focus-in", lambda _panel, context: seen[kind].append(context))
    assert bus.request_name(name, 0) == 1
    return panel


custom = make_panel(
    "/org/freedesktop/IBus/Panel/Extension/InkEcho",
    "org.freedesktop.IBus.Panel.Extension.InkEcho",
    "custom",
)
emoji = make_panel(
    IBus.PATH_PANEL_EXTENSION_EMOJI,
    IBus.SERVICE_PANEL_EXTENSION_EMOJI,
    "emoji",
)


def pump():
    end = time.monotonic() + 0.5
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


pump()
ctx = bus.create_input_context("inkecho-registration-probe")
ctx.set_capabilities(IBus.Capabilite.FOCUS)
ctx.focus_in()
pump()
print("custom focus events", seen["custom"], flush=True)
print("emoji focus events", seen["emoji"], flush=True)
assert ctx.get_object_path() in seen["emoji"]
assert not seen["custom"]
assert custom is not None and emoji is not None
received = []
ctx.connect("commit-text", lambda _ctx, _text: received.append(True))
custom.commit_text(IBus.Text.new_from_string("甲"))
pump()
print("custom commit count", len(received), flush=True)
assert len(received) == 0
emoji.commit_text(IBus.Text.new_from_string("乙"))
pump()
print("emoji commit count", len(received), flush=True)
assert len(received) == 1
claim = subprocess.run(
    [
        "gdbus",
        "call",
        "--address",
        os.environ["IBUS_ADDRESS"],
        "--dest",
        "org.freedesktop.DBus",
        "--object-path",
        "/org/freedesktop/DBus",
        "--method",
        "org.freedesktop.DBus.RequestName",
        IBus.SERVICE_PANEL_EXTENSION_EMOJI,
        "4",  # DBUS_NAME_FLAG_DO_NOT_QUEUE
    ],
    capture_output=True,
    text=True,
    timeout=4,
    check=True,
)
print("second owner attempt", claim.stdout.strip(), flush=True)
assert claim.stdout.strip() == "(uint32 3,)"  # EXISTS: original owner unchanged
