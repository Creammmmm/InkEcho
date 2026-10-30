"""Async parent for the GNOME keyboard guardian; never routes by focused window."""

import asyncio
import json
import math
import os
import sys
import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager

from inkecho.platform.keyboard import KeyboardError, KeyboardInput, _XTestDriver
from inkecho.platform.output_pacing import FeedbackLevel, OutputPacer


def _input_feedback(value):
    """Validate optional input diagnostics without changing delivery semantics."""
    if not isinstance(value, dict) or set(value) != {
        "map_changed",
        "cache_hit",
        "map_set_seconds",
        "map_confirm_seconds",
    }:
        return None
    if any(type(value[key]) is not bool for key in ("map_changed", "cache_hit")):
        return None
    if value["map_changed"] and value["cache_hit"]:
        return None
    for key in ("map_set_seconds", "map_confirm_seconds"):
        number = value[key]
        if type(number) not in (float, int) or number < 0:
            return None
        try:
            if not math.isfinite(number):
                return None
        except OverflowError:
            # JSON integers can exceed float range while remaining within the
            # reply size limit. Advisory parsing must not fail an accepted key.
            return None
    return dict(value)


def keyboard_for_desktop(environ: Mapping[str, str] | None = None):
    env = os.environ if environ is None else environ
    if env.get("XDG_SESSION_TYPE", "").lower() == "wayland" and "GNOME" in env.get(
        "XDG_CURRENT_DESKTOP", ""
    ).upper().split(":"):
        from inkecho.platform.hybrid_keyboard import HybridKeyboardInput

        return HybridKeyboardInput()
    if env.get("XDG_SESSION_TYPE", "").lower() == "x11":
        return KeyboardInput(driver_factory=_XTestDriver)
    return KeyboardInput()


