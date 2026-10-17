"""Current-focus X11/XWayland keyboard events, without clipboard or input methods."""

import asyncio
import ctypes
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, contextmanager

# Keep the first mapping stable for fresh X clients and retain 20 ms for later
# map changes. The 10 ms press/release profile has bounded fresh-window evidence
# in input-speed-optimization.md; it does not acknowledge application consumption.
INITIAL_MAP_SETTLE_SECONDS = 0.1
MAP_SETTLE_SECONDS = 0.02
PRESS_SETTLE_SECONDS = 0.01
RELEASE_SETTLE_SECONDS = 0.01


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
            "keys_held",
            "caps_lock",
            "cleanup_pending",
            "unsupported_layout",
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
        # Use literal Unicode for Latin as well as other scripts, including
        # across separate streaming insertions. Return remains a real key above.
        symbol = 0x01000000 | ord(character)
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

    supports_first_sent_callback = True

    def __init__(self, *, driver_factory=_XDriver):
        self._factory = driver_factory
        self._driver = None
        self._task = None
        self._output_owner = None
        self._output_failed = False
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

    @asynccontextmanager
    async def output_session(self) -> AsyncIterator[None]:
        """Retain our empty-row loan across fragments owned by one consumer task."""
        if not self.connected:
            raise KeyboardError("session_closed")
        owner = asyncio.current_task()
        if owner is None or self._task is not None or self._output_owner is not None:
            raise KeyboardError("busy")
        driver = self._driver
        self._output_owner, self._output_failed = owner, False
        try:
            yield
            if self._closing:
                raise KeyboardError("session_closed")
            if self._output_failed:
                raise KeyboardError("injection_failed")
        finally:
            try:
                # Same-owner aclose may already have restored and closed it.
                if self._driver is driver:
                    driver.restore()
            finally:
                self._output_owner, self._output_failed = None, False

    async def insert(
        self,
        text: str,
        can_continue: Callable[[], bool],
        *,
        deadline: float | None = None,
        on_first_sent: Callable[[float | None], None] | None = None,
    ) -> int:
        return await self._insert_prefix(
            text, can_continue, deadline=deadline, on_first_sent=on_first_sent
        )

    async def _insert_prefix(
        self,
        text: str,
        can_continue: Callable[[], bool],
        *,
        deadline=None,
        on_first_sent: Callable[[float | None], None] | None = None,
        selected: Callable[[], bool] | None = None,
    ) -> int:
        current = asyncio.current_task()
        try:
            text = _text(text)
        except BaseException:
            if self._output_owner is current and self._driver is not None:
                self._output_failed = True
                self._driver.restore()
            raise
        if not self.connected:
            raise KeyboardError("session_closed")
        if self._task is not None or (
            self._output_owner is not None and self._output_owner is not current
        ):
            raise KeyboardError("busy")
        if self._output_failed:
            raise KeyboardError("input_cancelled")
        self._task = current
        driver = self._driver
        completed = False
        count = 0

        def check():
            if (
                self._closing
                or not can_continue()
                or (deadline is not None and time.monotonic() >= deadline)
            ):
                raise KeyboardError("input_cancelled")

        try:
            for index, character in enumerate(text):
                check()
                if selected is not None and not selected():
                    break
                try:
                    driver.focus()
                except KeyboardError as error:
                    if selected is not None and error.code == "unsupported_target":
                        break
                    raise
                first_mapping = character != "\n" and driver.applied is None
                code = driver.map(character)
                await asyncio.sleep(
                    INITIAL_MAP_SETTLE_SECONDS if first_mapping else MAP_SETTLE_SECONDS
                )
                check()
                if selected is not None and not selected():
                    break  # No press has been attempted for this character.
                try:
                    window = driver.focus()
                except KeyboardError as error:
                    if selected is not None and error.code == "unsupported_target":
                        break
                    raise
                driver.verify()
                check()
                try:
                    self._send(window, code, True)
                    sent_at = time.monotonic()
                    if index == 0 and on_first_sent is not None:
                        on_first_sent(sent_at)
                    await asyncio.sleep(PRESS_SETTLE_SECONDS)
                finally:
                    self._send(window, code, False)
                await asyncio.sleep(RELEASE_SETTLE_SECONDS)
                check()
                count += 1
            completed = True
        finally:
            try:
                if not completed and self._output_owner is current:
                    self._output_failed = True
                if not completed or self._output_owner is not current:
                    driver.restore()
            finally:
                self._task = None
        return count

    async def aclose(self) -> None:
        self._closing = True
        task = self._output_owner or self._task
        try:
            if task is not None and task is not asyncio.current_task():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, KeyboardError):
                    pass
        finally:
            if self._driver is not None:
                driver, self._driver = self._driver, None
                driver.close()
