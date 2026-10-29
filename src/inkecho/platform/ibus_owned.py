"""Disabled-by-default bounded GNOME-owned context candidate.

Explicit test injection only; no installer, detector or automatic route uses this.
"""

import asyncio
import errno
import math
import os
import time
from pathlib import Path

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus

from inkecho.platform.ibus import IBusBridgeError
from inkecho.platform.ibus_lifecycle import Capability, LifecycleError

SERVICE = "io.github.Creammmmm.InkEcho.IBusOwnedCandidateV5"
PATH = "/io/github/Creammmmm/InkEcho/IBusOwnedCandidateV5"
INTERFACE = "io.github.Creammmmm.InkEcho.IBusOwnedCandidateV51"


class CandidateError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Client:
    def __init__(
        self,
        capability,
        *,
        bus_factory=MessageBus,
        timeout=3,
        owner_verifier=None,
        expected_owner=None,
    ):
        self._expected_owner = expected_owner
        self._owner_verifier = owner_verifier or self._verify_shell_owner
        self._cap = capability
        self._bus_factory = bus_factory
        self._timeout = timeout
        self._bus = self._owner = None
        self._sequence = 0
        self._failed = self._cancelled = self._busy = False
        self._no_service_confirmed = False

    async def _call(self, message, expected_sender):
        reply = await asyncio.wait_for(self._bus.call(message), self._timeout)
        if reply.sender != expected_sender:
            raise CandidateError("unavailable")
        return reply

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
                ),
                "org.freedesktop.DBus",
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
            # Retain the transport before authentication so timeouts and
            # cancellation can close a connection that never finishes setup.
            self._bus = self._bus_factory()
            await asyncio.wait_for(self._bus.connect(), self._timeout)
            reply = await self._call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="GetNameOwner",
                    signature="s",
                    body=[SERVICE],
                ),
                "org.freedesktop.DBus",
            )
            if reply.message_type != MessageType.METHOD_RETURN or len(reply.body) != 1:
                raise CandidateError("unavailable")
            owner = reply.body[0]
            if not isinstance(owner, str) or not owner.startswith(":"):
                raise CandidateError("unavailable")
            if self._expected_owner is not None and owner != self._expected_owner:
                raise CandidateError("untrusted_owner")
            if not await self._owner_verifier(owner):
                raise CandidateError("untrusted_owner")
            self._owner = owner
            reply = await self._request(
                "Begin", "ss", [self._cap.name, self._cap.token]
            )
            if reply.message_type == MessageType.METHOD_RETURN and reply.body == [
                False
            ]:
                raise CandidateError("authorization_failed")
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
            ),
            self._owner,
        )

    async def insert(self, text, active, *, on_first_sent=None):
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
            for index, char in enumerate(text):
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
                if (
                    reply.message_type == MessageType.METHOD_RETURN
                    and reply.body == ["no_service"]
                    and self._sequence == 0
                ):
                    self._failed = True
                    self._no_service_confirmed = True
                    raise CandidateError("no_service")
                if reply.message_type != MessageType.METHOD_RETURN or reply.body != [
                    "attempted"
                ]:
                    self._failed = True
                    raise CandidateError("delivery_unknown")
                self._sequence += 1
                if index == 0 and on_first_sent is not None:
                    on_first_sent(time.monotonic())
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


class IBusBridge:
    """One bridge per output task, compatible with OutputRouter's backend API."""

    def __init__(
        self, *, runtime_dir=None, capability_factory=Capability, client_factory=Client
    ):
        self._runtime_dir = runtime_dir
        self._capability_factory = capability_factory
        self._client_factory = client_factory
        self._client = None
        self._closed = False

    async def connect(self, *, expected_owner=None):
        if self._closed:
            raise IBusBridgeError("closed")
        if self._client is not None:
            return
        runtime = self._runtime_dir or os.environ.get("XDG_RUNTIME_DIR")
        if not runtime:
            raise IBusBridgeError("unavailable")
        cap = None
        try:
            cap = self._capability_factory(runtime)
            client = (
                self._client_factory(cap)
                if expected_owner is None
                else self._client_factory(cap, expected_owner=expected_owner)
            )
            await client.begin()
        except asyncio.CancelledError:
            if cap is not None:
                cap.close()
            raise
        except Exception as error:
            if cap is not None:
                cap.close()
            if isinstance(error, CandidateError) and error.code in {
                "unavailable",
                "authorization_failed",
                "untrusted_owner",
            }:
                code = error.code
            elif isinstance(error, LifecycleError) or (
                isinstance(error, OSError)
                and error.errno in {errno.EACCES, errno.EPERM}
            ):
                code = "permission_denied"
            else:
                code = "unavailable"
            raise IBusBridgeError(code) from None
        if self._closed:
            await client.close()
            raise IBusBridgeError("closed")
        self._client = client

    async def insert(self, text, can_continue, *, deadline=None, on_first_sent=None):
        if self._closed or self._client is None:
            raise IBusBridgeError("unavailable")
        if deadline is not None:
            try:
                valid_deadline = type(deadline) in (int, float) and math.isfinite(
                    deadline
                )
            except OverflowError:
                valid_deadline = False
            if not valid_deadline:
                raise IBusBridgeError("cancelled")

        def active():
            return (
                not self._closed
                and can_continue()
                and (deadline is None or time.monotonic() < deadline)
            )

        if not active():
            raise IBusBridgeError("cancelled")
        client = self._client
        try:
            return await client.insert(text, active, on_first_sent=on_first_sent)
        except CandidateError as error:
            raise IBusBridgeError(
                error.code, acknowledged_attempts=getattr(client, "_sequence", 0)
            ) from None

    async def close_after_no_service(self):
        """Disconnect only after a confirmed zero-attempt result.

        Owner loss removes the failed task in the extension; no remote Cancel
        round trip is needed and no uncertain input may take this path.
        """
        client = self._client
        if (
            self._closed
            or client is None
            or not client._no_service_confirmed
            or client._sequence != 0
            or client._busy
        ):
            raise IBusBridgeError("delivery_unknown")
        self._closed = True
        self._client = None
        try:
            await client.close()
        except Exception:
            raise IBusBridgeError("cleanup_failed") from None

    async def aclose(self):
        self._closed = True
        client, self._client = self._client, None
        if client is not None:
            try:
                await client.cancel()
            finally:
                await client.close()
