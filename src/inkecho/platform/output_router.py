"""Task-scoped output selection. No output is retried after a send starts.

The Session uses this adapter; input-method availability and desktop support
still require independent real-desktop and package acceptance.
"""

import asyncio
import logging
import os
import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AsyncExitStack, asynccontextmanager

from inkecho.platform.fcitx5 import Fcitx5Bridge, FcitxOutputError
from inkecho.platform.framework_detection import (
    detect_system_framework,
    verified_explicit_fcitx_owner,
)
from inkecho.platform.ibus import IBusBridge, IBusBridgeError
from inkecho.platform.keyboard import KeyboardError
from inkecho.text_normalization import normalize_newlines


class OutputRouterError(KeyboardError):
    """Fixed diagnostic codes, without the text passed to a transport."""

    def __init__(
        self,
        code: str,
        *,
        acknowledged_attempts: int = 0,
        dispatch_complete: bool = False,
    ):
        self.code = code
        self.dispatch_complete = dispatch_complete is True
        self.acknowledged_attempts = (
            acknowledged_attempts
            if type(acknowledged_attempts) is int and acknowledged_attempts >= 0
            else 0
        )
        RuntimeError.__init__(self, code)


def detect_input_framework(environ: Mapping[str, str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    # Conflicting indicators are not reliable evidence of a selected framework.
    values = (
        env.get("XMODIFIERS", "").removeprefix("@im="),
        env.get("GTK_IM_MODULE", ""),
        env.get("QT_IM_MODULE", ""),
    )
    known = {value.lower() for value in values if value.lower() in {"fcitx", "ibus"}}
    return next(iter(known)) if len(known) == 1 else None


class OutputRouter:
    """One prepared backend and one exclusive output scope per task.

    Call prepare_task once per recording task and discard_task on cancellation,
    including when that task never opens an output scope. A new task must prepare
    again so that framework and configuration changes can take effect.
    """

    supports_first_sent_callback = True

    def __init__(
        self,
        keyboard,
        *,
        bridge_factory=Fcitx5Bridge,
        ibus_factory=IBusBridge,
        detector=None,
    ):
        self.keyboard = keyboard
        self._bridge_factory = bridge_factory
        self._ibus_factory = ibus_factory
        self._detector = detector or detect_input_framework
        self._system_detector = detect_system_framework
        self._explicit_fcitx_detector = verified_explicit_fcitx_owner
        self._selected = None
        self._kind = None
        self._owner = None
        self._failed = False
        self._closed = False
        self._busy = False
        self._preparing = None
        self._auto_pending = False
        self._auto_task = False
        self._scope_stack = None
        self._keyboard_error = None
        self._keyboard_parent = ""
        self._keyboard_notice = None
        self._ibus_attempted = False
        self._ibus_acknowledged_attempts = 0
        self._diagnostic_handler = None

    def set_diagnostic_handler(self, handler):
        self._diagnostic_handler = handler

    @property
    def selected(self):
        return self._kind

    @property
    def acknowledged_attempts(self):
        """Snapshot completed dispatch attempts; never a delivery receipt."""
        if self._owner is None:
            return 0
        if self._kind == "fcitx":
            count = getattr(self._selected, "_accepted", 0)
        elif self._kind == "keyboard":
            count = getattr(self._selected, "acknowledged_attempts", 0)
        elif self._kind == "ibus":
            client = getattr(self._selected, "_client", None)
            count = max(
                self._ibus_acknowledged_attempts,
                getattr(
                    client, "_attempted_characters", getattr(client, "_sequence", 0)
                ),
            )
        else:
            return 0
        return count if type(count) is int and count >= 0 else 0

    @property
    def connected(self):
        return not self._closed

    @property
    def authorized(self):
        return self._selected is not None

    @property
    def backend(self):
        return getattr(self.keyboard, "backend", None)

    async def connect(self):
        if self._closed:
            raise OutputRouterError("session_closed")

    def set_mapping_wait_reader(self, reader):
        configure = getattr(self.keyboard, "set_mapping_wait_reader", None)
        if callable(configure):
            configure(reader)

    def set_receiver_feedback_wait_reader(self, reader):
        configure = getattr(self.keyboard, "set_receiver_feedback_wait_reader", None)
        if callable(configure):
            configure(reader)

    @property
    def receiver_feedback_status(self):
        if self._owner is None:
            return "not_checked"
        if self._kind in {"fcitx", "ibus"}:
            return "unsupported"
        return getattr(self.keyboard, "receiver_feedback_status", "unavailable")

    def set_feedback_timeout_reader(self, reader):
        configure = getattr(self.keyboard, "set_feedback_timeout_reader", None)
        if callable(configure):
            configure(reader)

    async def prepare_task(
        self,
        mode: str = "auto",
        parent_window: str = "",
        *,
        on_keyboard_authorization: Callable[[], None] | None = None,
    ) -> str:
        if self._closed:
            raise OutputRouterError("session_closed")
        if (
            self._selected is not None
            or self._owner is not None
            or self._busy
            or self._preparing is not None
        ):
            raise OutputRouterError("busy")
        self._preparing = asyncio.current_task()
        try:
            return await self._prepare_task(
                mode, parent_window, on_keyboard_authorization
            )
        finally:
            self._preparing = None

    async def _prepare_task(
        self, mode: str, parent_window: str, on_keyboard_authorization
    ) -> str:
        if mode not in {"auto", "keyboard", "fcitx", "ibus"}:
            raise OutputRouterError("unsupported_output_method")
        # Neither environment variables nor bridge presence establish that the
        # current target uses that bridge. Auto remains on the known keyboard
        # path until a trustworthy target-capability check is available.
        self._keyboard_parent = parent_window
        self._keyboard_notice = on_keyboard_authorization
        framework = "keyboard" if mode == "auto" else mode
        if framework in {"fcitx", "ibus"}:
            bridge = (
                self._bridge_factory() if framework == "fcitx" else self._ibus_factory()
            )
            try:
                if framework == "fcitx":
                    owner = await self._explicit_fcitx_detector()
                    if owner is None:
                        raise FcitxOutputError("unavailable")
                    await bridge.connect(expected_owner=owner)
                    if await self._explicit_fcitx_detector() != owner:
                        raise FcitxOutputError("unavailable")
                else:
                    await bridge.connect()
            except (FcitxOutputError, IBusBridgeError) as error:
                await bridge.aclose()
                if getattr(bridge, "preflight_cleanup_failed", False):
                    self._report_cleanup_failure()
                    raise OutputRouterError(f"{framework}_cleanup_failed") from None
                allowed = {
                    "unavailable",
                    "authorization_failed",
                    "upgrade_required",
                    "composition_guard_unavailable",
                    "permission_denied",
                    "untrusted_owner",
                }
                code = error.code if error.code in allowed else "unavailable"
                raise OutputRouterError(f"{framework}_{code}") from None
            except asyncio.CancelledError:
                await self._abort_preflight_after_stop(bridge)
                raise
            except BaseException:
                await bridge.aclose()
                raise
            else:
                self._selected, self._kind = bridge, framework
                self._failed = False
                return self._kind

        self._keyboard_parent = parent_window
        self._keyboard_notice = on_keyboard_authorization
        self._selected, self._kind = self.keyboard, "keyboard"
        self._auto_pending = mode == "auto"
        self._auto_task = mode == "auto"
        self._failed = False
        if mode != "auto":
            try:
                await self._prepare_keyboard()
            except BaseException:
                self._selected = self._kind = None
                raise
        return self._kind

    @staticmethod
    def _check_task(can_continue, deadline):
        if not can_continue():
            raise OutputRouterError("input_cancelled")
        if deadline is not None and time.monotonic() >= deadline:
            raise OutputRouterError("expired")

    async def _prepare_keyboard(self, can_continue=lambda: True, deadline=None):
        if deadline is None:
            deadline = time.monotonic() + 60.0
        self._check_task(can_continue, deadline)
        task = asyncio.create_task(self._connect_keyboard())
        try:
            while not task.done():
                self._check_task(can_continue, deadline)
                timeout = (
                    0.05
                    if deadline is None
                    else min(0.05, max(0, deadline - time.monotonic()))
                )
                await asyncio.wait({task}, timeout=timeout)
            try:
                await task
            except (KeyboardError, OutputRouterError):
                raise
            except Exception:
                if not self._auto_task:
                    raise
                raise KeyboardError("display_unavailable") from None
            self._check_task(can_continue, deadline)
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _connect_keyboard(self):
        await self.keyboard.connect()
        if not self.keyboard.authorized:
            if self._keyboard_notice is not None:
                self._keyboard_notice()
            await self.keyboard.authorize(self._keyboard_parent)
        if not self.keyboard.authorized:
            raise KeyboardError("permission_required")

    async def discard_task(self):
        if self._owner is not None or self._busy or self._preparing is not None:
            raise OutputRouterError("busy")
        selected, self._selected = self._selected, None
        self._kind = None
        self._auto_pending = False
        self._auto_task = False
        self._keyboard_error = None
        self._keyboard_parent = ""
        self._keyboard_notice = None
        self._failed = False
        self._ibus_attempted = False
        self._ibus_acknowledged_attempts = 0
        self._owned_handoff_scope = False
        self._stream_replan_armed = False
        if selected is not None and selected is not self.keyboard:
            await selected.aclose()

    async def abort_task(self):
        preparing = self._preparing
        if preparing is not None and preparing is not asyncio.current_task():
            preparing.cancel()
            await asyncio.gather(preparing, return_exceptions=True)
        owner = self._owner
        if owner is not None and owner is not asyncio.current_task():
            owner.cancel()
            await asyncio.gather(owner, return_exceptions=True)
        if self._owner is None and not self._busy and self._preparing is None:
            await self.discard_task()

    @asynccontextmanager
    async def output_session(self) -> AsyncIterator[None]:
        owner = asyncio.current_task()
        if owner is None or self._owner is not None or self._busy:
            raise OutputRouterError("busy")
        if self._selected is None:
            raise OutputRouterError("output_not_prepared")
        self._owner = owner
        try:
            async with AsyncExitStack() as stack:
                self._scope_stack = stack
                if not self._auto_pending and self._selected is self.keyboard:
                    await stack.enter_async_context(self.keyboard.output_session())
                yield
                if self._failed:
                    raise OutputRouterError("output_failed")
                if self._ibus_attempted:
                    # Panel calls do not acknowledge delivery to a target.
                    raise OutputRouterError(
                        "ibus_delivery_unknown",
                        acknowledged_attempts=self._ibus_acknowledged_attempts,
                        dispatch_complete=True,
                    )
        except BaseException:
            self._failed = True
            raise
        finally:
            self._scope_stack = None
            self._owner = None
            await self.discard_task()

    @property
    def neighbor_batches_enabled(self):
        return self._kind in {"fcitx", "ibus"} and bool(
            getattr(self._selected, "supports_neighbor_batch", False)
        )

    async def prepare_stream(self, can_continue, *, deadline=None):
        # Called only after the first actual body arrives, inside output_session.
        # Recording/transcription never inspects or pins a target.
        if self._owner is not asyncio.current_task() or self._busy:
            raise OutputRouterError("busy")
        if self._selected is None or self._failed:
            raise OutputRouterError("output_not_prepared")
        self._busy = True
        try:
            self._check_task(can_continue, deadline)
            if self._auto_pending:
                await self._choose_auto(can_continue, deadline)
            self._check_task(can_continue, deadline)
            # Only this streaming consumer understands a known-zero replan.
            self._stream_replan_armed = (
                self._kind == "fcitx" and not self.neighbor_batches_enabled
            )
            return self.neighbor_batches_enabled
        except BaseException:
            # A failed or cancelled selection cannot be retried in this scope:
            # the pending flag may already have been consumed by _choose_auto.
            self._failed = True
            raise
        finally:
            self._busy = False

    async def _wait_auto_preflight(
        self, awaitable, can_continue, deadline, *, timeout=None
    ):
        """Stop preflight on task cancellation or expiry before any input."""
        task = asyncio.create_task(awaitable)
        end = time.monotonic() + timeout if timeout is not None else None
        try:
            while not task.done():
                self._check_task(can_continue, deadline)
                now = time.monotonic()
                if end is not None and now >= end:
                    raise TimeoutError
                delay = 0.05
                if end is not None:
                    delay = min(delay, max(0, end - now))
                if deadline is not None:
                    delay = min(delay, max(0, deadline - now))
                await asyncio.wait({task}, timeout=delay)
            self._check_task(can_continue, deadline)
            return task.result()
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @staticmethod
    async def _abort_preflight_bridge(bridge):
        abort = getattr(bridge, "abort_preflight", None)
        if callable(abort):
            await abort()
        else:
            await bridge.aclose()
        if getattr(bridge, "preflight_cleanup_failed", False):
            raise FcitxOutputError("cleanup_failed")

    async def _abort_preflight_after_stop(self, bridge):
        """Preserve cancellation while surfacing cleanup failure separately."""
        try:
            await self._abort_preflight_bridge(bridge)
        except Exception:
            self._report_cleanup_failure()

    def _report_cleanup_failure(self):
        try:
            if self._diagnostic_handler is None:
                raise RuntimeError("no diagnostic handler")
            self._diagnostic_handler("input_cleanup_failed")
        except Exception:
            # Never include exception text, paths, capabilities or input.
            logging.getLogger(__name__).error("input_cleanup_failed")

    async def _choose_auto(self, can_continue=lambda: True, deadline=None):
        self._auto_pending = False
        try:
            evidence = await self._wait_auto_preflight(
                self._system_detector(), can_continue, deadline, timeout=1.5
            )
        except OutputRouterError:
            raise
        except Exception:
            if getattr(self, "_owned_auto_candidate", False):
                raise OutputRouterError("input_capability_unknown") from None
            evidence = None
        framework, expected_owner = (
            evidence
            if isinstance(evidence, tuple)
            and len(evidence) == 2
            and evidence[0] in {"fcitx", "ibus"}
            and isinstance(evidence[1], str)
            and evidence[1].startswith(":")
            else (None, None)
        )
        if framework in {"fcitx", "ibus"}:
            bridge = (
                self._bridge_factory() if framework == "fcitx" else self._ibus_factory()
            )
            try:
                if framework == "fcitx":
                    pending_connect = bridge.connect(expected_owner=expected_owner)
                elif getattr(self, "_owned_auto_candidate", False):
                    pending_connect = bridge.connect(
                        expected_owner=expected_owner, deadline=deadline
                    )
                else:
                    pending_connect = bridge.connect()
                await self._wait_auto_preflight(pending_connect, can_continue, deadline)
                refreshed = await self._wait_auto_preflight(
                    self._system_detector(), can_continue, deadline, timeout=1.5
                )
                if refreshed != evidence:
                    raise RuntimeError("owner_changed")
            except OutputRouterError:
                await self._abort_preflight_after_stop(bridge)
                # A stop observed during asynchronous cleanup takes priority
                # over the earlier target/probe diagnostic. No input is retried.
                self._check_task(can_continue, deadline)
                raise
            except asyncio.CancelledError:
                await self._abort_preflight_after_stop(bridge)
                raise
            except Exception as error:
                # No Commit has been attempted in preflight. Avoid waiting on
                # an unresponsive service before the safe keyboard fallback.
                try:
                    await self._abort_preflight_bridge(bridge)
                except Exception:
                    self._report_cleanup_failure()
                    raise OutputRouterError(f"{framework}_cleanup_failed") from None
                self._check_task(can_continue, deadline)
                if (
                    framework == "fcitx"
                    and isinstance(error, FcitxOutputError)
                    and error.code
                    in {"composition_guard_unavailable", "authorization_failed"}
                ):
                    # Missing/rejected protection is not permission to bypass
                    # composition through keyboard or the optional owned bridge.
                    raise OutputRouterError("fcitx_" + error.code) from None
                if framework == "fcitx" and not getattr(
                    self, "_fcitx_keyboard_fallback_allowed", True
                ):
                    # Installation uncertainty forbids keyboard fallback, so do
                    # not connect or request authorization before refusing it.
                    raise OutputRouterError("input_capability_unknown") from None
                if framework == "ibus" and getattr(
                    self, "_owned_auto_candidate", False
                ):
                    # Only complete, authenticated legacy negotiation proves an
                    # upgrade is needed. It is never permission for fallback.
                    if (
                        isinstance(error, IBusBridgeError)
                        and error.code == "upgrade_required"
                    ):
                        raise OutputRouterError("ibus_upgrade_required") from None
                    raise OutputRouterError("input_capability_unknown") from None
            else:
                self._selected, self._kind = bridge, framework
        if self._selected is self.keyboard:
            await self._prepare_keyboard(can_continue, deadline)
            self._check_task(can_continue, deadline)
            await self._scope_stack.enter_async_context(self.keyboard.output_session())

    async def insert(
        self,
        text: str,
        can_continue: Callable[[], bool],
        *,
        deadline: float | None = None,
        on_first_sent: Callable[[float | None], None] | None = None,
    ) -> int:
        if isinstance(text, str):
            text = normalize_newlines(text)
        if self._busy or (
            self._owner is not None and self._owner is not asyncio.current_task()
        ):
            raise OutputRouterError("busy")
        if self._selected is None:
            raise OutputRouterError("output_not_prepared")
        if self._owner is None:
            async with self.output_session():
                return await self.insert(
                    text, can_continue, deadline=deadline, on_first_sent=on_first_sent
                )
        if self._failed:
            raise OutputRouterError("output_failed")
        self._busy = True
        try:
            if self._auto_pending:
                if not can_continue():
                    raise OutputRouterError("input_cancelled")
                await self._choose_auto(can_continue, deadline)
                if not can_continue():
                    raise OutputRouterError("input_cancelled")
            result = await self._selected.insert(
                text, can_continue, deadline=deadline, on_first_sent=on_first_sent
            )
            if self._kind == "ibus" and type(result) is int and result > 0:
                self._ibus_attempted = True
                self._ibus_acknowledged_attempts += result
            return result
        except FcitxOutputError as error:
            offset = error.unsent_offset
            if (
                self._auto_task
                and (
                    getattr(self, "_fcitx_keyboard_fallback_allowed", True)
                    or callable(getattr(self, "_handoff_unsent_fcitx", None))
                )
                and self._kind == "fcitx"
                and error.code in {"no_target", "ambiguous_target"}
                and not error.uncertain
                and error.accepted == 0
                and type(offset) is int
                and offset == 0
                and offset < len(text)
            ):
                try:
                    if not can_continue():
                        raise OutputRouterError("input_cancelled")
                    if not getattr(self, "_fcitx_keyboard_fallback_allowed", True):
                        return await self._handoff_unsent_fcitx(
                            error, text, can_continue, deadline, on_first_sent
                        )
                    bridge = self._selected
                    # Detach before close: real Fcitx releases local resources
                    # in its finally block, including when cleanup reports an
                    # error. Scope teardown must not close it a second time.
                    self._selected = self._kind = None
                    try:
                        await bridge.aclose()
                    except Exception:
                        self._report_cleanup_failure()
                        self._check_task(can_continue, deadline)
                        raise OutputRouterError("input_cleanup_failed") from None
                    self._check_task(can_continue, deadline)
                    self._selected, self._kind = self.keyboard, "keyboard"
                    await self._prepare_keyboard(can_continue, deadline)
                    self._check_task(can_continue, deadline)
                    await self._scope_stack.enter_async_context(
                        self.keyboard.output_session()
                    )
                    if not can_continue():
                        raise OutputRouterError("input_cancelled")
                    sent = await self.keyboard.insert(
                        text[offset:],
                        can_continue,
                        deadline=deadline,
                        on_first_sent=on_first_sent if offset == 0 else None,
                    )
                    return offset + sent
                except asyncio.CancelledError:
                    self._failed = True
                    raise
                except Exception:
                    self._failed = True
                    raise
            self._failed = True
            if (
                error.accepted > 0
                and not error.uncertain
                and error.code
                in {
                    "no_target",
                    "ambiguous_target",
                    "expired",
                    "owner_changed",
                    "composition_active",
                }
            ):
                if not can_continue():
                    raise OutputRouterError("input_cancelled") from None
                raise OutputRouterError(
                    "partial_input_failed", acknowledged_attempts=error.accepted
                ) from None
            raise OutputRouterError(
                f"{self._kind}_" + error.code, acknowledged_attempts=error.accepted
            ) from None
        except IBusBridgeError as error:
            if getattr(self, "_explicit_owned_task", False):
                self._failed = True
                self._check_task(can_continue, deadline)
                # Known zero does not authorize changing an explicitly chosen
                # route. After any body attempt, uncertainty remains terminal.
                if error.code == "no_service":
                    definitely_unsent = (
                        not self._ibus_attempted and error.acknowledged_attempts == 0
                    )
                    code = (
                        "ibus_target_unavailable"
                        if definitely_unsent
                        else "ibus_delivery_unknown"
                    )
                else:
                    code = "ibus_" + error.code
                raise OutputRouterError(
                    code,
                    acknowledged_attempts=max(
                        self._ibus_acknowledged_attempts, error.acknowledged_attempts
                    ),
                ) from None
            if getattr(self, "_owned_handoff_scope", False):
                self._failed = True
                raise OutputRouterError(
                    self._owned_failure_code(error),
                    acknowledged_attempts=max(
                        self._ibus_acknowledged_attempts, error.acknowledged_attempts
                    ),
                ) from None
            if (
                (not self._auto_task or getattr(self, "_owned_auto_scope", False))
                and self._kind == "ibus"
                and error.code == "no_service"
                and not self._ibus_attempted
                and error.acknowledged_attempts == 0
                and bool(text)
            ):
                try:
                    bridge = self._selected
                    close_unsent = getattr(bridge, "close_after_no_service", None)
                    if callable(close_unsent):
                        # Even an expired task may release a confirmed-unsent
                        # bridge immediately; no output occurs in this step.
                        try:
                            await close_unsent()
                        except Exception:
                            self._report_cleanup_failure()
                            # Do not mask a stopped task, and never send after
                            # cleanup failed even if the task is still active.
                            self._check_task(can_continue, deadline)
                            raise OutputRouterError("ibus_cleanup_failed") from None
                    else:
                        self._check_task(can_continue, deadline)
                        await bridge.aclose()
                    self._selected, self._kind = self.keyboard, "keyboard"
                    self._check_task(can_continue, deadline)
                    await self._prepare_keyboard(can_continue, deadline)
                    self._check_task(can_continue, deadline)
                    await self._scope_stack.enter_async_context(
                        self.keyboard.output_session()
                    )
                    self._check_task(can_continue, deadline)
                    return await self.keyboard.insert(
                        text,
                        can_continue,
                        deadline=deadline,
                        on_first_sent=on_first_sent,
                    )
                except BaseException:
                    self._failed = True
                    raise
            self._failed = True
            raise OutputRouterError(
                f"{self._kind}_" + error.code,
                acknowledged_attempts=max(
                    self._ibus_acknowledged_attempts, error.acknowledged_attempts
                ),
            ) from None
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def aclose(self):
        self._closed = True
        await self.abort_task()
        await self.keyboard.aclose()
