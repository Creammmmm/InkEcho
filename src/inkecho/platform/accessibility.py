"""Targeted AT-SPI insertion. No global key injection and no clipboard operations.

The adapter runs on the application asyncio event loop. Callers must also
invalidate their task when ``on_focus_lost`` runs. Focus notifications
permanently invalidate a captured token, even if focus later returns.
"""

import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus

ACCESSIBLE = "org.a11y.atspi.Accessible"
TEXT = "org.a11y.atspi.Text"
EDITABLE = "org.a11y.atspi.EditableText"
REGISTRY = ("org.a11y.atspi.Registry", "/org/a11y/atspi/registry")
ROOT = ("org.a11y.atspi.Registry", "/org/a11y/atspi/accessible/root")
PROPERTIES = "org.freedesktop.DBus.Properties"
FOCUSED, ACTIVE, EDITABLE_STATE, DEFUNCT = 12, 1, 7, 6


class InputUnavailable(RuntimeError):
    """A target cannot safely receive direct input."""


class UnsupportedTarget(InputUnavailable):
    """The focused application does not expose the required safe interface."""


@dataclass(frozen=True)
class AccessibleTarget:
    address: tuple[str, str]
    window: tuple[str, str]
    generation: int
    caret: int
    process_id: int | None = None


def has_state(words: list[int], state: int) -> bool:
    return len(words) > state // 32 and bool(words[state // 32] & (1 << (state % 32)))


