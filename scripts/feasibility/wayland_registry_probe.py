"""List advertised Wayland interface names/versions without binding any globals.

Run with an external bound: timeout 10s python wayland_registry_probe.py
Only wl_display.get_registry and its synchronization roundtrip are requested.
No surface, seat, keyboard, clipboard or input-method object is created.
"""

from __future__ import annotations

import ctypes as c
import json


class Interface(c.Structure):
    _fields_ = [
        ("name", c.c_char_p),
        ("version", c.c_int),
        ("method_count", c.c_int),
        ("methods", c.c_void_p),
        ("event_count", c.c_int),
        ("events", c.c_void_p),
    ]


def inspect_registry() -> dict:
    """Read only protocol metadata from a fresh, immediately closed connection."""
    lib = c.CDLL("libwayland-client.so.0")
    signatures = {
        "wl_display_connect": ([c.c_char_p], c.c_void_p),
        "wl_display_disconnect": ([c.c_void_p], None),
        "wl_display_roundtrip": ([c.c_void_p], c.c_int),
        "wl_proxy_get_version": ([c.c_void_p], c.c_uint32),
        "wl_proxy_destroy": ([c.c_void_p], None),
        "wl_proxy_add_listener": (
            [c.c_void_p, c.POINTER(c.c_void_p), c.c_void_p],
            c.c_int,
        ),
        # Fixed arguments of the variadic generated get_registry wrapper.
        "wl_proxy_marshal_flags": (
            [c.c_void_p, c.c_uint32, c.c_void_p, c.c_uint32, c.c_uint32],
            c.c_void_p,
        ),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(lib, name)
        function.argtypes = arguments
        function.restype = result

    advertised = {}
    global_callback = c.CFUNCTYPE(
        None, c.c_void_p, c.c_void_p, c.c_uint32, c.c_char_p, c.c_uint32
    )
    remove_callback = c.CFUNCTYPE(None, c.c_void_p, c.c_void_p, c.c_uint32)

    @global_callback
    def add_global(_data, _registry, number, name, version):
        advertised[number] = {"interface": name.decode("ascii"), "version": version}

    @remove_callback
    def remove_global(_data, _registry, number):
        advertised.pop(number, None)

    listeners = (c.c_void_p * 2)(
        c.cast(add_global, c.c_void_p), c.cast(remove_global, c.c_void_p)
    )
    interface = Interface.in_dll(lib, "wl_registry_interface")
    display = lib.wl_display_connect(None)
    if not display:
        raise RuntimeError("display_unavailable")
    registry = None
    try:
        # wl_display.get_registry is request opcode 1. The final NULL is the
        # new_id placeholder, as in wayland-scanner's generated client wrapper.
        registry = lib.wl_proxy_marshal_flags(
            display, 1, c.byref(interface), lib.wl_proxy_get_version(display), 0, None
        )
        if not registry or lib.wl_proxy_add_listener(registry, listeners, None) < 0:
            raise RuntimeError("registry_unavailable")
        if lib.wl_display_roundtrip(display) < 0:
            raise RuntimeError("roundtrip_failed")
        values = sorted(advertised.values(), key=lambda value: value["interface"])
        return {
            "globals": values,
            "virtual_keyboard_advertised": any(
                value["interface"] == "zwp_virtual_keyboard_manager_v1"
                for value in values
            ),
            "globals_bound": 0,
            "input_requests": 0,
        }
    finally:
        if registry:
            lib.wl_proxy_destroy(registry)
        lib.wl_display_disconnect(display)


if __name__ == "__main__":
    print(json.dumps(inspect_registry(), sort_keys=True))
