"""Owned-fixture-only XSendEvent diagnostic; no XTEST or physical modifiers."""

import ctypes
import json
import os
import tempfile
import time


class KeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class Event(ctypes.Union):
    _fields_ = [("key", KeyEvent), ("pad", ctypes.c_long * 24)]


class XSendProbe:
    def __init__(self, keyboard):
        self.keyboard = keyboard
        self.x11, self.display = keyboard.x11, keyboard.display
        self.x11.XGetInputFocus.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
        ]
        self.x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self.x11.XDefaultRootWindow.restype = ctypes.c_ulong
        self.x11.XSendEvent.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_long,
            ctypes.POINTER(Event),
        ]
        self.width, original = keyboard.original
        slots = [
            code
            for code in range(keyboard.first, keyboard.first + keyboard.count)
            if not any(
                original[
                    (code - keyboard.first) * self.width : (code - keyboard.first + 1)
                    * self.width
                ]
            )
        ]
        if not slots:
            raise RuntimeError("No unused diagnostic keycode")
        self.code = slots[-1]
        self.applied_row = None
        self.last_symbol = None
        fd, self.snapshot_path = tempfile.mkstemp(
            prefix="inkecho-xsend-map-", suffix=".json"
        )
        with os.fdopen(fd, "w") as stream:
            json.dump(
                {
                    "first": keyboard.first,
                    "count": keyboard.count,
                    "original": keyboard.original,
                    "slot": self.code,
                },
                stream,
            )

    def row(self):
        width, values = self.keyboard.read()
        offset = (self.code - self.keyboard.first) * width
        return tuple(values[offset : offset + width])

    def restore(self):
        if self.applied_row is None:
            return True
        if self.row() != self.applied_row:
            return False
        zeros = (ctypes.c_ulong * self.width)()
        self.x11.XChangeKeyboardMapping(self.display, self.code, self.width, zeros, 1)
        self.x11.XSync(self.display, 0)
        return not any(self.row())

    def send(self, character, owned_focus, *, existing=False, owner_mask=False):
        focus = ctypes.c_ulong(int(owned_focus))
        if focus.value <= 1:
            raise RuntimeError("No focused X11 window")
        symbol = 0xFF0D if character == "\n" else ord(character)
        if symbol > 255 and character != "\n":
            symbol |= 0x01000000
        code = self.code
        if existing or character == "\n":
            self.x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            self.x11.XKeysymToKeycode.restype = ctypes.c_ubyte
            code = self.x11.XKeysymToKeycode(self.display, symbol)
            if not code:
                raise RuntimeError("No existing keycode")
        else:
            mapping = (ctypes.c_ulong * self.width)(*([symbol] * self.width))
            self.x11.XChangeKeyboardMapping(
                self.display, self.code, self.width, mapping, 1
            )
            self.x11.XSync(self.display, 0)
            self.applied_row = self.row()
            self.last_symbol = symbol
            if symbol not in self.applied_row:
                raise RuntimeError("Temporary mapping did not apply")
            time.sleep(0.04)
        event = Event()
        event.key.display = self.display
        event.key.window = focus.value
        event.key.root = self.x11.XDefaultRootWindow(self.display)
        event.key.keycode = code
        event.key.same_screen = 1
        event.key.state = 0
        try:
            event.key.type = 2
            if not self.x11.XSendEvent(
                self.display,
                focus.value,
                1,
                0 if owner_mask else 1,
                ctypes.byref(event),
            ):
                raise RuntimeError("XSendEvent press failed")
            self.x11.XSync(self.display, 0)
            time.sleep(0.04)
        finally:
            event.key.type = 3
            if not self.x11.XSendEvent(
                self.display,
                focus.value,
                1,
                0 if owner_mask else 2,
                ctypes.byref(event),
            ):
                raise RuntimeError("XSendEvent release failed")
            self.x11.XSync(self.display, 0)
        time.sleep(0.04)