class AccessibilityInput:
    def __init__(self, on_focus_lost: Callable[[], None] = lambda: None):
        self.on_focus_lost = on_focus_lost
        self.generation = 0
        self.target = None
        self.consumed = None
        self.bus = None
        self.inserting = False
        self._verification = None
        self._verification_requested = False

    async def connect(self) -> None:
        try:
            async with asyncio.timeout(5):
                await self._connect()
        except Exception:
            self.close()
            raise InputUnavailable("Desktop accessibility is unavailable.") from None

    async def _call(self, address, interface, member, signature="", body=None):
        async with asyncio.timeout(2):
            response = await self.bus.call(
                Message(
                    destination=address[0],
                    path=address[1],
                    interface=interface,
                    member=member,
                    signature=signature,
                    body=body or [],
                )
            )
        if response.message_type == MessageType.ERROR:
            raise InputUnavailable("The target no longer accepts accessibility input.")
        return response.body

    async def _connect(self):
        session = await MessageBus().connect()
        try:
            response = await session.call(
                Message(
                    destination="org.a11y.Bus",
                    path="/org/a11y/bus",
                    interface="org.a11y.Bus",
                    member="GetAddress",
                )
            )
            self.bus = await MessageBus(bus_address=response.body[0]).connect()
        finally:
            session.disconnect()
        self.bus.add_message_handler(self._event)
        await self._call(
            ("org.freedesktop.DBus", "/org/freedesktop/DBus"),
            "org.freedesktop.DBus",
            "AddMatch",
            "s",
            ["type='signal',interface='org.a11y.atspi.Event.Object'"],
        )
        for event in ("object:state-changed", "object:text-caret-moved"):
            await self._call(
                REGISTRY, "org.a11y.atspi.Registry", "RegisterEvent", "s", [event]
            )

    def _invalidate(self, target):
        if self.target_is_current(target):
            self.generation += 1
            self.on_focus_lost()

    def _event(self, message):
        if (
            message.message_type != MessageType.SIGNAL
            or message.interface != "org.a11y.atspi.Event.Object"
        ):
            return
        address = (message.sender, message.path)
        body = message.body
        target = self.target
        state_event = message.member == "StateChanged" and len(body) >= 2
        if target is None:
            # Discovery has no identified control yet. Keep focus transitions
            # conservative, but unrelated object destruction cannot move focus.
            if state_event and body[0] in {"focused", "active"}:
                self.generation += 1
            return
        if (
            message.member == "TextCaretMoved"
            and address == target.address
            and not self.inserting
        ):
            self._invalidate(target)
            return
        if not state_event:
            return
        state, enabled = body[:2]
        target_lost = (
            (address == target.address and state == "focused" and not enabled)
            or (address == target.window and state == "active" and not enabled)
            or (
                address in {target.address, target.window}
                and state == "defunct"
                and enabled
            )
        )
        if target_lost:
            # A later focus-gain event must never revive this generation.
            self._invalidate(target)
        elif (
            state in {"focused", "active"}
            and enabled
            and address not in {target.address, target.window}
            and self.target_is_current(target)
            and not self.inserting
            and self.consumed != target
        ):
            # Notification controls may advertise focus without taking keyboard
            # focus from the editor. Check the captured target, without a delay.
            self._verification_requested = True
            if self._verification is None or self._verification.done():
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    self._invalidate(target)
                    return
                self._verification = loop.create_task(self._verify_target(target))

    async def _verify_target(self, target):
        try:
            async with asyncio.timeout(5):
                while self._verification_requested and self.target_is_current(target):
                    self._verification_requested = False
                    valid = await self._current(target)
                    if self.inserting or self.consumed == target:
                        return
                    if not valid:
                        self._invalidate(target)
                        return
        except asyncio.CancelledError:
            raise
        except Exception:
            self._invalidate(target)
        finally:
            if self._verification is asyncio.current_task():
                self._verification = None
                self._verification_requested = False

    def _cancel_verification(self):
        if self._verification is not None:
            self._verification.cancel()
            self._verification = None
        self._verification_requested = False

    async def _state(self, address):
        return (await self._call(address, ACCESSIBLE, "GetState"))[0]

    async def _property(self, address, interface, name):
        return (await self._call(address, PROPERTIES, "Get", "ss", [interface, name]))[
            0
        ].value

    async def _external_process_id(self, address):
        # Unique bus names cannot be transferred to a different connection. Never
        # decide target ownership from Qt's possibly stale active-window cache.
        if not address[0].startswith(":"):
            raise UnsupportedTarget("The target's process could not be verified.")
        try:
            response = await self._call(
                ("org.freedesktop.DBus", "/org/freedesktop/DBus"),
                "org.freedesktop.DBus",
                "GetConnectionUnixProcessID",
                "s",
                [address[0]],
            )
            process_id = response[0]
            if type(process_id) is not int or process_id <= 0:
                raise ValueError("Invalid process identifier")
        except Exception:
            raise UnsupportedTarget(
                "The target's process could not be verified."
            ) from None
        if process_id == os.getpid():
            raise UnsupportedTarget("InkEcho cannot insert text into its own process.")
        return process_id

    async def _capture(self):
        self._cancel_verification()
        self.target = None
        self.consumed = None
        generation = self.generation
        applications = (await self._call(ROOT, ACCESSIBLE, "GetChildren"))[0]
        for app in applications:
            try:
                windows = (await self._call(tuple(app), ACCESSIBLE, "GetChildren"))[0]
                for window in windows:
                    window = tuple(window)
                    if not has_state(await self._state(window), ACTIVE):
                        continue
                    stack, visited = [window], 0
                    while stack and visited < 4096:
                        address = tuple(stack.pop())
                        visited += 1
                        states = await self._state(address)
                        if has_state(states, FOCUSED):
                            process_id = await self._external_process_id(address)
                            interfaces = (
                                await self._call(address, ACCESSIBLE, "GetInterfaces")
                            )[0]
                            role = (
                                await self._call(address, ACCESSIBLE, "GetRoleName")
                            )[0]
                            if (
                                not any(i.endswith("EditableText") for i in interfaces)
                                or role == "password text"
                            ):
                                raise UnsupportedTarget(
                                    "This control does not support safe direct input."
                                )
                            if not has_state(states, EDITABLE_STATE):
                                raise UnsupportedTarget(
                                    "The focused control is not editable."
                                )
                            caret = await self._property(address, TEXT, "CaretOffset")
                            token = AccessibleTarget(
                                address, window, generation, caret, process_id
                            )
                            if not await self._current(token):
                                raise InputUnavailable(
                                    "Focus changed while capturing the target."
                                )
                            self.target = token
                            return token
                        stack.extend(
                            (await self._call(address, ACCESSIBLE, "GetChildren"))[0]
                        )
            except UnsupportedTarget:
                raise
            except Exception:
                continue
        raise InputUnavailable("No active, focused editable target is available.")

    async def _current(self, target):
        try:
            process_id = await self._external_process_id(target.address)
            if process_id != target.process_id:
                return False
            states = await self._state(target.address)
            window = await self._state(target.window)
            caret = await self._property(target.address, TEXT, "CaretOffset")
            return (
                target.generation == self.generation
                and has_state(states, FOCUSED)
                and has_state(states, EDITABLE_STATE)
                and not has_state(states, DEFUNCT)
                and has_state(window, ACTIVE)
                and caret == target.caret
            )
        except Exception:
            return False

    async def capture_target(self) -> AccessibleTarget:
        try:
            async with asyncio.timeout(5):
                return await self._capture()
        except TimeoutError:
            raise InputUnavailable("Desktop focus discovery timed out.") from None

    def target_is_current(self, target: object) -> bool:
        return (
            isinstance(target, AccessibleTarget)
            and self.target == target
            and target.generation == self.generation
        )

    async def inject(
        self, target: AccessibleTarget, text: str, can_continue: Callable[[], bool]
    ) -> None:
        if (
            not text
            or not self.target_is_current(target)
            or self.consumed == target
            or not await self._current(target)
            or not can_continue()
        ):
            raise InputUnavailable(
                "The task was cancelled or its input target changed."
            )
        selections = (await self._call(target.address, TEXT, "GetNSelections"))[0]
        if selections:
            raise InputUnavailable(
                "Clear the text selection before starting dictation."
            )
        if not await self._current(target) or not can_continue():
            raise InputUnavailable(
                "The task was cancelled or its input target changed."
            )
        # One targeted operation cannot redirect text to a newly focused window.
        # The remote application processes an accepted call atomically; it cannot
        # be retracted after dispatch, so no automatic retry is permitted.
        self.inserting = True
        try:
            result = await self._call(
                target.address,
                EDITABLE,
                "InsertText",
                "isi",
                [target.caret, text, len(text.encode("utf-8"))],
            )
        finally:
            self.inserting = False
            self.consumed = target
        if not result[0]:
            raise InputUnavailable("The target rejected direct text input.")

    def close(self) -> None:
        self._cancel_verification()
        self.target = None
        if self.bus:
            self.bus.disconnect()
