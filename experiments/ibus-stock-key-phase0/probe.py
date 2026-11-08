import json
import os
import time
from contextlib import ExitStack

from gi.repository import Gio, GLib

SERVICE = "org.freedesktop.IBus"
ROOT_PATH = "/org/freedesktop/IBus"
CONTEXT_INTERFACE = SERVICE + ".InputContext"
CONNECTION_FLAGS = (
    Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
    | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION
)


def call(connection, path, interface, method, variant=None):
    return connection.call_sync(
        SERVICE,
        path,
        interface,
        method,
        variant,
        None,
        Gio.DBusCallFlags.NONE,
        500,
        None,
    ).unpack()


def connect_owner(address):
    for _ in range(50):
        try:
            return Gio.DBusConnection.new_for_address_sync(
                address, CONNECTION_FLAGS, None, None
            )
        except GLib.Error:
            time.sleep(0.05)
    raise RuntimeError("private daemon not ready")


def check_context(owner, peer):
    assert owner.get_unique_name() != peer.get_unique_name()
    (context,) = call(
        owner,
        ROOT_PATH,
        SERVICE,
        "CreateInputContext",
        GLib.Variant("(s)", ("inkecho-private-synthetic-owner",)),
    )
    call(
        owner, context, CONTEXT_INTERFACE, "SetCapabilities", GLib.Variant("(u)", (9,))
    )
    call(owner, context, CONTEXT_INTERFACE, "FocusIn")
    (current,) = call(
        peer,
        ROOT_PATH,
        "org.freedesktop.DBus.Properties",
        "Get",
        GLib.Variant("(ss)", (SERVICE, "CurrentInputContext")),
    )
    assert current == context

    event = GLib.Variant("(uuu)", (0x01007532, 0, 0))
    results = {
        "owner": owner.get_unique_name(),
        "peer": peer.get_unique_name(),
        "current": current,
    }
    for name, connection, method in (
        ("owner_process", owner, "ProcessKeyEvent"),
        ("peer_process", peer, "ProcessKeyEvent"),
        ("owner_forward", owner, "ForwardKeyEvent"),
        ("peer_forward", peer, "ForwardKeyEvent"),
    ):
        try:
            results[name] = call(connection, context, CONTEXT_INTERFACE, method, event)
        except GLib.Error as error:
            results[name] = {
                "remote_error": Gio.DBusError.get_remote_error(error),
                "code": error.code,
                "message": error.message,
            }
    call(owner, context, CONTEXT_INTERFACE, "FocusOut")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    assert isinstance(results["owner_process"][0], bool)
    assert results["peer_process"]["code"] == Gio.IOErrorEnum.TIMED_OUT
    for name in ("owner_forward", "peer_forward"):
        assert (
            results[name]["remote_error"] == "org.freedesktop.DBus.Error.UnknownMethod"
        )


def main():
    address = os.environ["IBUS_ADDRESS"]
    assert address.startswith("unix:path=/tmp/inkecho-ibus-stock-key-")
    assert not os.getenv("DISPLAY") and not os.getenv("WAYLAND_DISPLAY")
    with ExitStack() as clients:
        owner = connect_owner(address)
        clients.callback(owner.close_sync, None)
        peer = Gio.DBusConnection.new_for_address_sync(
            address, CONNECTION_FLAGS, None, None
        )
        clients.callback(peer.close_sync, None)
        check_context(owner, peer)


if __name__ == "__main__":
    main()
