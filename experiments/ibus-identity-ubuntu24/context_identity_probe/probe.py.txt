"""Compare only identity metadata of isolated fake and client IBus contexts."""

from xml.etree import ElementTree

import gi

gi.require_version("IBus", "1.0")
from gi.repository import Gio, GLib, IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
fake = bus.current_input_context()
client = bus.create_input_context("inkecho-isolated-identity")
client.set_capabilities(
    IBus.Capabilite.PREEDIT_TEXT
    | IBus.Capabilite.FOCUS
    | IBus.Capabilite.SURROUNDING_TEXT
)
real = client.get_object_path()
assert fake and fake != real
connection = bus.get_connection()


def properties(path):
    xml = connection.call_sync(
        "org.freedesktop.IBus",
        path,
        "org.freedesktop.DBus.Introspectable",
        "Introspect",
        None,
        GLib.VariantType.new("(s)"),
        Gio.DBusCallFlags.NONE,
        2000,
        None,
    ).unpack()[0]
    node = ElementTree.fromstring(xml)
    interface = node.find("./interface[@name='org.freedesktop.IBus.InputContext']")
    assert interface is not None
    return sorted(
        (p.get("name"), p.get("access")) for p in interface.findall("property")
    )


fake_properties = properties(fake)
real_properties = properties(real)
print("fake property declarations:", fake_properties, flush=True)
print("real property declarations:", real_properties, flush=True)
assert fake_properties == real_properties and fake_properties


def query(path, method, parameters):
    try:
        result = connection.call_sync(
            "org.freedesktop.IBus",
            path,
            "org.freedesktop.DBus.Properties",
            method,
            parameters,
            None,
            Gio.DBusCallFlags.NONE,
            2000,
            None,
        )
        return ("returned", result.unpack())
    except GLib.Error as error:
        return ("error", Gio.DBusError.get_remote_error(error))


for name in ("Client", "ClientName", "Fake", "Capabilities"):
    values = []
    for path in (fake, real):
        args = GLib.Variant("(ss)", ("org.freedesktop.IBus.InputContext", name))
        values.append(query(path, "Get", args))
    print(name, values, flush=True)
    assert values[0] == values[1]
    assert values[0][0] == "error"

print("identity properties absent or inaccessible in both contexts", flush=True)
