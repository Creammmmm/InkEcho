"""Authenticated, bounded GNOME-owned bridge for the optional automatic route.

Producer dispatch is unconfirmed input, never a target receipt or replay grant.
The separately selected legacy IBus V2 mode is not implemented by this module.
"""

import asyncio
import errno
import math
import os
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus

from inkecho.platform.ibus import IBusBridgeError
from inkecho.platform.ibus_lifecycle import (
    Capability,
    LifecycleCleanupError,
    LifecycleError,
)
from inkecho.text_units import iter_text_units

SERVICE = "io.github.Creammmmm.InkEcho.IBusOwnedCandidateV5"
PATH = "/io/github/Creammmmm/InkEcho/IBusOwnedCandidateV5"
INTERFACE = "io.github.Creammmmm.InkEcho.IBusOwnedCandidateV51"


class _OwnedMessageBus(MessageBus):
    """Observe dbus-next's otherwise discarded per-message write futures.

    dbus-next's call() still reports connection and reply failures normally;
    this only consumes the separate send future that its _call() ignores.
    """

    def send(self, message):
        future = super().send(message)

        def observe(done):
            if not done.cancelled():
                done.exception()

        future.add_done_callback(observe)
        return future


class CandidateError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Client:
    def __init__(
        self,
        capability,
        *,
        bus_factory=_OwnedMessageBus,
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
        self._attempted_characters = 0
        self._neighbor_batch = False
        self._failed = self._cancelled = self._busy = False
        self._no_service_confirmed = False
        self.cleanup_failed = False

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

    @property
    def supports_neighbor_batch(self):
        return (
            self._neighbor_batch
            and self._bus is not None
            and not (self._failed or self._cancelled)
        )

    async def _negotiate_batch(self):
        reply = await self._call(
            Message(
                destination=self._owner,
                path=PATH,
                interface="org.freedesktop.DBus.Introspectable",
                member="Introspect",
            ),
            self._owner,
        )
        if (
            reply.message_type != MessageType.METHOD_RETURN
            or reply.signature != "s"
            or len(reply.body) != 1
            or not isinstance(reply.body[0], str)
            or len(reply.body[0]) > 65536
        ):
            raise CandidateError("unavailable")
        try:
            root = ET.fromstring(reply.body[0])
        except ET.ParseError:
            raise CandidateError("unavailable") from None
        interfaces = root.findall(f"interface[@name='{INTERFACE}']")
        if len(interfaces) != 1:
            raise CandidateError("unavailable")
        methods = interfaces[0].findall("method")

        def exact(name, inputs, outputs):
            selected = [x for x in methods if x.get("name") == name]
            if len(selected) != 1:
                return False
            args = selected[0].findall("arg")
            if any(x.get("direction", "in") not in {"in", "out"} for x in args):
                return False
            return [
                x.get("type") for x in args if x.get("direction", "in") == "in"
            ] == list(inputs) and [
                x.get("type") for x in args if x.get("direction") == "out"
            ] == list(outputs)

        # Require the complete bounded protocol. A complete legacy schema needs
        # an explicit upgrade; partial/malformed schemas remain unavailable.
        # Never emit via an old method while claiming a bounded task.
        bounded_advertised = any(
            method.get("name") in {"BeginLongBounded", "CommitLongBounded"}
            for method in methods
        )
        if bounded_advertised:
            if not (
                exact("BeginLongBounded", "ssut", "b")
                and exact("CommitLongBounded", "ust", "s")
                and exact("Cancel", "", "b")
            ):
                raise CandidateError("unavailable")
            return 2
        old_bounded = (
            exact("BeginBounded", "ssut", "b")
            and exact("CommitBounded", "ust", "s")
            and exact("Cancel", "", "b")
        )
        if old_bounded:
            return 1
        if any(
            method.get("name") in {"BeginBounded", "CommitBounded"}
            for method in methods
        ):
            raise CandidateError("unavailable")
        complete_legacy = exact("Cancel", "", "b") and (
            (exact("BeginBatch", "ssu", "b") and exact("CommitBatch", "us", "s"))
            or (exact("Begin", "ss", "b") and exact("Commit", "us", "s"))
        )
        if complete_legacy:
            raise CandidateError("upgrade_required")
        raise CandidateError("unavailable")

    async def begin(self, deadline=None):
        if self._bus is not None or self._cancelled:
            raise CandidateError("busy")
        try:
            if deadline is None:
                deadline = time.monotonic() + 59
            try:
                if type(deadline) not in (int, float) or not math.isfinite(deadline):
                    raise CandidateError("cancelled")
                deadline_us = math.floor(deadline * 1_000_000)
                if (
                    not 0 < deadline_us <= 2**53 - 1
                    or deadline_us <= time.monotonic() * 1_000_000
                ):
                    raise CandidateError("cancelled")
            except (OverflowError, ValueError):
                raise CandidateError("cancelled") from None
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
            self._protocol = await self._negotiate_batch()
            self._neighbor_batch = True
            # Same Linux CLOCK_MONOTONIC epoch; integer microseconds round down.
            # The first task ceiling is fixed, never renewed by later fragments.
            now_us = int(time.monotonic() * 1_000_000)
            self._deadline_us = min(
                deadline_us,
                now_us + (555_000_000 if self._protocol == 2 else 59_000_000),
            )
            if self._deadline_us <= now_us:
                raise CandidateError("cancelled")
            reply = await self._request(
                "BeginLongBounded" if self._protocol == 2 else "BeginBounded",
                "ssut",
                [self._cap.name, self._cap.token, self._protocol, self._deadline_us],
            )
            if getattr(reply, "signature", None) != "b":
                raise CandidateError("unavailable")
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
        except BaseException as error:
            try:
                await self.close()
            except Exception:
                self.cleanup_failed = True
                if not isinstance(error, asyncio.CancelledError):
                    raise CandidateError("cleanup_failed") from None
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

    async def insert(self, text, active, *, deadline=None, on_first_sent=None):
        if self._busy or self._bus is None or self._failed or self._cancelled:
            raise CandidateError("not_ready")
        if not isinstance(text, str) or any(
            (ord(c) < 32 and c not in "\n\t")
            or 0x7F <= ord(c) <= 0x9F
            or 0xD800 <= ord(c) <= 0xDFFF
            for c in text
        ):
            raise CandidateError("unsupported_text")
        # A legacy addon must never receive a known-unsafe standalone LF.
        # Validate before any request; unknown delivery never enables replay.
        if "\n" in text and (not self._neighbor_batch or text == "\n"):
            self._failed = True
            raise CandidateError("unsupported_text")
        if deadline is not None:
            try:
                valid = type(deadline) in (int, float) and math.isfinite(deadline)
                # Values beyond our fixed session ceiling do not extend it.
                if not valid:
                    raise CandidateError("cancelled")
                if deadline < self._deadline_us / 1_000_000:
                    self._deadline_us = math.floor(deadline * 1_000_000)
            except (OverflowError, ValueError):
                raise CandidateError("cancelled") from None
        if not (0 < self._deadline_us <= 2**53 - 1):
            raise CandidateError("cancelled")
        self._busy = True
        try:
            units = iter_text_units(text) if self._neighbor_batch else iter(text)
            for index, char in enumerate(units):
                if (
                    self._cancelled
                    or not active()
                    or time.monotonic() * 1_000_000 >= self._deadline_us
                ):
                    raise CandidateError("cancelled")
                try:
                    reply = await self._request(
                        "CommitLongBounded" if self._protocol == 2 else "CommitBounded",
                        "ust",
                        [
                            self._sequence,
                            char,
                            min(
                                self._deadline_us,
                                int(time.monotonic() * 1_000_000) + 2_000_000,
                            )
                            if self._protocol == 2
                            else self._deadline_us,
                        ],
                    )
                except asyncio.CancelledError:
                    self._failed = True
                    raise
                except Exception:
                    self._failed = True
                    raise CandidateError("delivery_unknown") from None
                if getattr(reply, "signature", None) != "s":
                    self._failed = True
                    raise CandidateError("delivery_unknown")
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
                self._attempted_characters += len(char)
                if index == 0 and on_first_sent is not None:
                    on_first_sent(time.monotonic())
                if (
                    self._cancelled
                    or not active()
                    or time.monotonic() * 1_000_000 >= self._deadline_us
                ):
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
        self.preflight_cleanup_failed = False

    @property
    def supports_neighbor_batch(self):
        return bool(
            self._client and getattr(self._client, "supports_neighbor_batch", False)
        )

    async def connect(self, *, expected_owner=None, deadline=None):
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
            if deadline is None:
                await client.begin()
            else:
                await client.begin(deadline=deadline)
        except asyncio.CancelledError as error:
            self.preflight_cleanup_failed |= bool(
                getattr(error, "cleanup_failed", False)
            )
            if cap is not None:
                try:
                    cap.close()
                except Exception:
                    self.preflight_cleanup_failed = True
            self.preflight_cleanup_failed |= bool(
                getattr(locals().get("client"), "cleanup_failed", False)
            )
            raise
        except Exception as error:
            if cap is not None:
                try:
                    cap.close()
                except Exception:
                    self.preflight_cleanup_failed = True
            self.preflight_cleanup_failed |= bool(
                getattr(locals().get("client"), "cleanup_failed", False)
            )
            if (
                self.preflight_cleanup_failed
                or isinstance(error, LifecycleCleanupError)
                or (
                    isinstance(error, CandidateError) and error.code == "cleanup_failed"
                )
            ):
                self.preflight_cleanup_failed = True
                raise IBusBridgeError("cleanup_failed") from None
            if isinstance(error, CandidateError) and error.code in {
                "unavailable",
                "authorization_failed",
                "untrusted_owner",
                "upgrade_required",
                "cancelled",
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
            return await client.insert(
                text, active, deadline=deadline, on_first_sent=on_first_sent
            )
        except CandidateError as error:
            raise IBusBridgeError(
                error.code,
                acknowledged_attempts=getattr(client, "_attempted_characters", 0),
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
