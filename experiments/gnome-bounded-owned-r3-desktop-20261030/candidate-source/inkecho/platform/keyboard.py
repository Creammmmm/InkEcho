"""Current-focus X11/XWayland keyboard events, without clipboard or input methods."""

import asyncio
import ctypes
import math
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, contextmanager
from dataclasses import replace

from inkecho.platform.output_pacing import (
    FeedbackLevel,
    OutputPacer,
    PacingScopeChanged,
)

# Keep the first mapping stable for fresh X clients; later map changes use the
# configured wait. The 10 ms press/release profile has bounded fresh-window evidence
# in input-speed-optimization.md; it does not acknowledge application consumption.
INITIAL_MAP_SETTLE_SECONDS = 0.1
MAP_SETTLE_SECONDS = 0.04
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
            "unsupported_compositor",
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


class _MappingEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("request", ctypes.c_int),
        ("first_keycode", ctypes.c_int),
        ("count", ctypes.c_int),
    ]


class _Event(ctypes.Union):
    _fields_ = [
        ("key", _KeyEvent),
        ("mapping", _MappingEvent),
        ("pad", ctypes.c_long * 24),
    ]


class _ModifierMap(ctypes.Structure):
    _fields_ = [
        ("max_keypermod", ctypes.c_int),
        ("modifiermap", ctypes.POINTER(ctypes.c_ubyte)),
    ]


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
        self.feedback_enabled = False
        self._map_revision = 0
        self._focused_top = None
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
                    self._focused_top = active
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
        self._map_revision = getattr(self, "_map_revision", 0) + 1
        return self.slot

    def mapping_needed(self, text, index):
        return text[index] != "\n"

    def observation_target(self, window):
        return getattr(self, "_focused_top", None) or window

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


