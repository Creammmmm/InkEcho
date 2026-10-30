"""Per-prefix GNOME transport selection, without input replay."""

import asyncio
import math
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from inkecho.platform.keyboard import KeyboardError, KeyboardInput, _text
from inkecho.platform.wayland_keyboard import WaylandKeyboardInput


class HybridKeyboardInput:
    """Keep each mapping loan exclusive; select again at character boundaries.

    Selection reads the current X receiver only during output, never during
    recording. If native authorization reports an unsupported compositor,
    only a currently selected XWayland receiver is allowed.
    """

    backend = "gnome-wayland"
    supports_first_sent_callback = True

    def __init__(self, *, native=None, x11=None):
        self.native = native if native is not None else WaylandKeyboardInput()
        self.x11 = x11 if x11 is not None else KeyboardInput()
        self._busy = False
        self._closing = False
        self._task = None
        self._output_owner = None
        self._completed_dispatches = 0
        self._output_failed = False
        self._output_deadline = None
        self._scope = None
        self._backend = None
        self._output_check = None
        self._mapping_wait_reader = None
        self._feedback_timeout_reader = None
        self._receiver_wait_reader = None
        self._xonly = False

    def set_mapping_wait_reader(self, reader):
        self._mapping_wait_reader = reader

    def set_receiver_feedback_wait_reader(self, reader):
        self._receiver_wait_reader = reader

    @property
    def receiver_feedback_status(self):
        if self._output_owner is None or self._backend is None:
            return "not_checked"
        if self._backend is self.native:
            return "unsupported"
        return getattr(self.x11, "receiver_feedback_status", "unavailable")

    def set_feedback_timeout_reader(self, reader):
        self._feedback_timeout_reader = reader

    @property
    def acknowledged_attempts(self):
        """Completed backend dispatches; not target delivery receipts."""
        if self._output_owner is None:
            return 0
        current = getattr(self._backend, "acknowledged_attempts", 0)
        if type(current) is not int or current < 0:
            current = 0
        return self._completed_dispatches + current

    @property
    def connected(self) -> bool:
        return not self._closing and (
            self.x11.connected if self._xonly else self.native.connected
        )

    @property
    def authorized(self) -> bool:
        return self.connected and (self._xonly or self.native.authorized)

    async def connect(self) -> None:
        await self.native.connect()
        try:
            await self.x11.connect()
        except KeyboardError as error:
            if error.code != "display_unavailable":
                raise

    async def authorize(self, parent_window: str = "") -> None:
        try:
            await self.native.authorize(parent_window)
        except KeyboardError as error:
            if error.code != "unsupported_compositor" or not self.x11.connected:
                raise
            # Select only at output time, never at recording start.
            self._xonly = True

    def _x_selected(self):
        if not self.x11.connected:
            return False
        try:
            self.x11._driver.focus()
        except KeyboardError as error:
            if error.code == "unsupported_target":
                return False
            raise
        return True

    async def _release_scope(self, error=None):
        scope, self._scope = self._scope, None
        backend, self._backend = self._backend, None
        if scope is not None:
            count = getattr(backend, "acknowledged_attempts", 0)
            if type(count) is int and count >= 0:
                self._completed_dispatches += count
            try:
                await scope.__aexit__(
                    type(error) if error is not None else None,
                    error,
                    error.__traceback__ if error is not None else None,
                )
            except Exception as failure:
                try:
                    failure.acknowledged_attempts = self._completed_dispatches
                except Exception:
                    pass
                raise

    @asynccontextmanager
    async def output_session(self) -> AsyncIterator[None]:
        owner = asyncio.current_task()
        if owner is None or self._output_owner is not None or self._busy:
            raise KeyboardError("busy")
        if not self.authorized:
            raise KeyboardError("permission_required")
        if self._mapping_wait_reader is not None:
            mapping_wait = self._mapping_wait_reader()
            configure = getattr(self.x11, "set_mapping_wait_reader", None)
            if callable(configure):
                configure(lambda: mapping_wait)
        if self._feedback_timeout_reader is not None:
            feedback_timeout = self._feedback_timeout_reader()
            configure = getattr(self.x11, "set_feedback_timeout_reader", None)
            if callable(configure):
                configure(lambda: feedback_timeout)
        if self._receiver_wait_reader is not None:
            receiver_wait = self._receiver_wait_reader()
            configure = getattr(self.x11, "set_receiver_feedback_wait_reader", None)
            if callable(configure):
                configure(lambda: receiver_wait)
        self._completed_dispatches = 0
        self._output_owner = owner
        self._output_failed = False
        self._output_deadline = None
        try:
            yield
            if self._closing or self._output_failed:
                raise KeyboardError("injection_failed")
            await self._release_scope()
            if self._output_check is not None:
                self._output_check()
        except BaseException as error:
            await self._release_scope(error)
            raise
        finally:
            try:
                await self._release_scope()
            finally:
                self._output_owner = None
                self._output_deadline = None
                self._output_failed = False
                self._output_check = None

    async def insert(
        self,
        text: str,
        can_continue: Callable[[], bool],
        *,
        deadline: float | None = None,
        on_first_sent: Callable[[float | None], None] | None = None,
    ) -> int:
        current = asyncio.current_task()
        if self._busy or (
            self._output_owner is not None and self._output_owner is not current
        ):
            raise KeyboardError("busy")
        if self._output_owner is None:
            async with self.output_session():
                return await self.insert(
                    text, can_continue, deadline=deadline, on_first_sent=on_first_sent
                )
        try:
            normalized = _text(text)
            if any(ord(char) > 0xFFFF for char in normalized):
                raise KeyboardError("unsupported_text")
            if self._output_failed:
                raise KeyboardError("input_cancelled")
            if not self.authorized:
                raise KeyboardError("permission_required")
            if deadline is None:
                deadline = self._output_deadline
                if deadline is None:
                    deadline = time.monotonic() + 60
            if type(deadline) not in (int, float) or not math.isfinite(deadline):
                raise KeyboardError("input_cancelled")
            if self._output_deadline is not None and deadline != self._output_deadline:
                raise KeyboardError("input_cancelled")
            if normalized:
                self._output_deadline = deadline
        except BaseException as error:
            self._output_failed = True
            await self._release_scope(error)
            raise
        self._busy = True
        self._task = asyncio.current_task()
        offset = 0
        reported = False

        def check():
            if self._closing or not can_continue() or time.monotonic() >= deadline:
                raise KeyboardError("input_cancelled")
            if not self.authorized:
                raise KeyboardError("session_closed")

        def first_sent(sent_at):
            nonlocal reported
            if not reported:
                reported = True
                if on_first_sent is not None:
                    on_first_sent(sent_at)

        def selected(x11):
            check()
            return self._x_selected() == x11

        if normalized:
            self._output_check = check
        try:
            while offset < len(normalized):
                check()
                use_x11 = self._x_selected()
                if self._xonly and not use_x11:
                    raise KeyboardError("unsupported_compositor")
                backend = self.x11 if use_x11 else self.native
                options = dict(
                    deadline=deadline,
                    on_first_sent=first_sent,
                    selected=lambda use_x11=use_x11: selected(use_x11),
                )
                if self._backend is not backend:
                    await self._release_scope()
                    check()
                    scope = backend.output_session()
                    await scope.__aenter__()
                    self._scope, self._backend = scope, backend
                    check()
                count = await backend._insert_prefix(
                    normalized[offset:], can_continue, **options
                )
                check()
                if type(count) is not int or not 0 <= count <= len(normalized) - offset:
                    raise KeyboardError("injection_failed")
                offset += count
                if not count:
                    # Focus can move between selection and the final press check.
                    # Yield even under repeated changes; cancellation remains live.
                    await asyncio.sleep(0.001)
                    check()
            return offset
        except BaseException as error:
            self._output_failed = True
            if isinstance(error, Exception):
                try:
                    error.acknowledged_attempts = self.acknowledged_attempts
                except Exception:
                    pass
            await self._release_scope(error)
            raise
        finally:
            self._task = None
            self._busy = False

    async def aclose(self) -> None:
        self._closing = True
        try:
            task = self._output_owner or self._task
            if task is not None and task is not asyncio.current_task():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, KeyboardError):
                    pass
        finally:
            try:
                await self.x11.aclose()
            finally:
                await self.native.aclose()
