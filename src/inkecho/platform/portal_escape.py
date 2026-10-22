"""Task-lifetime GlobalShortcuts portal using InkEcho's legitimate host identity."""

import asyncio
import uuid

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus

from inkecho.integration import APP_ID

SERVICE = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
INTERFACE = "org.freedesktop.portal.GlobalShortcuts"
SHORTCUT = "cancel-task"


class PortalEscapeUnavailable(RuntimeError):
    """The desktop did not grant this task's cancellation shortcut."""


class PortalTaskEscape:
    """Never keep a binding after the task or D-Bus peer ends.

    Construct only after normal desktop identity registration. Portal setup is
    asynchronous; it must not precede or delay microphone capture. An initial
    grant can present the desktop's own configuration UI. Later grant behavior
    depends on that desktop. No persistent GNOME binding is written here.
    """

    def __init__(self, *, bus_factory=MessageBus):
        self.bus_factory = bus_factory
        self.bus = None
        self.owner = None
        self.session = None
        self.request = None
        self.response = None
        self.match = None
        self.closed = False
        self.armed = False
        self.callback = None
        self.trigger_description = None

    async def _call(self, message, timeout=3):
        if self.closed or self.bus is None:
            raise PortalEscapeUnavailable("任务已结束。")
        reply = await asyncio.wait_for(self.bus.call(message), timeout)
        if self.closed:
            raise PortalEscapeUnavailable("任务已结束。")
        if reply.message_type == MessageType.ERROR:
            raise PortalEscapeUnavailable("桌面未授权本次任务的 Escape 取消快捷键。")
        return reply

    async def _request(self, member, signature, body, token, timeout):
        peer = self.bus.unique_name[1:].replace(".", "_")
        self.request = f"{PATH}/request/{peer}/{token}"
        self.response = asyncio.get_running_loop().create_future()
        reply = await self._call(
            Message(
                destination=SERVICE,
                path=PATH,
                interface=INTERFACE,
                member=member,
                signature=signature,
                body=body,
            )
        )
        if reply.body != [self.request]:
            raise PortalEscapeUnavailable("桌面返回了无法确认的快捷键请求。")
        status, values = await asyncio.wait_for(self.response, timeout)
        self.request = None
        self.response = None
        if self.closed or status != 0:
            raise PortalEscapeUnavailable(
                "未启用全局 Escape；仍可使用当前任务的取消入口。"
            )
        return values

    def _receive(self, message):
        if (
            self.closed
            or message.message_type != MessageType.SIGNAL
            or message.sender != self.owner
        ):
            return
        if (
            message.interface == "org.freedesktop.portal.Request"
            and message.member == "Response"
            and message.path == self.request
            and self.response is not None
            and not self.response.done()
        ):
            self.response.set_result(message.body)
        elif (
            self.armed
            and message.interface == INTERFACE
            and message.member == "Activated"
            and message.path == PATH
            and len(message.body) >= 2
            and message.body[:2] == [self.session, SHORTCUT]
        ):
            callback = self.callback
            # Disconnect first: the compositor owns the session's peer lifetime.
            # No await may let transcription/output continue before cancellation.
            self.abort()
            callback()

    async def arm(self, callback):
        self.callback = callback
        try:
            bus = self.bus_factory()
            self.bus = bus
            await asyncio.wait_for(bus.connect(), 3)
            if self.closed:
                bus.disconnect()
                raise PortalEscapeUnavailable("任务已结束。")
            await self._call(
                Message(
                    destination=SERVICE,
                    path=PATH,
                    interface="org.freedesktop.DBus.Properties",
                    member="Get",
                    signature="ss",
                    body=[INTERFACE, "version"],
                )
            )
            owner = await self._call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="GetNameOwner",
                    signature="s",
                    body=[SERVICE],
                )
            )
            self.owner = owner.body[0]
            await self._call(
                Message(
                    destination=SERVICE,
                    path=PATH,
                    interface="org.freedesktop.host.portal.Registry",
                    member="Register",
                    signature="sa{sv}",
                    body=[APP_ID, {}],
                )
            )
            self.bus.add_message_handler(self._receive)
            self.match = f"type='signal',sender='{self.owner}'"
            await self._call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="AddMatch",
                    signature="s",
                    body=[self.match],
                )
            )
            token = "inkecho_cancel_" + uuid.uuid4().hex
            values = await self._request(
                "CreateSession",
                "a{sv}",
                [
                    {
                        "handle_token": Variant("s", token),
                        "session_handle_token": Variant("s", token),
                    }
                ],
                token,
                8,
            )
            expected = (
                f"{PATH}/session/{self.bus.unique_name[1:].replace('.', '_')}/{token}"
            )
            returned = values["session_handle"].value
            if returned != expected:
                raise PortalEscapeUnavailable("桌面返回了无法确认的快捷键会话。")
            self.session = returned
            token += "_list"
            saved = await self._request(
                "ListShortcuts",
                "oa{sv}",
                [self.session, {"handle_token": Variant("s", token)}],
                token,
                8,
            )
            if any(
                identifier != SHORTCUT
                for identifier, _ in saved.get(
                    "shortcuts", Variant("a(sa{sv})", [])
                ).value
            ):
                raise PortalEscapeUnavailable("已有其他 InkEcho 快捷键，保留其设置。")
            token += "_bind"
            bound = await self._request(
                "BindShortcuts",
                "oa(sa{sv})sa{sv}",
                [
                    self.session,
                    [
                        [
                            SHORTCUT,
                            {
                                "description": Variant("s", "取消当前语音任务"),
                                "preferred_trigger": Variant("s", "Escape"),
                            },
                        ]
                    ],
                    "",
                    {"handle_token": Variant("s", token)},
                ],
                token,
                180,
            )
            shortcuts = bound.get("shortcuts", Variant("a(sa{sv})", [])).value
            if len(shortcuts) != 1 or shortcuts[0][0] != SHORTCUT:
                raise PortalEscapeUnavailable("桌面没有授予取消任务快捷键。")
            # Localized display text is informational, never parsed as a key code.
            description = shortcuts[0][1].get("trigger_description")
            self.trigger_description = (
                description.value if description is not None else None
            )
            self.armed = True
        except BaseException:
            await self.close()
            raise

    def abort(self):
        """Synchronous cancellation/terminal/disposal fallback, before callbacks."""
        self.closed = True
        self.armed = False
        if self.bus is not None:
            self.bus.remove_message_handler(self._receive)
            self.bus.disconnect()
            self.bus = None
        self.session = None
        self.request = None
        if self.response is not None and not self.response.done():
            self.response.cancel()
        self.response = None

    async def close(self):
        if self.closed:
            return
        self.closed = True
        self.armed = False
        bus = self.bus
        try:
            if bus is not None:
                for path, interface in (
                    (self.request, "org.freedesktop.portal.Request"),
                    (self.session, "org.freedesktop.portal.Session"),
                ):
                    if path:
                        try:
                            await asyncio.wait_for(
                                bus.call(
                                    Message(
                                        destination=SERVICE,
                                        path=path,
                                        interface=interface,
                                        member="Close",
                                    )
                                ),
                                2,
                            )
                        except (TimeoutError, OSError, EOFError):
                            pass
        finally:
            self.abort()