class _XTestDriver(_XDriver):
    """Server-wide Xorg events, including terminals which reject XSendEvent.

    Never use this driver on XWayland: its client-local mapping is not the
    compositor's physical keyboard map. Only the explicit Xorg factory selects
    this driver. The empty-row loan and ownership-checked restoration are shared.
    """

    def __init__(self):
        super().__init__()
        self.feedback_enabled = True
        self._pair_applied = {}
        self._pair_pending = {}
        self._batch = {}
        self._map_revision = 0
        self._notified = None
        try:
            self.xtst = ctypes.CDLL("libXtst.so.6")
            p, i, u, word = (
                ctypes.c_void_p,
                ctypes.c_int,
                ctypes.c_uint,
                ctypes.c_ulong,
            )
            self.xtst.XTestFakeKeyEvent.argtypes = [p, u, i, word]
            self.xtst.XTestFakeKeyEvent.restype = i
            self.x11.XQueryKeymap.argtypes = [p, ctypes.POINTER(ctypes.c_char)]
            self.x11.XQueryKeymap.restype = i
            self.x11.XQueryPointer.argtypes = [
                p,
                word,
                ctypes.POINTER(word),
                ctypes.POINTER(word),
                *([ctypes.POINTER(i)] * 4),
                ctypes.POINTER(u),
            ]
            self.x11.XQueryPointer.restype = i
            self.x11.XGetModifierMapping.argtypes = [p]
            self.x11.XGetModifierMapping.restype = ctypes.POINTER(_ModifierMap)
            self.x11.XFreeModifiermap.argtypes = [ctypes.POINTER(_ModifierMap)]
            self.x11.XFreeModifiermap.restype = i
        except BaseException:
            self.close()
            raise

    def _reserve_pair(self):
        self.width, values = self._mapping()
        with self._checked():
            modifiers = self.x11.XGetModifierMapping(self.display)
            if not modifiers:
                raise KeyboardError("mapping_changed")
            try:
                excluded = set(
                    modifiers.contents.modifiermap[
                        : 8 * modifiers.contents.max_keypermod
                    ]
                )
            finally:
                self.x11.XFreeModifiermap(modifiers)
        empty = {
            self.first + index
            for index in range(self.count)
            if self.first + index not in excluded
            and not any(values[index * self.width : (index + 1) * self.width])
        }
        start = next((code for code in sorted(empty) if code + 1 in empty), None)
        if start is None:
            raise KeyboardError("mapping_changed")
        self._pair_applied = {code: () for code in (start, start + 1)}

    def _pair_row(self, code):
        self.slot = code
        return self._row()

    def _owns_pair_row(self, code, actual):
        if _row_identity(actual) == _row_identity(self._pair_applied[code]):
            return True
        pending = self._pair_pending.get(code)
        if pending is None:
            return False
        if _row_identity(actual) == _row_identity(pending):
            return True
        symbols = set(pending) - {0}
        return (
            len(symbols) == 1
            and bool(symbols & set(actual))
            and set(actual) <= symbols | {0}
        )

    def prepare(self, text, index):
        """Two Unicode rows per request; repeated/current symbols reuse the map.

        Frequent global mapping notifications can defer GTK Entry drawing. Keep
        the existing key pacing, but update both adjacent borrowed rows together.
        No mapping is prepared for Return or while an output session is idle.
        """
        if text[index] == "\n" or text[index] in self._batch:
            return
        if not self._pair_applied:
            self._reserve_pair()
        self.verify()
        characters = []
        for offset in range(index, len(text)):
            character = text[offset]
            if character == "\n":
                break
            if character not in characters:
                if len(characters) == 2:
                    break
                characters.append(character)
        codes = tuple(self._pair_applied)
        desired = {}
        for code in codes:
            actual = _row_identity(self._pair_row(code))
            if len(actual) > self.width:
                raise KeyboardError("mapping_changed")
            desired[code] = actual + (0,) * (self.width - len(actual))
        self._batch = dict(zip(characters, codes, strict=False))
        for character, code in self._batch.items():
            desired[code] = (0x01000000 | ord(character),) * self.width
        # Register both intents before any write/readback can fail. A final
        # one-symbol batch retains the unused row's existing owned values.
        self._pair_pending = desired
        array = (ctypes.c_ulong * (self.width * 2))(
            *(desired[codes[0]] + desired[codes[1]])
        )
        with self._checked():
            self.x11.XChangeKeyboardMapping(
                self.display, codes[0], self.width, array, 2
            )
        for code in codes:
            actual = self._pair_row(code)
            pending = self._pair_pending[code]
            symbols = set(pending) - {0}
            if (symbols and not symbols <= set(actual)) or not self._owns_pair_row(
                code, actual
            ):
                raise KeyboardError("mapping_changed")
            self._pair_applied[code] = actual
            del self._pair_pending[code]
        self._map_revision += 1

    def mapping_needed(self, text, index):
        return text[index] != "\n" and text[index] not in self._batch

    def map(self, character):
        if character == "\n":
            return super().map(character)
        self.slot = self._batch[character]
        self.applied = self._pair_applied[self.slot]
        return self.slot

    def verify(self):
        selected = self.slot
        try:
            for code in self._pair_applied:
                if not self._owns_pair_row(code, self._pair_row(code)):
                    raise KeyboardError("mapping_changed")
        finally:
            self.slot = selected

    def restore(self):
        failed = False
        borrowed = tuple(self._pair_applied)
        for code in tuple(self._pair_applied):
            try:
                actual = self._pair_row(code)
                if any(actual):
                    if not self._owns_pair_row(code, actual):
                        raise KeyboardError("mapping_changed")
                    self.applied, self.pending_symbol = actual, None
                    super().restore()
                del self._pair_applied[code]
                self._pair_pending.pop(code, None)
            except Exception:
                failed = True  # Still release every other row that is ours.
        self.applied = self.pending_symbol = None
        self._batch.clear()
        self._notified = None
        if borrowed:
            try:
                self._notify_mapping(min(borrowed), max(borrowed) - min(borrowed) + 1)
            except KeyboardError:
                pass  # Cache hints must never prevent returning borrowed rows.
        if failed:
            raise KeyboardError("mapping_changed")

    def focus(self):
        # Global events inherit physical modifiers. Refuse held keys and lock
        # modifiers rather than releasing or rewriting the user's physical state.
        keys = (ctypes.c_char * 32)()
        root, child = ctypes.c_ulong(), ctypes.c_ulong()
        coordinates = [ctypes.c_int() for _ in range(4)]
        mask = ctypes.c_uint()
        with self._checked():
            self.x11.XQueryKeymap(self.display, keys)
            result = self.x11.XQueryPointer(
                self.display,
                self.root,
                ctypes.byref(root),
                ctypes.byref(child),
                *(ctypes.byref(value) for value in coordinates),
                ctypes.byref(mask),
            )
        # Mod2 is the usual Num Lock and has no effect on our non-keypad,
        # identical-level Unicode rows. Preserve it (as the native backend does).
        if any(bytes(keys)) or mask.value & 0xEF:
            raise KeyboardError("keys_held")
        if not result:
            raise KeyboardError("unsupported_target")
        return super().focus()

    def _notify_mapping(self, first, count):
        # XKB-aware Chromium clients can retain an old map despite server-side
        # MapNotify. Invalidate the current client's cache before its next key.
        # InputFocus (1) follows the cursor; no recording target is retained.
        event = _Event()
        event.mapping.type = 34  # MappingNotify
        event.mapping.display = self.display
        event.mapping.window = 1
        event.mapping.request = 1  # MappingKeyboard
        event.mapping.first_keycode = first
        event.mapping.count = count
        with self._checked():
            if not self.x11.XSendEvent(self.display, 1, 0, 0, ctypes.byref(event)):
                raise KeyboardError("injection_failed")

    def send(self, window, code, pressed):
        # window only deduplicates cache hints; XTest follows the current cursor.
        # Releases must remain possible even if a physical modifier was pressed.
        if pressed and code in getattr(self, "_pair_applied", {}):
            key = (self._map_revision, window)
            if key != self._notified:
                rows = tuple(self._pair_applied)
                self._notify_mapping(min(rows), max(rows) - min(rows) + 1)
                self._notified = key
        with self._checked():
            if not self.xtst.XTestFakeKeyEvent(self.display, code, int(pressed), 0):
                raise KeyboardError("injection_failed")


