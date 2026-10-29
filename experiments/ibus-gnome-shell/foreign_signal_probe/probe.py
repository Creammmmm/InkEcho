"""Test whether a foreign sender can impersonate IBus for an owned proxy."""

import os
import subprocess
import time
from pathlib import Path

import gi

gi.require_version("IBus", "1.0")
from gi.repository import GLib, IBus  # noqa: E402

assert os.environ["IBUS_ADDRESS"].startswith("unix:path=/tmp/inkecho-ibus-lab.")
IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
panel = IBus.PanelService.new(bus.get_connection())
assert bus.request_name(IBus.SERVICE_PANEL, 0) == 1
ctx = bus.create_input_context("inkecho-synthetic-signal-victim")
ctx.set_capabilities(IBus.Capabilite.FOCUS)
received = []
raw_senders = []


def inspect_header(_connection, message, incoming, _data):
    if (
        incoming
        and message.get_interface() == "org.freedesktop.IBus.InputContext"
        and message.get_member() == "CommitText"
    ):
        raw_senders.append(message.get_sender())
    return message


filter_id = bus.get_connection().add_filter(inspect_header, None)
ctx.connect("commit-text", lambda _ctx, _text: received.append(True))
ctx.focus_in()


def pump():
    end = time.monotonic() + 0.7
    while time.monotonic() < end:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        time.sleep(0.01)


pump()
assert bus.current_input_context() == ctx.get_object_path()
attacker = subprocess.run(
    [
        "/usr/bin/python3",
        str(Path(__file__).with_name("attacker.py")),
        bus.get_connection().get_unique_name(),
        ctx.get_object_path(),
    ],
    capture_output=True,
    text=True,
    timeout=8,
    check=False,
)
print(
    "foreign sender result",
    attacker.returncode,
    attacker.stdout,
    attacker.stderr,
    flush=True,
)
pump()
print("foreign signals received", len(received), flush=True)
print("foreign signal raw sender headers", raw_senders, flush=True)
assert attacker.returncode == 0 and len(raw_senders) == 2
assert raw_senders[0] == raw_senders[1] and raw_senders[0].startswith(":")
assert not received
panel.commit_text(IBus.Text.new_from_string("乙"))
pump()
print("panel positive control received", len(received), flush=True)
assert received == [True]
bus.get_connection().remove_filter(filter_id)
