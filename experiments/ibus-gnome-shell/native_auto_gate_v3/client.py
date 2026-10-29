"""Fixed-character isolated probe; --send explicitly permits at most one 甲."""

import argparse
import json

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

NAME = "io.github.Creammmmm.InkEcho.OwnedNativeGateV3"
PATH = "/io/github/Creammmmm/InkEcho/OwnedNativeGateV3"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--owned-pid", type=int, required=True)
parser.add_argument("--send", action="store_true")
parser.add_argument("--cancel-before-send", action="store_true")
args = parser.parse_args()
assert args.owned_pid > 0
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)


def call(method, params=None):
    return bus.call_sync(
        NAME, PATH, NAME + "1", method, params, None,
        Gio.DBusCallFlags.NO_AUTO_START, 2000, None,
    ).unpack()


report = {"read_only": not args.send, "initial": call("Read")}
if args.send:
    report["begun"] = call("Begin", GLib.Variant("(u)", [args.owned_pid]))[0]
    if report["begun"]:
        try:
            if args.cancel_before_send:
                report["cancelled"] = call("Cancel")[0]
            status = call("Send", GLib.Variant("(u)", [0]))[0]
            report["status"] = status
            report["after"] = call("Read")
            report["keyboard_fallback_eligible"] = (
                status == "not_attempted" and report["after"][-1] == 0
            )
        finally:
            call("Cancel")
print(json.dumps(report))
