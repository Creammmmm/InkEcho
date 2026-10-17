"""Per-prefix GNOME transport selection, without input replay."""

import asyncio
import math
import time
from collections.abc import Callable

from inkecho.platform.keyboard import KeyboardError, KeyboardInput, _text
from inkecho.platform.wayland_keyboard import WaylandKeyboardInput


class HybridKeyboardInput:
    """Keep each mapping loan exclusive; select again at character boundaries.

    Selection reads the current X receiver only during output, never during
    recording. Native authorization remains required for either transport.
    """

    backend = "gnome-wayland"
    supports_first_sent_callback = True

    def __init__(self, *, native=None, x11=None):
        self.native = native if native is not None else WaylandKeyboardInput()
        self.x11 = x11 if x11 is not None else KeyboardInput()
        self._busy = False
        self._closing = False
        self._task = None

    @property
    def connected(self) -> bool:
        return not self._closing and self.native.connected

    @property
    def authorized(self) -> bool:
        return self.connected and self.native.authorized

    async def connect(self) -> None:
        await self.native.connect()
        try:
            await self.x11.connect()
        except KeyboardError as error:
            if error.code != "display_unavailable":
                raise

    async def authorize(self, parent_window: str = "") -> None:
        await self.native.authorize(parent_window)

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

    async def insert(
        self,
        text: str,
        can_continue: Callable[[], bool],
        *,
        deadline: float | None = None,
        on_first_sent: Callable[[float | None], None] | None = None,
    ) -> int:
        normalized = _text(text)
        if any(ord(char) > 0xFFFF for char in normalized):
            raise KeyboardError("unsupported_text")
        if self._busy:
            raise KeyboardError("busy")
        if not self.authorized:
            raise KeyboardError("permission_required")
        deadline = time.monotonic() + 60 if deadline is None else deadline
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise KeyboardError("input_cancelled")
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

        try:
            while offset < len(normalized):
                check()
                use_x11 = self._x_selected()
                backend = self.x11 if use_x11 else self.native
                options = dict(
                    deadline=deadline,
                    on_first_sent=first_sent,
                    selected=lambda use_x11=use_x11: selected(use_x11),
                )
                if use_x11:
                    # Exit restores the X row before native can acquire its map.
                    async with self.x11.output_session():
                        count = await backend._insert_prefix(
                            normalized[offset:], can_continue, **options
                        )
                else:
                    # The native prefix performs its own begin/finish restoration.
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
        finally:
            self._task = None
            self._busy = False

    async def aclose(self) -> None:
        self._closing = True
        try:
            if self._task is not None and self._task is not asyncio.current_task():
                self._task.cancel()
                try:
                    await self._task
                except (asyncio.CancelledError, KeyboardError):
                    pass
        finally:
            try:
                await self.x11.aclose()
            finally:
                await self.native.aclose()