class WaylandKeyboardInput:
    """One guardian per application; stdout contains bounded fixed-code replies."""

    backend = "gnome-wayland"
    supports_first_sent_callback = True

    def __init__(self, *, spawn=None, timeout=5, cleanup_timeout=5, pacer=None):
        self._pacer = pacer if pacer is not None else OutputPacer()
        self._pacing_token = None
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
        self._output_owner = None
        self._acknowledged_keys = 0
        self._output_failed = False
        self._output_deadline = None
        self._output_process = None
        self._begun = False
        self._output_check = None
        self._cleanup_pending = False
        self._cleanup_task = None
        self._cleanup_process = None
        self._connect_lock = asyncio.Lock()

    def _cleaning(self):
        return self._cleanup_task is not None and self._cleanup_process is self._process

    @property
    def acknowledged_attempts(self):
        """Worker-acknowledged key requests, not target delivery receipts."""
        return self._acknowledged_keys if self._output_owner is not None else 0

    @property
    def connected(self) -> bool:
        return bool(
            self._connected
            and not self._closing
            and not self._cleanup_pending
            and not self._cleaning()
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
            if self._cleaning() or (
                self._cleanup_pending
                and (self._process is None or self._process.returncode is None)
            ):
                raise KeyboardError("cleanup_pending")
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
        if self._cleanup_process is process and self._cleanup_task is not None:
            cleanup = self._cleanup_task
        elif process is not self._process:
            self._close_pipe(process)
            return
        else:
            pending = self._pending

            async def clean():
                current = asyncio.current_task()
                try:
                    if process is not self._process:
                        self._close_pipe(process)
                        return
                    await self._request(
                        "cancel",
                        timeout=self.cleanup_timeout,
                        process=process,
                        pending=pending,
                    )
                except KeyboardError:
                    if (
                        process is self._process
                        and self._cleanup_task is current
                        and self._cleanup_process is process
                    ):
                        self._cleanup_pending = True
                    self._close_pipe(process)
                    raise KeyboardError("cleanup_pending") from None
                finally:
                    # A replaced process may already own another cleanup task.
                    # Completing this older generation must never unlock it.
                    if (
                        self._cleanup_task is current
                        and self._cleanup_process is process
                    ):
                        self._cleanup_task = self._cleanup_process = None

            self._cleanup_process = process
            cleanup = self._cleanup_task = asyncio.create_task(clean())
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            # The process-bound lock outlives a twice-cancelled requester.
            cleanup.add_done_callback(
                lambda task: task.exception() if not task.cancelled() else None
            )
            raise

    async def authorize(self, parent_window: str = "") -> None:
        del parent_window  # This GNOME route does not fabricate a target/window handle.
        if self._cleaning() or self._cleanup_pending:
            raise KeyboardError("cleanup_pending")
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

    @asynccontextmanager
    async def output_session(self) -> AsyncIterator[None]:
        if self._cleaning() or self._cleanup_pending:
            raise KeyboardError("cleanup_pending")
        owner = asyncio.current_task()
        if owner is None or self._busy or self._output_owner is not None:
            raise KeyboardError("busy")
        if not self.authorized:
            raise KeyboardError("permission_required")
        self._acknowledged_keys = 0
        self._output_owner = owner
        self._output_process = self._process
        self._output_deadline = None
        self._output_failed = False
        self._begun = False
        token = self._pacer.bind(FeedbackLevel.INPUT)
        self._pacing_token = token
        try:
            yield
            if self._closing or self._output_failed:
                raise KeyboardError("injection_failed")
            if self._begun:
                if self._process is not self._output_process:
                    raise KeyboardError("session_closed")
                await self._request("finish", timeout=self.cleanup_timeout)
                self._begun = False
                if self._output_check is not None:
                    self._output_check()
        except BaseException:
            if self._begun:
                self._begun = False
                await self._cancel_and_clean(self._output_process)
            raise
        finally:
            self._pacer.invalidate(token)
            self._pacing_token = None
            self._output_owner = self._output_process = self._output_deadline = None
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
        return await self._insert_prefix(
            text, can_continue, deadline=deadline, on_first_sent=on_first_sent
        )

    async def _insert_prefix(
        self,
        text: str,
        can_continue: Callable[[], bool],
        *,
        deadline: float | None = None,
        on_first_sent: Callable[[float | None], None] | None = None,
        selected: Callable[[], bool] | None = None,
    ) -> int:
        current = asyncio.current_task()
        if self._busy or (
            self._output_owner is not None and self._output_owner is not current
        ):
            raise KeyboardError("busy")
        if self._output_owner is None:
            async with self.output_session():
                return await self._insert_prefix(
                    text,
                    can_continue,
                    deadline=deadline,
                    on_first_sent=on_first_sent,
                    selected=selected,
                )
        process = self._output_process
        token = self._pacing_token
        try:
            normalized = text.replace("\r\n", "\n").replace("\r", "\n")
            if any(
                (ord(char) < 32 and char != "\n")
                or 0x7F <= ord(char) <= 0x9F
                or 0xD800 <= ord(char) <= 0xDFFF
                or ord(char) > 0xFFFF
                for char in normalized
            ):
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
        except BaseException:
            self._output_failed = True
            if self._begun:
                self._begun = False
                await self._cancel_and_clean(process)
            raise
        self._busy = True

        def check():
            if (
                self._closing
                or process is not self._process
                or not can_continue()
                or (deadline is not None and time.monotonic() >= deadline)
            ):
                raise KeyboardError("input_cancelled")

        self._output_check = check
        try:
            check()
            count = 0
            for index, character in enumerate(normalized):
                check()
                if selected is not None and not selected():
                    break
                if not self._begun:
                    self._begun = True
                    await self._request("begin", deadline=deadline)
                    check()
                    if selected is not None and not selected():
                        break

                def active():
                    check()
                    return True

                await self._pacer.before_send(
                    token, mapping_changed=False, active=active, deadline=deadline
                )
                check()
                if selected is not None and not selected():
                    break
                request_start = time.monotonic()
                hint = normalized[index + 1 : index + 4].split("\n", 1)[0]
                fields = {"value": character}
                if character != "\n" and hint:
                    fields["hint"] = hint
                result = await self._request("key", **fields)
                acknowledged = time.monotonic()
                if type(result.get("count")) is not int or result["count"] != 1:
                    check()
                    raise KeyboardError("injection_failed")
                sent_at = result.get("sent_at")
                if (
                    type(sent_at) not in (float, int)
                    or not request_start <= sent_at <= acknowledged
                    or not math.isfinite(sent_at)
                ):
                    check()
                    raise KeyboardError("injection_failed")
                # The worker completed this key request; target delivery is unknown.
                # Count before any callback that may synchronously cancel.
                self._acknowledged_keys += 1
                # A stop after a valid reply must still prevent another key.
                check()
                # Optional telemetry cannot turn an already successful press into
                # failure. Old workers without it still provide an INPUT RTT.
                feedback = _input_feedback(result.get("input_feedback"))
                self._pacer.sent(
                    token, mapping_changed=bool(feedback and feedback["map_changed"])
                )
                if "input_feedback" in result and feedback is None:
                    self._pacer.reset_input(token)
                else:
                    self._pacer.ack(
                        token,
                        started=request_start,
                        completed=acknowledged,
                        mapping_changed=(feedback["map_changed"] if feedback else None),
                    )
                if count == 0 and on_first_sent is not None:
                    on_first_sent(sent_at)
                count += 1
            check()
            return count
        except BaseException as error:
            self._output_failed = True
            if isinstance(error, Exception):
                try:
                    error.acknowledged_attempts = self._acknowledged_keys
                except Exception:
                    pass
            if self._begun:
                self._begun = False
                await self._cancel_and_clean(process)
            raise
        finally:
            self._busy = False

    async def aclose(self) -> None:
        if self._pacing_token is not None:
            self._pacer.invalidate(self._pacing_token)
        self._closing = True
        self._authorized = self._connected = False
        owner = self._output_owner
        try:
            if owner is not None and owner is not asyncio.current_task():
                owner.cancel()
                try:
                    await owner
                except (asyncio.CancelledError, KeyboardError):
                    pass
        finally:
            await self._close_process()

    async def _close_process(self):
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
