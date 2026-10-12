"""Standard desktop notifications without mapping application windows."""

import asyncio
from collections.abc import Callable

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus

SERVICE = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"


class DesktopNotifications:
    def __init__(self, action: Callable[[str, str], None]):
        self.action = action
        self.bus = None
        self.identifier = 0
        self.actions = {}
        self.generation = 0
        self.lock = asyncio.Lock()

    async def show(
        self, message: str, *, recording=False, processing=False, task_id=None
    ) -> bool:
        """Replace our last notice; return false if the desktop service fails."""
        self.generation += 1
        generation = self.generation
        self.invalidate_actions()
        try:
            async with self.lock, asyncio.timeout(2):
                if generation != self.generation:
                    return True
                if self.bus is None:
                    self.bus = await MessageBus().connect()
                    self.bus.add_message_handler(self._receive)
                    reply = await self.bus.call(
                        Message(
                            destination="org.freedesktop.DBus",
                            path="/org/freedesktop/DBus",
                            interface="org.freedesktop.DBus",
                            member="AddMatch",
                            signature="s",
                            body=[
                                f"type='signal',sender='{SERVICE}',interface='{SERVICE}'"
                            ],
                        )
                    )
                    if reply.message_type == MessageType.ERROR:
                        raise RuntimeError("Notification subscription unavailable")
                actions = []
                callbacks = {}
                if recording and task_id:
                    token = f"stop:{generation}"
                    actions.extend([token, "结束录音"])
                    callbacks[token] = ("stop", task_id)
                if (recording or processing) and task_id:
                    token = f"cancel:{generation}"
                    actions.extend([token, "取消任务"])
                    callbacks[token] = ("cancel", task_id)
                reply = await self.bus.call(
                    Message(
                        destination=SERVICE,
                        path=PATH,
                        interface=SERVICE,
                        member="Notify",
                        signature="susssasa{sv}i",
                        body=[
                            "InkEcho",
                            self.identifier,
                            "audio-input-microphone",
                            "InkEcho · 语音输入",
                            message,
                            actions,
                            {"transient": Variant("b", True)},
                            0 if recording or processing else 10000,
                        ],
                    )
                )
                if reply.message_type == MessageType.ERROR:
                    raise RuntimeError("Notification service unavailable")
                self.identifier = int(reply.body[0])
                if generation == self.generation:
                    self.actions = callbacks
                return True
        except asyncio.CancelledError:
            raise
        except Exception:
            self.close()
            return False

    def invalidate_actions(self):
        self.actions.clear()

    async def shutdown(self):
        self.invalidate_actions()
        try:
            async with asyncio.timeout(2):
                if self.bus is not None and self.identifier:
                    await self.bus.call(
                        Message(
                            destination=SERVICE,
                            path=PATH,
                            interface=SERVICE,
                            member="CloseNotification",
                            signature="u",
                            body=[self.identifier],
                        )
                    )
        except Exception:
            pass
        finally:
            self.close()

    def _receive(self, message):
        if (
            message.message_type != MessageType.SIGNAL
            or message.interface != SERVICE
            or message.path != PATH
            or len(message.body) != 2
            or message.body[0] != self.identifier
        ):
            return
        if message.member == "ActionInvoked" and message.body[1] in self.actions:
            self.action(*self.actions[message.body[1]])
        elif message.member == "NotificationClosed":
            self.identifier = 0
            self.actions.clear()

    def close(self):
        self.generation += 1
        if self.bus is not None:
            self.bus.disconnect()
            self.bus = None
        self.identifier = 0
        self.actions.clear()
