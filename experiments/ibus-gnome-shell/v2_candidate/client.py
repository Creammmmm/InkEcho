"""IBus Shell prototype. Not integrated or validated for production."""

import asyncio
import os
from pathlib import Path

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus

SERVICE = "io.github.Creammmmm.InkEcho.IBusCandidateV2"
PATH = "/io/github/Creammmmm/InkEcho/IBusCandidateV2"
INTERFACE = "io.github.Creammmmm.InkEcho.IBusCandidateV21"


class CandidateError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Client:
    def __init__(
        self, capability, *, bus_factory=MessageBus, timeout=3, owner_verifier=None
    ):
        self._owner_verifier = owner_verifier or self._verify_shell_owner
        self._cap = capability
        self._bus_factory = bus_factory
        self._timeout = timeout
        self._bus = self._owner = None
        self._sequence = 0
        self._failed = self._cancelled = self._busy = False

    async def _call(self, message):
        return await asyncio.wait_for(self._bus.call(message), self._timeout)

    async def _verify_shell_owner(self, owner):
        values = []
        for method in ("GetConnectionUnixUser", "GetConnectionUnixProcessID"):
            reply = await self._call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member=method,
                    signature="s",
                    body=[owner],
                )
            )
            if (
                reply.message_type != MessageType.METHOD_RETURN
                or len(reply.body) != 1
                or type(reply.body[0]) is not int
            ):
                return False
            values.append(reply.body[0])
        uid, pid = values
        if uid != os.getuid() or pid <= 0:
            return False
        try:
            exe = Path(f"/proc/{pid}/exe").resolve(strict=True)
            return exe == Path("/usr/bin/gnome-shell") and exe.stat().st_uid == 0
        except OSError:
            return False

    async def begin(self):
        if self._bus is not None or self._cancelled:
            raise CandidateError("busy")
        try:
            self._bus = await asyncio.wait_for(
                self._bus_factory().connect(), self._timeout
            )
            reply = await self._call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="GetNameOwner",
                    signature="s",
                    body=[SERVICE],
                )
            )
            if reply.message_type != MessageType.METHOD_RETURN or len(reply.body) != 1:
                raise CandidateError("unavailable")
            owner = reply.body[0]
            if not isinstance(owner, str) or not owner.startswith(":"):
                raise CandidateError("unavailable")
            if not await self._owner_verifier(owner):
                raise CandidateError("untrusted_owner")
            self._owner = owner
            reply = await self._request(
                "Begin", "ss", [self._cap.name, self._cap.token]
            )
            if (
                reply.body != [True]
                or type(reply.body[0]) is not bool
                or reply.message_type != MessageType.METHOD_RETURN
            ):
                raise CandidateError("unavailable")
        except BaseException:
            await self.close()
            raise

    async def _request(self, method, signature, body):
        return await self._call(
            Message(
                destination=self._owner,
                path=PATH,
                interface=INTERFACE,
                member=method,
                signature=signature,
                body=body,
            )
        )

    async def insert(self, text, active):
        if self._busy or self._bus is None or self._failed or self._cancelled:
            raise CandidateError("not_ready")
        if not isinstance(text, str) or any(
            (ord(c) < 32 and c not in "\n\t")
            or 0x7F <= ord(c) <= 0x9F
            or 0xD800 <= ord(c) <= 0xDFFF
            for c in text
        ):
            raise CandidateError("unsupported_text")
        self._busy = True
        try:
            for char in text:
                if self._cancelled or not active():
                    raise CandidateError("cancelled")
                try:
                    reply = await self._request("Commit", "us", [self._sequence, char])
                except asyncio.CancelledError:
                    self._failed = True
                    raise
                except Exception:
                    self._failed = True
                    raise CandidateError("delivery_unknown") from None
                if reply.message_type != MessageType.METHOD_RETURN or reply.body != [
                    "attempted"
                ]:
                    self._failed = True
                    raise CandidateError("delivery_unknown")
                self._sequence += 1
                if self._cancelled or not active():
                    raise CandidateError("cancelled")
            return len(text)
        except BaseException:
            self._failed = True
            raise
        finally:
            self._busy = False

    async def cancel(self):
        self._cancelled = True  # Invalidate locally before any async operation.
        if self._bus is not None and self._owner is not None:
            try:
                await self._request("Cancel", "", [])
            except Exception:
                pass  # Never replay a queued or unconfirmed message.

    async def close(self):
        self._cancelled = True
        if self._bus is not None:
            self._bus.disconnect()
            self._bus = None
        self._cap.close()
