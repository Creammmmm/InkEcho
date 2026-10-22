"""Offline protocol/lifecycle checks; actual desktop permission needs real tests."""

import asyncio

import pytest
from dbus_next import Message, MessageType, Variant

from inkecho.integration import APP_ID
from inkecho.platform.portal_escape import (
    INTERFACE,
    PATH,
    PortalEscapeUnavailable,
    PortalTaskEscape,
)


class Bus:
    unique_name = ":1.77"
    owner = ":1.90"

    def __init__(self, *, deny=False, saved=(), block=None, close_error=False):
        self.handlers, self.calls, self.events = [], [], []
        self.deny, self.saved, self.block, self.close_error = (
            deny,
            saved,
            block,
            close_error,
        )
        self.blocked = asyncio.Event()
        self.resume = asyncio.Event()
        self.disconnected = False
        self.session = None

    async def connect(self):
        return self

    def add_message_handler(self, callback):
        self.handlers.append(callback)

    def remove_message_handler(self, callback):
        if callback in self.handlers:
            self.handlers.remove(callback)

    def disconnect(self):
        self.events.append("disconnect")
        self.disconnected = True

    def emit(self, path, interface, member, body, signature, sender=None):
        message = Message.new_signal(path, interface, member, signature, body)
        message.sender = sender or self.owner
        for callback in list(self.handlers):
            callback(message)

    async def call(self, message):
        self.calls.append(message)
        if message.member == self.block:
            self.blocked.set()
            await self.resume.wait()
        body = []
        if message.member == "Get":
            body = [Variant("u", 1)]
        elif message.member == "GetNameOwner":
            body = [self.owner]
        elif message.member in {"CreateSession", "ListShortcuts", "BindShortcuts"}:
            options = message.body[-1]
            token = options["handle_token"].value
            request = f"{PATH}/request/1_77/{token}"
            values = {}
            status = 0
            if message.member == "CreateSession":
                self.session = (
                    f"{PATH}/session/1_77/{options['session_handle_token'].value}"
                )
                values["session_handle"] = Variant("s", self.session)
            elif message.member == "ListShortcuts":
                values["shortcuts"] = Variant("a(sa{sv})", list(self.saved))
            else:
                status = 1 if self.deny else 0
                values["shortcuts"] = Variant(
                    "a(sa{sv})",
                    [
                        [
                            "cancel-task",
                            {"trigger_description": Variant("s", "Escape drücken")},
                        ]
                    ],
                )
            asyncio.get_running_loop().call_soon(
                self.emit,
                request,
                "org.freedesktop.portal.Request",
                "Response",
                [status, values],
                "ua{sv}",
            )
            body = [request]
        elif message.member == "Close" and self.close_error:
            raise OSError("closed transport")
        return Message(
            message_type=MessageType.METHOD_RETURN, reply_serial=1, body=body
        )


def test_real_own_identity_and_task_session_binding():
    async def scenario():
        bus = Bus()
        backend = PortalTaskEscape(bus_factory=lambda: bus)
        await backend.arm(lambda: None)
        assert backend.armed and not bus.disconnected
        registered = next(call for call in bus.calls if call.member == "Register")
        assert registered.body == [APP_ID, {}]
        bound = next(call for call in bus.calls if call.member == "BindShortcuts")
        assert bound.body[1][0][1]["description"].value == "取消当前语音任务"
        assert bound.body[1][0][1]["preferred_trigger"].value == "Escape"
        assert backend.trigger_description == "Escape drücken"
        await backend.close()
        assert bus.disconnected and not backend.armed
        assert any(
            call.member == "Close" and call.path == bus.session for call in bus.calls
        )

    asyncio.run(scenario())


