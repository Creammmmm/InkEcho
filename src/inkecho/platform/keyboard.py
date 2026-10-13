"""Current-focus X11/XWayland keyboard events, without clipboard or input methods."""

import asyncio
import ctypes
from collections.abc import Callable
from contextlib import contextmanager


class KeyboardError(RuntimeError):
    """Sanitized keyboard transport failure; never contains supplied text."""

    CODES = frozenset(
        {
            "permission_required",
            "permission_denied",
            "portal_unavailable",
            "session_closed",
            "injection_failed",
            "input_cancelled",
            "unsupported_text",
            "busy",
            "unsupported_target",
            "mapping_changed",
            "display_unavailable",
        }
    )

    def __init__(self, code: str):
        self.code = code if code in self.CODES else "injection_failed"
        super().__init__(self.code)


class _KeyEvent(ctypes.Structure):
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


class _Event(ctypes.Union):
    _fields_ = [("key", _KeyEvent), ("pad", ctypes.c_long * 24)]


def _row_identity(row):
    end = len(row)
    while end and row[end - 1] == 0:
        end -= 1
    return tuple(row[:end])


class _XDriver:
    """One X connection. Only an originally empty keycode row is modified."""

    def __init__(self):
        self.x11 = ctypes.CDLL("libX11.so.6")
        p, i, u, word = ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong
        specs = {
            "XOpenDisplay": ([ctypes.c_char_p], p),
            "XCloseDisplay": ([p], i),
            "XDefaultRootWindow": ([p], word),
            "XDisplayKeycodes": ([p, ctypes.POINTER(i), ctypes.POINTER(i)], i),
            "XGetKeyboardMapping": (
                [p, ctypes.c_ubyte, i, ctypes.POINTER(i)],
                ctypes.POINTER(word),
            ),
            "XChangeKeyboardMapping": ([p, i, i, ctypes.POINTER(word), i], i),
            "XGetInputFocus": ([p, ctypes.POINTER(word), ctypes.POINTER(i)], i),
            "XInternAtom": ([p, ctypes.c_char_p, i], word),
            "XGetWindowProperty": (
                [
                    p,
                    word,
                    word,
                    ctypes.c_long,
                    ctypes.c_long,
                    i,
                    word,
                    ctypes.POINTER(word),
                    ctypes.POINTER(i),
                    ctypes.POINTER(word),
                    ctypes.POINTER(word),
                    ctypes.POINTER(p),
                ],
                i,
            ),
            "XQueryTree": (
                [
                    p,
                    word,
                    ctypes.POINTER(word),
                    ctypes.POINTER(word),
                    ctypes.POINTER(p),
                    ctypes.POINTER(u),
                ],
                i,
            ),
            "XKeysymToKeycode": ([p, word], ctypes.c_ubyte),
            "XSendEvent": ([p, word, i, ctypes.c_long, ctypes.POINTER(_Event)], i),
            "XSync": ([p, i], i),
            "XFree": ([p], i),
            "XSetErrorHandler": ([p], p),
        }
        for name, (arguments, result) in specs.items():
            method = getattr(self.x11, name)
            method.argtypes, method.restype = arguments, result
        self.display = self.x11.XOpenDisplay(None)
        if not self.display:
            raise KeyboardError("display_unavailable")
        self.root = self.x11.XDefaultRootWindow(self.display)
        self.slot = None
        self.applied = None
        self.pending_symbol = None
        self.width = None
        low, high = i(), i()
        self.x11.XDisplayKeycodes(self.display, ctypes.byref(low), ctypes.byref(high))
        self.first, self.count = low.value, high.value - low.value + 1
        self.active_atom = self.x11.XInternAtom(self.display, b"_NET_ACTIVE_WINDOW", 0)
        self.pid_atom = self.x11.XInternAtom(self.display, b"_NET_WM_PID", 0)

    @contextmanager
    def _checked(self):
        # Xlib's default BadWindow handler exits the process. Trap errors only on
        # this connection, forwarding other displays to the existing Qt handler.
        errors = []
        callback_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
        previous = None

        def handle(display, event):
            if display == self.display:
                errors.append(True)
                return 0
            return callback_type(previous)(display, event) if previous else 0

        callback = callback_type(handle)
        previous = self.x11.XSetErrorHandler(ctypes.cast(callback, ctypes.c_void_p))
        try:
            yield
            self.x11.XSync(self.display, 0)
            if errors:
                raise KeyboardError("injection_failed")
        finally:
            self.x11.XSync(self.display, 0)
            self.x11.XSetErrorHandler(previous)

    def _property(self, window, atom):
        actual, count, after = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_ulong()
        format_ = ctypes.c_int()
        data = ctypes.c_void_p()
        try:
            result = self.x11.XGetWindowProperty(
                self.display,
                window,
                atom,
                0,
                1,
                0,
                0,
                ctypes.byref(actual),
                ctypes.byref(format_),
                ctypes.byref(count),
                ctypes.byref(after),
                ctypes.byref(data),
            )
            if result or format_.value != 32 or count.value != 1 or not data:
                return 0
            return ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))[0]
        finally:
            if data:
                self.x11.XFree(data)

    def focus(self):
        with self._checked():
            active = self._property(self.root, self.active_atom)
            pid = self._property(active, self.pid_atom) if active else 0
            if not pid:
                raise KeyboardError("unsupported_target")
            focus, revert = ctypes.c_ulong(), ctypes.c_int()
            self.x11.XGetInputFocus(
                self.display, ctypes.byref(focus), ctypes.byref(revert)
            )
            window = focus.value
            if window <= 1:
                raise KeyboardError("unsupported_target")
            ancestor = window
            for _ in range(32):
                if ancestor == active:
                    return window
                root, parent = ctypes.c_ulong(), ctypes.c_ulong()
                children, count = ctypes.c_void_p(), ctypes.c_uint()
                try:
                    status = self.x11.XQueryTree(
                        self.display,
                        ancestor,
                        ctypes.byref(root),
                        ctypes.byref(parent),
                        ctypes.byref(children),
                        ctypes.byref(count),
                    )
                finally:
                    if children:
                        self.x11.XFree(children)
                if not status or parent.value in (0, ancestor, self.root):
                    break
                ancestor = parent.value
            raise KeyboardError("unsupported_target")

    def _mapping(self):
        width = ctypes.c_int()
        with self._checked():
            data = self.x11.XGetKeyboardMapping(
                self.display, self.first, self.count, ctypes.byref(width)
            )
            if not data:
                raise KeyboardError("mapping_changed")
            try:
                return width.value, tuple(data[: self.count * width.value])
            finally:
                self.x11.XFree(data)

    def _row(self):
        width, values = self._mapping()
        offset = (self.slot - self.first) * width
        return tuple(values[offset : offset + width])

    def _write(self, values):
        array = (ctypes.c_ulong * len(values))(*values)
        with self._checked():
            self.x11.XChangeKeyboardMapping(
                self.display, self.slot, len(values), array, 1
            )

    def map(self, character):
        if character == "\n":
            with self._checked():
                code = self.x11.XKeysymToKeycode(self.display, 0xFF0D)
            if not code:
                raise KeyboardError("unsupported_text")
            return code
        if self.slot is None:
            self.width, values = self._mapping()
            empty = [
                self.first + index
                for index in range(self.count)
                if not any(values[index * self.width : (index + 1) * self.width])
            ]
            if not empty:
                raise KeyboardError("mapping_changed")
            self.slot = empty[-1]
        if self.applied is not None and _row_identity(self._row()) != _row_identity(
            self.applied
        ):
            self.applied = None
            raise KeyboardError("mapping_changed")
        if self.applied is None and any(self._row()):
            raise KeyboardError("mapping_changed")
        symbol = ord(character)
        if symbol > 255:
            symbol |= 0x01000000
        # Keep ownership intent before the write: an X error while reading back
        # must not leave a successful mapping write without a cleanup candidate.
        self.pending_symbol = symbol
        self._write([symbol] * self.width)
        self.applied = self._row()
        self.pending_symbol = None
        if symbol not in self.applied:
            raise KeyboardError("mapping_changed")
        return self.slot

    def verify(self):
        if self.applied is not None and _row_identity(self._row()) != _row_identity(
            self.applied
        ):
            self.applied = None
            raise KeyboardError("mapping_changed")

    def send(self, window, code, pressed):
        event = _Event()
        event.key.type = 2 if pressed else 3
        event.key.display = self.display
        event.key.window = window
        event.key.root = self.root
        event.key.keycode = code
        event.key.same_screen = 1
        # Explicit zero modifiers prevent physical Ctrl/Alt/Shift/F4 leftovers
        # turning text into shortcuts. No physical modifier is changed.
        event.key.state = 0
        with self._checked():
            if not self.x11.XSendEvent(self.display, window, 0, 0, ctypes.byref(event)):
                raise KeyboardError("injection_failed")

    def restore(self):
        if self.applied is None and self.pending_symbol is not None:
            row = self._row()
            if not any(row):
                self.pending_symbol = None
                return
            if self.pending_symbol in row and set(row) <= {0, self.pending_symbol}:
                self.applied = row
            else:
                self.pending_symbol = None
                raise KeyboardError("mapping_changed")
        if self.applied is None:
            return
        if _row_identity(self._row()) != _row_identity(self.applied):
            self.applied = None
            raise KeyboardError("mapping_changed")
        self._write([0] * self.width)
        self.applied = None
        self.pending_symbol = None
        if any(self._row()):
            raise KeyboardError("mapping_changed")

    def close(self):
        try:
            self.restore()
        finally:
            self.x11.XCloseDisplay(self.display)


