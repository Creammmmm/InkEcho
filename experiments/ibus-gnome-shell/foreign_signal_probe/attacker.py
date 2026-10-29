"""Send only synthetic forged signals to an owned private-bus test proxy."""

import os
import sys

import gi

gi.require_version("IBus", "1.0")
from gi.repository import Gio, GLib, IBus  # noqa: E402

assert os.environ["IBUS_ADDRESS"].startswith("unix:path=/tmp/inkecho-ibus-lab.")
IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
connection = bus.get_connection()
destination, path = sys.argv[1:]
print("connected", flush=True)
synthetic = IBus.Text.new_from_string("甲")
serialized = IBus.Serializable.serialize_object(synthetic)
parameters = GLib.Variant("(v)", (serialized,))
print("serialized", flush=True)
for spoof in (False, True):
    message = Gio.DBusMessage.new_signal(
        path, "org.freedesktop.IBus.InputContext", "CommitText"
    )
    message.set_destination(destination)
    message.set_body(parameters)
    if spoof:
        message.set_sender("org.freedesktop.IBus")
    print("before send", spoof, flush=True)
    try:
        sent, _serial = connection.send_message(message, Gio.DBusSendMessageFlags.NONE)
        print("spoof", spoof, "queued", sent, flush=True)
    except GLib.Error as error:
        print("spoof", spoof, "error", error.domain, error.code, flush=True)
connection.flush_sync(None)
