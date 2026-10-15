"""Async parent for the GNOME keyboard guardian; never routes by focused window."""

import asyncio
import json
import math
import os
import sys
import time
from collections.abc import Callable, Mapping

from inkecho.platform.keyboard import KeyboardError, KeyboardInput


def keyboard_for_desktop(environ: Mapping[str, str] | None = None):
    env = os.environ if environ is None else environ
    if env.get("XDG_SESSION_TYPE", "").lower() == "wayland" and "GNOME" in env.get(
        "XDG_CURRENT_DESKTOP", ""
    ).upper().split(":"):
        return WaylandKeyboardInput()
    return KeyboardInput()


class WaylandKeyboardInput:
    """One guardian per application; stdout contains bounded fixed-code replies."""

    backend = "gnome-wayland"
    supports_first_sent_callback = True

    def __init__(self, *, spawn=None, timeout=5, cleanup_timeout=5):
        self._spawn = spawn or asyncio.create_subprocess_exec
        self.timeout = timeout
        self.cleanup_timeout = cleanup_timeout
        self._process = None
        self._starting = None
        self._reader = None
        self._pending = {}
        self._serial = 0
        self._connected = False
        self._authorized = False
        self._closing = False
        self._busy = False
        self._cleanup_pending = False
        self._connect_lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return bool(
            self._connected
            and not self._closing
            and not self._cleanup_pending
            and self._process is not None
            and self._process.returncode is None
        )

    @property
    def authorized(self) -> bool:
        return self.connected and self._authorized

    def _close_pipe(self, process=None):
        process = self._process if process is None else process
        if process is self._process:
            self._connected = self._authorized = False
        if process is not None and process.stdin is not None:
            process.stdin.close()

    async def _read_replies(self, process, pending):
        try:
            while line := await process.stdout.readline():
                if len(line) > 4096 or not line.endswith(b"\n"):
                    raise ValueError
                reply = json.loads(line)
                if reply == {"event": "session_closed"}:
                    self._close_pipe(process)
                    break
                if (
                    not isinstance(reply, dict)
                    or type(reply.get("id")) is not int
                    or type(reply.get("ok")) is not bool
                ):
                    raise ValueError
                future = pending.get(reply["id"])
                if future is not None and not future.done():
                    if reply["ok"]:
                        future.set_result(reply)
                    else:
                        code = reply.get("error")
                        if not isinstance(code, str):
                            code = "injection_failed"
                        if process is self._process and code in {
                            "session_closed",
                            "permission_denied",
                            "display_unavailable",
                            "cleanup_pending",
                        }:
                            self._authorized = False
                            if code != "permission_denied":
                                self._cleanup_pending = code == "cleanup_pending"
                                self._close_pipe(process)
                        future.set_exception(KeyboardError(code))
        except (ValueError, UnicodeError, OSError, asyncio.LimitOverrunError):
            pass
        finally:
            self._close_pipe(process)
            for future in pending.values():
                if not future.done():
                    future.set_exception(KeyboardError("session_closed"))

    async def _request(
        self, operation, *, timeout=None, process=None, pending=None, **fields
    ):
        process = self._process if process is None else process
        pending = self._pending if pending is None else pending
        if process is None or process.returncode is not None:
            raise KeyboardError("session_closed")
        self._serial += 1
        identity = self._serial
        future = asyncio.get_running_loop().create_future()
        pending[identity] = future
        try:
            payload = json.dumps({"id": identity, "op": operation, **fields}).encode()
            if len(payload) + 1 > 4096:
                raise KeyboardError("unsupported_text")
            process.stdin.write(payload + b"\n")
            await asyncio.wait_for(
                process.stdin.drain(),
                self.timeout if timeout is None else timeout,
            )
            return await asyncio.wait_for(
                future, self.timeout if timeout is None else timeout
            )
        except (OSError, RuntimeError, TimeoutError) as error:
            if isinstance(error, KeyboardError):
                raise
            raise KeyboardError("session_closed") from None
        finally:
            pending.pop(identity, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()

    async def connect(self) -> None:
        async with self._connect_lock:
            if self._closing:
                raise KeyboardError("session_closed")
            if self.connected:
                return
            if self._starting is not None and not self._starting.done():
                raise KeyboardError("cleanup_pending")
            if self._process is not None and self._process.returncode is None:
                raise KeyboardError("cleanup_pending")
            try:
                self._starting = asyncio.create_task(
                    self._spawn(
                        sys.executable,
                        "-m",
                        "inkecho.platform.wayland_worker",
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        limit=4096,
                        start_new_session=True,
                    )
                )
                try:
                    self._process = await asyncio.wait_for(
                        asyncio.shield(self._starting), self.timeout
                    )
                except BaseException:

                    def abandon(task):
                        if not task.cancelled() and task.exception() is None:
                            task.result().stdin.close()

                    self._starting.add_done_callback(abandon)
                    raise
                if self._closing:
                    self._close_pipe()
                    raise KeyboardError("session_closed")
                self._cleanup_pending = False
                self._pending = {}
                self._reader = asyncio.create_task(
                    self._read_replies(self._process, self._pending)
                )
                await self._request("connect")
                if self._closing or self._reader.done():
                    raise KeyboardError("session_closed")
                self._connected = True
            except asyncio.CancelledError:
                self._close_pipe()
                raise
            except KeyboardError:
                self._close_pipe()
                raise
            except (OSError, TimeoutError):
                self._close_pipe()
                raise KeyboardError("display_unavailable") from None

    async def _cancel_and_clean(self, process):
        if process is not self._process:
            self._close_pipe(process)
            return
        pending = self._pending

        async def clean():
            if process is not self._process:
                self._close_pipe(process)
                return
            try:
                await self._request(
                    "cancel",
                    timeout=self.cleanup_timeout,
                    process=process,
                    pending=pending,
                )
            except KeyboardError:
                if process is self._process:
                    self._cleanup_pending = True
                self._close_pipe(process)
                raise KeyboardError("cleanup_pending") from None

        cleanup = asyncio.create_task(clean())
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            # A second caller cancellation must not cancel guardian cleanup.
            cleanup.add_done_callback(
                lambda task: task.exception() if not task.cancelled() else None
            )
            raise

    async def authorize(self, parent_window: str = "") -> None:
        del parent_window  # This GNOME route does not fabricate a target/window handle.
        if not self.connected:
            raise KeyboardError("session_closed")
        if self.authorized:
            return
        process = self._process
        try:
            await self._request("authorize")
            if self._closing or not self.connected or process is not self._process:
                raise KeyboardError("session_closed")
            self._authorized = True
        except BaseException:
            self._authorized = False
            await self._cancel_and_clean(process)
            raise

    async def insert(
        self,
        text: str,
        can_continue: Callable[[], bool],
        *,
        deadline: float | None = None,
        on_first_sent: Callable[[float | None], None] | None = None,
    ) -> int:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        if any(
            (ord(char) < 32 and char != "\n")
            or 0x7F <= ord(char) <= 0x9F
            or 0xD800 <= ord(char) <= 0xDFFF
            or ord(char) > 0xFFFF
            for char in normalized
        ):
            raise KeyboardError("unsupported_text")
        if self._busy:
            raise KeyboardError("busy")
        if not self.authorized:
            raise KeyboardError("permission_required")
        self._busy = True
        process = self._process

        def check():
            if (
                self._closing
                or process is not self._process
                or not can_continue()
                or (deadline is not None and time.monotonic() >= deadline)
            ):
                raise KeyboardError("input_cancelled")

        try:
            check()
            await self._request("begin", deadline=deadline)
            count = 0
            for character in normalized:
                check()
                request_start = time.monotonic()
                result = await self._request("key", value=character)
                acknowledged = time.monotonic()
                check()
                if type(result.get("count")) is not int or result["count"] != 1:
                    raise KeyboardError("injection_failed")
                sent_at = result.get("sent_at")
                if (
                    type(sent_at) not in (float, int)
                    or not request_start <= sent_at <= acknowledged
                    or not math.isfinite(sent_at)
                ):
                    raise KeyboardError("injection_failed")
                if count == 0 and on_first_sent is not None:
                    on_first_sent(sent_at)
                count += 1
            await self._request("finish", timeout=self.cleanup_timeout)
            check()
            return count
        except BaseException:
            await self._cancel_and_clean(process)
            raise
        finally:
            self._busy = False

    async def aclose(self) -> None:
        self._closing = True
        self._authorized = self._connected = False
        process = self._process
        if process is None:
            return
        try:
            if process.returncode is None:
                await self._request("close", timeout=self.cleanup_timeout)
        finally:
            # EOF is also the guardian's parent-death signal. Never SIGKILL a
            # guardian that may still own a map or a possibly pressed key.
            self._close_pipe()
            try:
                await asyncio.wait_for(process.wait(), self.cleanup_timeout)
            except TimeoutError:
                self._cleanup_pending = True
                raise KeyboardError("cleanup_pending") from None
            if self._reader is not None:
                await self._reader