def _text(text):
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    if any(
        (ord(char) < 32 and char != "\n")
        or 127 <= ord(char) < 160
        or 0xD800 <= ord(char) <= 0xDFFF
        for char in normalized
    ):
        raise KeyboardError("unsupported_text")
    return normalized


class KeyboardInput:
    """Authorize at connection time, then emit only at the current X window."""

    def __init__(self, *, driver_factory=_XDriver):
        self._factory = driver_factory
        self._driver = None
        self._task = None
        self._closing = False

    @property
    def connected(self) -> bool:
        return self._driver is not None and not self._closing

    @property
    def authorized(self) -> bool:
        return self.connected

    async def connect(self) -> None:
        if self.connected:
            return
        if self._closing:
            raise KeyboardError("session_closed")
        try:
            self._driver = self._factory()
        except KeyboardError:
            raise
        except Exception:
            raise KeyboardError("display_unavailable") from None

    async def authorize(self, parent_window: str = "") -> None:
        await self.connect()

    def _send(self, window, keycode, pressed):
        self._driver.send(window, keycode, pressed)

    async def insert(self, text: str, can_continue: Callable[[], bool]) -> int:
        text = _text(text)
        if not self.connected:
            raise KeyboardError("session_closed")
        if self._task is not None:
            raise KeyboardError("busy")
        self._task = asyncio.current_task()
        driver = self._driver

        def check():
            if self._closing or not can_continue():
                raise KeyboardError("input_cancelled")

        try:
            for character in text:
                check()
                driver.focus()  # Reject native Wayland/proxy before changing map.
                code = driver.map(character)
                await asyncio.sleep(0.04)
                check()
                window = driver.focus()  # Refresh after every asynchronous gap.
                driver.verify()
                check()
                try:
                    self._send(window, code, True)
                    await asyncio.sleep(0.04)
                finally:
                    self._send(window, code, False)
                await asyncio.sleep(0.04)
                check()
                driver.restore()
        finally:
            try:
                driver.restore()
            finally:
                self._task = None
        return len(text)

    async def aclose(self) -> None:
        self._closing = True
        task = self._task
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, KeyboardError):
                pass
        if self._driver is not None:
            driver, self._driver = self._driver, None
            driver.close()
