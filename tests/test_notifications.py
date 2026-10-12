"""Desktop notification protocol and delayed action safety, without a desktop."""

import asyncio
from types import SimpleNamespace

from dbus_next import Message, MessageType

from inkecho.ui.notifications import PATH, SERVICE, DesktopNotifications


class Bus:
    def __init__(self):
        self.calls = []

    async def connect(self):
        return self

    def add_message_handler(self, callback):
        self.handler = callback

    async def call(self, message):
        self.calls.append(message)
        return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=[42])

    def disconnect(self):
        pass

    def signal(self, name, body):
        self.handler(Message.new_signal(PATH, SERVICE, name, "us", body))


def test_notification_replacement_and_stale_actions(monkeypatch):
    async def scenario():
        bus, actions = Bus(), []
        monkeypatch.setattr("inkecho.ui.notifications.MessageBus", lambda: bus)
        notices = DesktopNotifications(lambda *action: actions.append(action))
        assert await notices.show("Recording", recording=True, task_id="first")
        assert bus.calls[-1].body[1] == 0
        assert await notices.show("Recording", recording=True, task_id="second")
        assert bus.calls[-1].body[1] == 42
        bus.signal("ActionInvoked", [42, "stop:1"])
        assert actions == []
        bus.signal("ActionInvoked", [42, "stop:2"])
        assert actions == [("stop", "second")]
        bus.handler(
            Message.new_signal(PATH, SERVICE, "NotificationClosed", "uu", [42, 2])
        )
        assert notices.identifier == 0
        assert notices.actions == {}
        notices.close()

    asyncio.run(scenario())


def test_late_notify_reply_does_not_restore_old_actions(monkeypatch):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        actions = []

        class SlowBus(Bus):
            async def call(self, message):
                if message.member == "Notify" and not entered.is_set():
                    entered.set()
                    await release.wait()
                return await super().call(message)

        bus = SlowBus()
        monkeypatch.setattr("inkecho.ui.notifications.MessageBus", lambda: bus)
        notices = DesktopNotifications(lambda *action: actions.append(action))
        old = asyncio.create_task(notices.show("Old", recording=True, task_id="old"))
        await entered.wait()
        new = asyncio.create_task(notices.show("New", recording=True, task_id="new"))
        await asyncio.sleep(0)
        assert notices.actions == {}
        release.set()
        await asyncio.gather(old, new)
        bus.signal("ActionInvoked", [42, "cancel:1"])
        assert actions == []
        bus.signal("ActionInvoked", [42, "cancel:2"])
        assert actions == [("cancel", "new")]
        notices.close()

    asyncio.run(scenario())


def test_notification_failure_is_bounded_and_sanitized(monkeypatch):
    async def scenario():
        class FailedBus(Bus):
            async def connect(self):
                raise RuntimeError("untrusted diagnostic text")

        monkeypatch.setattr("inkecho.ui.notifications.MessageBus", FailedBus)
        notices = DesktopNotifications(lambda *_: None)
        assert not await notices.show("Unable to record")
        assert notices.bus is None

    asyncio.run(scenario())


def test_shutdown_closes_owned_notice_before_disconnecting(monkeypatch):
    async def scenario():
        class ClosingBus(Bus):
            def disconnect(self):
                assert self.calls[-1].member == "CloseNotification"
                assert self.calls[-1].body == [42]

        bus = ClosingBus()
        monkeypatch.setattr("inkecho.ui.notifications.MessageBus", lambda: bus)
        notices = DesktopNotifications(lambda *_: None)
        await notices.show("Recording", recording=True, task_id="task")
        await notices.shutdown()
        assert notices.bus is None
        assert notices.identifier == 0
        assert notices.actions == {}

    asyncio.run(scenario())
