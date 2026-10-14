"""Read wl_keyboard.keymap from an explicitly named isolated Wayland socket.

No surface, input-method object or injected event is created. Callers must bound
roundtrips externally; this helper has no production input role.
"""

import ctypes as c
import os

from wayland_registry_probe import Interface


def snapshot(socket_name: str) -> bytes:
    lib = c.CDLL("libwayland-client.so.0")
    p, u = c.c_void_p, c.c_uint32
    signatures = {
        "wl_display_connect": ([c.c_char_p], p),
        "wl_display_disconnect": ([p], None),
        "wl_display_roundtrip": ([p], c.c_int),
        "wl_proxy_destroy": ([p], None),
        "wl_proxy_add_listener": ([p, c.POINTER(p), p], c.c_int),
        "wl_proxy_marshal_flags": ([p, u, p, u, u], p),
    }
    for name, (arguments, result) in signatures.items():
        method = getattr(lib, name)
        method.argtypes, method.restype = arguments, result
    interfaces = {
        name: Interface.in_dll(lib, f"wl_{name}_interface")
        for name in ("registry", "seat", "keyboard")
    }
    callbacks, listeners, proxies, seats, maps = [], [], [], [], []

    def listen(proxy, definitions):
        values = []
        for arguments, callback in definitions:
            value = c.CFUNCTYPE(None, p, p, *arguments)(callback)
            callbacks.append(value)
            values.append(c.cast(value, p))
        listener = (p * len(values))(*values)
        listeners.append(listener)
        if lib.wl_proxy_add_listener(proxy, listener, None) < 0:
            raise RuntimeError("listener_failed")

    def global_added(_data, _registry, number, name, version):
        if name == b"wl_seat":
            seats.append((number, min(version, 4)))

    def keymap(_data, _keyboard, format_, fd, size):
        try:
            if format_ == 1 and 0 < size <= 4_000_000:
                maps.append(os.pread(fd, size, 0))
        finally:
            os.close(fd)

    def noop(*_args):
        pass

    def roundtrip():
        if lib.wl_display_roundtrip(display) < 0:
            raise RuntimeError("roundtrip_failed")

    display = lib.wl_display_connect(socket_name.encode("ascii"))
    if not display:
        raise RuntimeError("isolated_display_unavailable")
    try:
        registry = lib.wl_proxy_marshal_flags(
            display, 1, c.byref(interfaces["registry"]), 1, 0, None
        )
        proxies.append(registry)
        listen(registry, [([u, c.c_char_p, u], global_added), ([u], noop)])
        roundtrip()
        if len(seats) != 1:
            raise RuntimeError("expected_one_isolated_seat")
        number, version = seats[0]
        seat = lib.wl_proxy_marshal_flags(
            registry,
            0,
            c.byref(interfaces["seat"]),
            version,
            0,
            u(number),
            b"wl_seat",
            u(version),
            None,
        )
        proxies.append(seat)
        listen(seat, [([u], noop), ([c.c_char_p], noop)])
        roundtrip()
        keyboard = lib.wl_proxy_marshal_flags(
            seat, 1, c.byref(interfaces["keyboard"]), version, 0, None
        )
        proxies.append(keyboard)
        listen(
            keyboard,
            [
                ([u, c.c_int, u], keymap),
                ([u, p, p], noop),
                ([u, p], noop),
                ([u, u, u, u], noop),
                ([u, u, u, u, u], noop),
                ([c.c_int, c.c_int], noop),
            ],
        )
        roundtrip()
        if not maps or not maps[-1].endswith(b"\0"):
            raise RuntimeError("keymap_unavailable")
        return maps[-1]
    finally:
        for proxy in reversed(proxies):
            if proxy:
                lib.wl_proxy_destroy(proxy)
        lib.wl_display_disconnect(display)
