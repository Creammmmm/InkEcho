"""Task-scoped Escape cancellation without recording ordinary keyboard input."""

import asyncio
import ctypes as c
import os

from PySide6.QtCore import QEvent, QObject, QSocketNotifier, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication


class EscapeUnavailable(RuntimeError):
    """The desktop cannot grant a task-scoped Escape shortcut."""


class _ModifierMap(c.Structure):
    _fields_ = [
        ("max_keypermod", c.c_int),
        ("modifiermap", c.POINTER(c.c_ubyte)),
    ]


def _lock_combinations(rows, lock_codes):
    masks = [0]
    for index, row in enumerate(rows):
        assigned = {code for code in row if code}
        # Never ignore a modifier shared with Alt, Control, Shift or another
        # real modifier key. A remapped lock is safe only in a lock-only column.
        if assigned and assigned <= lock_codes:
            masks += [mask | (1 << index) for mask in masks]
    return tuple(sorted(masks))


class _XEscape:
    """Only grab unmodified Escape on Xorg; closing the display releases grabs.

    XWayland cannot observe keys delivered to native Wayland clients. Never use
    this adapter there or claim that an XWayland grab is a global shortcut.
    """

    def __init__(self):
        self.display = None
        try:
            self.lib = c.CDLL("libX11.so.6")
            signatures = {
                "XOpenDisplay": ([c.c_char_p], c.c_void_p),
                "XDefaultRootWindow": ([c.c_void_p], c.c_ulong),
                "XKeysymToKeycode": ([c.c_void_p, c.c_ulong], c.c_ubyte),
                "XGetModifierMapping": ([c.c_void_p], c.POINTER(_ModifierMap)),
                "XFreeModifiermap": ([c.POINTER(_ModifierMap)], c.c_int),
                "XGrabKey": (
                    [
                        c.c_void_p,
                        c.c_int,
                        c.c_uint,
                        c.c_ulong,
                        c.c_int,
                        c.c_int,
                        c.c_int,
                    ],
                    c.c_int,
                ),
                "XSync": ([c.c_void_p, c.c_int], c.c_int),
                "XSetErrorHandler": ([c.c_void_p], c.c_void_p),
                "XConnectionNumber": ([c.c_void_p], c.c_int),
                "XPending": ([c.c_void_p], c.c_int),
                "XNextEvent": ([c.c_void_p, c.c_void_p], c.c_int),
                "XCloseDisplay": ([c.c_void_p], c.c_int),
            }
            for name, (arguments, result) in signatures.items():
                function = getattr(self.lib, name)
                function.argtypes, function.restype = arguments, result
            self.display = self.lib.XOpenDisplay(None)
            if not self.display:
                raise EscapeUnavailable
            root = self.lib.XDefaultRootWindow(self.display)
            key = self.lib.XKeysymToKeycode(self.display, 0xFF1B)
            if not key:
                raise EscapeUnavailable
            mapping = self.lib.XGetModifierMapping(self.display)
            if not mapping:
                raise EscapeUnavailable
            try:
                width = mapping.contents.max_keypermod
                if not 0 < width <= 256:
                    raise EscapeUnavailable
                rows = [
                    tuple(
                        mapping.contents.modifiermap[index * width + offset]
                        for offset in range(width)
                    )
                    for index in range(8)
                ]
                locks = {
                    self.lib.XKeysymToKeycode(self.display, keysym)
                    for keysym in (0xFFE5, 0xFFE6, 0xFF7F, 0xFF14)
                } - {0}
                self.masks = _lock_combinations(rows, locks)
            finally:
                self.lib.XFreeModifiermap(mapping)
            errors = []
            handler = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_void_p)(
                lambda *_args: errors.append(True) or 0
            )
            # Xlib's handler is process-wide: change it only for these synchronous
            # requests on Qt's event-loop thread, and restore before returning.
            old = self.lib.XSetErrorHandler(c.cast(handler, c.c_void_p))
            try:
                for mask in self.masks:
                    self.lib.XGrabKey(self.display, key, mask, root, False, 1, 1)
                self.lib.XSync(self.display, False)
            finally:
                self.lib.XSetErrorHandler(old)
            if errors:
                raise EscapeUnavailable
            self.fd = self.lib.XConnectionNumber(self.display)
        except (OSError, AttributeError, EscapeUnavailable):
            self.close()
            raise EscapeUnavailable from None

    def pressed(self):
        pressed = False
        event = (c.c_long * 24)()
        while self.lib.XPending(self.display):
            self.lib.XNextEvent(self.display, c.byref(event))
            # This connection selects no ordinary input events. Type 2 is the
            # KeyPress granted exclusively for our passive Escape grabs.
            pressed |= c.cast(event, c.POINTER(c.c_int))[0] == 2
        return pressed

    def close(self):
        if self.display:
            self.lib.XCloseDisplay(self.display)
            self.display = None