def test_activated_disconnects_and_cancels_in_same_loop_turn():
    async def scenario():
        bus = Bus()
        backend = PortalTaskEscape(bus_factory=lambda: bus)
        await backend.arm(lambda: bus.events.append("cancel"))
        bus.emit(
            PATH,
            INTERFACE,
            "Activated",
            [bus.session, "cancel-task", 1, {}],
            "osta{sv}",
        )
        # No await or next event-loop turn is needed to invalidate the task.
        assert bus.events == ["disconnect", "cancel"]
        assert backend.closed and not backend.armed
        bus.emit(
            PATH,
            INTERFACE,
            "Activated",
            [bus.session, "cancel-task", 2, {}],
            "osta{sv}",
        )
        assert bus.events == ["disconnect", "cancel"]

    asyncio.run(scenario())


def test_foreign_sender_session_and_shortcut_cannot_cancel():
    async def scenario():
        bus = Bus()
        cancelled = []
        backend = PortalTaskEscape(bus_factory=lambda: bus)
        await backend.arm(lambda: cancelled.append(True))
        for session, shortcut, sender in (
            ("/foreign", "cancel-task", bus.owner),
            (bus.session, "another", bus.owner),
            (bus.session, "cancel-task", ":1.999"),
        ):
            bus.emit(
                PATH,
                INTERFACE,
                "Activated",
                [session, shortcut, 1, {}],
                "osta{sv}",
                sender,
            )
        assert not cancelled and backend.armed
        await backend.close()

    asyncio.run(scenario())


def test_denied_permission_closes_session_without_callback():
    async def scenario():
        bus = Bus(deny=True)
        backend = PortalTaskEscape(bus_factory=lambda: bus)
        with pytest.raises(PortalEscapeUnavailable):
            await backend.arm(lambda: pytest.fail("denial must not cancel user work"))
        assert bus.disconnected and backend.closed
        assert any(
            call.member == "Close" and call.path == bus.session for call in bus.calls
        )

    asyncio.run(scenario())


def test_saved_unrelated_shortcut_is_not_overwritten():
    async def scenario():
        bus = Bus(saved=[["user-action", {}]])
        backend = PortalTaskEscape(bus_factory=lambda: bus)
        with pytest.raises(PortalEscapeUnavailable):
            await backend.arm(lambda: None)
        assert not any(call.member == "BindShortcuts" for call in bus.calls)
        assert bus.disconnected

    asyncio.run(scenario())


def test_terminal_during_pending_bind_disconnects_and_releases_waiter():
    async def scenario():
        bus = Bus(block="BindShortcuts")
        backend = PortalTaskEscape(bus_factory=lambda: bus)
        task = asyncio.create_task(backend.arm(lambda: pytest.fail("stale callback")))
        await bus.blocked.wait()
        backend.abort()
        assert bus.disconnected
        bus.resume.set()
        with pytest.raises(PortalEscapeUnavailable):
            await task
        assert backend.closed and not backend.armed

    asyncio.run(scenario())


def test_close_error_still_disconnects_without_retaining_binding():
    async def scenario():
        bus = Bus(close_error=True)
        backend = PortalTaskEscape(bus_factory=lambda: bus)
        await backend.arm(lambda: None)
        await backend.close()
        assert bus.disconnected and backend.closed and not backend.armed

    asyncio.run(scenario())


def test_abort_while_connecting_closes_late_connection_without_session():
    async def scenario():
        class ConnectingBus(Bus):
            async def connect(self):
                self.blocked.set()
                await self.resume.wait()
                # The transport can become ready after an earlier disconnect.
                self.disconnected = False
                return self

        bus = ConnectingBus()
        backend = PortalTaskEscape(bus_factory=lambda: bus)
        task = asyncio.create_task(backend.arm(lambda: pytest.fail("late callback")))
        await bus.blocked.wait()
        backend.abort()
        assert bus.disconnected and backend.bus is None
        bus.resume.set()
        with pytest.raises(PortalEscapeUnavailable):
            await task
        assert bus.disconnected and backend.closed
        assert not bus.calls and not bus.handlers

    asyncio.run(scenario())