class KeyboardInput:
    """Authorize at connection time, then emit only at the current X window."""

    supports_first_sent_callback = True

    def __init__(self, *, driver_factory=_XDriver, pacer=None, feedback_factory=None):
        self._factory = driver_factory
        self._driver = None
        self._task = None
        self._output_owner = None
        self._output_failed = False
        self._closing = False
        self._pacer = pacer if pacer is not None else OutputPacer()
        self._feedback_factory = feedback_factory
        self._feedback = None
        self._feedback_poll = None
        self._feedback_disabled = False
        self._pacing_target = None
        self._pacing_token = None
        self._pacing_level = FeedbackLevel.NONE
        self._focus_revision = None
        self._output_deadline = None
        self._mapping_wait_reader = lambda: MAP_SETTLE_SECONDS
        self._feedback_timeout_reader = None
        self._receiver_wait_reader = None
        self._output_mapping_wait = MAP_SETTLE_SECONDS

    def set_mapping_wait_reader(self, reader):
        """Read the X11 mapping wait once at the next output session."""
        self._mapping_wait_reader = reader

    def set_receiver_feedback_wait_reader(self, reader):
        self._receiver_wait_reader = reader

    @property
    def receiver_feedback_status(self):
        if self._output_owner is None or self._pacing_token is None:
            return "not_checked"
        return (
            "available" if self._pacing_level == FeedbackLevel.DRAW else "unavailable"
        )

    def set_feedback_timeout_reader(self, reader):
        """Read the task's X11 draw-feedback timeout at output setup."""
        self._feedback_timeout_reader = reader

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

    def _bind_pacer(self, level):
        self._pacing_level = FeedbackLevel(level)
        self._pacing_token = self._pacer.bind(self._pacing_level)
        if self._feedback is not None:
            token = self._pacing_token
            try:
                self._feedback.set_callback(
                    lambda at, token=token: self._pacer.observe(token, at=at)
                )
            except Exception:
                self._disable_feedback()
                self._pacing_level = FeedbackLevel.NONE
                self._pacing_token = self._pacer.bind(FeedbackLevel.NONE)

    def _select_feedback(self, window):
        driver = self._driver
        top = getattr(driver, "observation_target", lambda value: value)(window)
        target = (window, top)
        if target == self._pacing_target:
            return self._pacing_token
        self._pacing_target = target
        level = FeedbackLevel.NONE
        if not self._feedback_disabled:
            try:
                if self._feedback is None:
                    factory = self._feedback_factory
                    if factory is None and getattr(driver, "feedback_enabled", False):
                        from inkecho.platform.x11_feedback import X11Feedback

                        factory = X11Feedback
                    if factory is not None:
                        self._feedback = factory(driver)
                if self._feedback is not None:
                    level = FeedbackLevel(self._feedback.bind(top).level)
                    watch_focus = getattr(self._feedback, "watch_focus", None)
                    if watch_focus is not None:
                        watch_focus(window)
                    level = FeedbackLevel(self._feedback.capability.level)
                    self._focus_revision = getattr(
                        self._feedback, "focus_revision", None
                    )
            except Exception:
                self._disable_feedback()
                level = FeedbackLevel.NONE
        self._bind_pacer(level)
        if self._feedback is not None and self._feedback_poll is None:
            self._feedback_poll = asyncio.create_task(self._poll_feedback())
        return self._pacing_token

    def _disable_feedback(self):
        feedback, self._feedback = self._feedback, None
        self._feedback_disabled = True
        if feedback is not None:
            try:
                feedback.close()
            except Exception:
                pass  # Optional observation cannot obstruct mapping restoration.

    def _poll_feedback_once(self):
        if self._feedback is None:
            return
        try:
            self._feedback.poll()
            capability = self._feedback.capability
            level = FeedbackLevel(capability.level)
            revision = getattr(self._feedback, "focus_revision", None)
            changed = (
                self._focus_revision is not None and revision != self._focus_revision
            )
            self._focus_revision = revision
            if getattr(capability, "reason", None) == "event_backlog":
                self._disable_feedback()
                self._pacing_target = None
                self._bind_pacer(FeedbackLevel.NONE)
                return
            if changed:
                # Even A -> B -> A is a new observation generation. Events only
                # reset scheduling; actual delivery still follows current focus.
                self._pacing_target = None
                self._bind_pacer(FeedbackLevel.NONE)
            elif level != self._pacing_level:
                self._bind_pacer(level)
        except Exception:
            self._disable_feedback()
            self._bind_pacer(FeedbackLevel.NONE)

    async def _poll_feedback(self):
        while self._feedback is not None:
            self._poll_feedback_once()
            await asyncio.sleep(0.008)

    async def _stop_feedback(self):
        if self._pacing_token is not None:
            self._pacer.invalidate(self._pacing_token)
        poller, self._feedback_poll = self._feedback_poll, None
        try:
            if poller is not None:
                poller.cancel()
                try:
                    await poller
                except asyncio.CancelledError:
                    pass
        finally:
            self._disable_feedback()
            self._pacing_target = self._pacing_token = None
            self._focus_revision = None

    @asynccontextmanager
    async def output_session(self) -> AsyncIterator[None]:
        """Retain our empty-row loan across fragments owned by one consumer task."""
        if not self.connected:
            raise KeyboardError("session_closed")
        owner = asyncio.current_task()
        if owner is None or self._task is not None or self._output_owner is not None:
            raise KeyboardError("busy")
        driver = self._driver
        mapping_wait = self._mapping_wait_reader()
        if type(mapping_wait) not in (int, float) or not 0.020 <= mapping_wait <= 0.250:
            raise ValueError("Invalid X11 mapping wait")
        if self._feedback_timeout_reader is not None:
            feedback_timeout = self._feedback_timeout_reader()
            if type(feedback_timeout) not in (int, float) or not (
                0.020 <= feedback_timeout <= 0.250
            ):
                raise ValueError("Invalid X11 feedback timeout")
            self._pacer.config = replace(
                self._pacer.config, feedback_min=feedback_timeout
            )
        if self._receiver_wait_reader is not None:
            receiver_wait = self._receiver_wait_reader()
            if type(receiver_wait) not in (int, float) or not (
                0.020 <= receiver_wait <= 0.250
            ):
                raise ValueError("Invalid receiver feedback wait")
            self._pacer.config = replace(
                self._pacer.config, receiver_wait_max=receiver_wait
            )
        self._output_owner, self._output_failed = owner, False
        self._output_mapping_wait = mapping_wait
        self._output_deadline = None
        self._feedback_disabled = False
        try:
            yield
            if self._closing:
                raise KeyboardError("session_closed")
            if self._output_failed:
                raise KeyboardError("injection_failed")
        finally:
            try:
                try:
                    await self._stop_feedback()
                finally:
                    # Same-owner aclose may already have restored and closed it.
                    if self._driver is driver:
                        driver.restore()
            finally:
                self._output_owner, self._output_failed = None, False
                self._output_deadline = None

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
                try:
                    await self._stop_feedback()
                finally:
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
        if self._output_owner is None:
            async with self.output_session():
                return await self._insert_prefix(
                    text,
                    can_continue,
                    deadline=deadline,
                    on_first_sent=on_first_sent,
                    selected=selected,
                )
        if deadline is None:
            deadline = self._output_deadline
            if deadline is None:
                deadline = time.monotonic() + 60
        try:
            valid_deadline = type(deadline) in (int, float) and math.isfinite(deadline)
        except OverflowError:
            valid_deadline = False
        if not valid_deadline or (
            self._output_deadline is not None and deadline != self._output_deadline
        ):
            self._output_failed = True
            try:
                await self._stop_feedback()
            finally:
                self._driver.restore()
            raise KeyboardError("input_cancelled")
        if text:
            self._output_deadline = deadline
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
                prepared, mapped, ready = False, False, False
                while True:
                    check()
                    if selected is not None and not selected():
                        break
                    try:
                        window = driver.focus()
                    except KeyboardError as error:
                        if selected is not None and error.code == "unsupported_target":
                            break
                        raise
                    token = self._select_feedback(window)
                    needs_map = not prepared and getattr(
                        driver,
                        "mapping_needed",
                        lambda text, index: text[index] != "\n",
                    )(text, index)

                    def active():
                        check()
                        return True

                    try:
                        # Pace before changing the global map: changing it first
                        # can freeze the very frame progress we are waiting for.
                        await self._pacer.before_send(
                            token,
                            mapping_changed=needs_map,
                            active=active,
                            deadline=deadline,
                        )
                    except PacingScopeChanged:
                        check()
                        continue  # No press has been attempted for this character.
                    check()
                    if selected is not None and not selected():
                        break
                    try:
                        window = driver.focus()
                    except KeyboardError as error:
                        if selected is not None and error.code == "unsupported_target":
                            break
                        raise
                    if self._select_feedback(window) != token:
                        continue
                    if not prepared:
                        first_mapping = character != "\n" and driver.applied is None
                        revision = getattr(driver, "_map_revision", None)
                        prepare = getattr(driver, "prepare", None)
                        if prepare is not None:
                            prepare(text, index)
                        code = driver.map(character)
                        mapped = (
                            getattr(driver, "_map_revision", None) != revision
                            if revision is not None
                            else needs_map
                        )
                        prepared = True
                        # Real map changes retain their protocol floor. Cached
                        # characters no longer pay a fictitious map settle.
                        if mapped:
                            await asyncio.sleep(
                                INITIAL_MAP_SETTLE_SECONDS
                                if first_mapping
                                else self._output_mapping_wait
                            )
                        check()
                        if selected is not None and not selected():
                            break
                        try:
                            window = driver.focus()
                        except KeyboardError as error:
                            if (
                                selected is not None
                                and error.code == "unsupported_target"
                            ):
                                break
                            raise
                        if self._select_feedback(window) != token:
                            continue  # Keep the prepared map; no key was sent.
                    # Observe queued focus events before a press, including a
                    # round trip whose current child/top tuple is unchanged.
                    self._poll_feedback_once()
                    if self._pacing_token != token:
                        continue
                    ready = True
                    break
                if not ready:
                    break
                driver.verify()
                check()
                try:
                    self._send(window, code, True)
                    sent_at = time.monotonic()
                    # Outside the pre-press reselection handler: a changed scope
                    # after delivery must never trigger a replay.
                    self._pacer.sent(token, mapping_changed=mapped)
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
                    try:
                        await self._stop_feedback()
                    finally:
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
            try:
                await self._stop_feedback()
            finally:
                if self._driver is not None:
                    driver, self._driver = self._driver, None
                    driver.close()