class TaskEscape(QObject):
    """Arm only during a task; no persistent desktop settings or key logger.

    Xorg grabs and authorized Wayland portal sessions are released at task end.
    Local Qt Escape remains available when the desktop denies a global binding.
    """

    unavailable = Signal(str)

    def __init__(self, cancel, parent=None, *, factory=_XEscape, portal_factory=None):
        super().__init__(parent)
        self.cancel = cancel
        self.factory = factory
        self.active = False
        self.backend = None
        self.notifier = None
        self.revision = 0
        self.portal_factory = portal_factory
        self.portal = None
        self.portal_task = None
        self.pending = set()
        self.closed = False
        QApplication.instance().installEventFilter(self)

    def set_active(self, active):
        if self.closed or active == self.active:
            return
        self.active = active
        self.revision += 1
        if not active:
            self._release()
            return
        revision = self.revision
        # Never put display setup before the recorder's synchronous start call.
        QTimer.singleShot(0, lambda: self._arm(revision))

    def _arm(self, revision):
        if not self.active or revision != self.revision or self.closed:
            return
        session = os.environ.get("XDG_SESSION_TYPE")
        if session == "wayland":
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return
            self.portal_task = loop.create_task(self._arm_portal(revision))
            self.pending.add(self.portal_task)
            self.portal_task.add_done_callback(self.pending.discard)
            return
        if session != "x11":
            return
        try:
            self.backend = self.factory()
            self.notifier = QSocketNotifier(
                self.backend.fd, QSocketNotifier.Type.Read, self
            )
            self.notifier.activated.connect(self._read)
        except EscapeUnavailable:
            # Do not replace a conflicting desktop binding. Local Qt Escape and
            # the existing explicit cancel controls remain available.
            self._release()

    async def _arm_portal(self, revision):
        from inkecho.platform.portal_escape import PortalTaskEscape

        backend = (self.portal_factory or PortalTaskEscape)()
        self.portal = backend
        try:
            await backend.arm(lambda: self._portal_cancel(revision))
            if self.closed or not self.active or revision != self.revision:
                backend.abort()
        except asyncio.CancelledError:
            backend.abort()
        except Exception:
            backend.abort()
            if self.active and revision == self.revision and not self.closed:
                self.unavailable.emit(
                    "未启用全局 Escape；可使用托盘或窗口中的取消入口。"
                )
        finally:
            if backend.closed and self.portal is backend:
                self.portal = None

    def _portal_cancel(self, revision):
        if not self.closed and self.active and revision == self.revision:
            self._cancel()

    def _read(self, *_args):
        if self.backend and self.backend.pressed() and self.active:
            self._cancel()

    def _cancel(self):
        self.set_active(False)
        self.cancel()

    def eventFilter(self, watched, event):
        if (
            self.active
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            self._cancel()
            return True
        return False

    def _release(self):
        if self.portal is not None:
            self.portal.abort()
            self.portal = None
        if self.portal_task is not None:
            if not self.portal_task.done():
                self.portal_task.cancel()
            self.portal_task = None
        if self.notifier is not None:
            self.notifier.setEnabled(False)
            self.notifier.deleteLater()
            self.notifier = None
        if self.backend is not None:
            self.backend.close()
            self.backend = None

    async def shutdown(self):
        self.close()
        if self.pending:
            await asyncio.gather(*tuple(self.pending), return_exceptions=True)

    def close(self):
        self.set_active(False)
        self.closed = True
        self.revision += 1
        self._release()
        QApplication.instance().removeEventFilter(self)
