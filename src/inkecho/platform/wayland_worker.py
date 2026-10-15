"""GNOME keyboard guardian: bounded requests, no queued text, restore on EOF.

The requester sends one character and waits for its acknowledgement. A concurrent
reader marks cancellation/EOF immediately, including while a map request is in
flight. Only this process owns the session and its recovery state. No text,
credentials or map data are logged or persisted.
"""

import asyncio
import fcntl
import json
import math
import os
import signal
import sys
import time
import xml.etree.ElementTree as ET

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus

from inkecho.platform.eis import EISModifierObserver, ObserverError
from inkecho.platform.keyboard import KeyboardError
from inkecho.platform.wayland_keymap import Keymap, normalize_text

SERVICE = "org.gnome.Mutter.RemoteDesktop"
ROOT = "/org/gnome/Mutter/RemoteDesktop"
INTERFACE = SERVICE + ".Session"
# XWayland adds an input queue and client mapping notifications between the
# compositor and application. Keep each map stable before and after its key.
MAP_SETTLE_SECONDS = 0.05
RELEASE_SETTLE_SECONDS = 0.05


class MutterSession:
    """One authenticated normal D-Bus client; no fallback around permission errors."""

    def __init__(self):
        self.bus = None
        self.owner = None
        self.path = None
        self.observer = None
        self.on_closed = None
        self.closed_signal = False

    def _message(self, message):
        if (
            message.message_type == MessageType.SIGNAL
            and message.sender == self.owner
            and message.path == self.path
            and message.interface == INTERFACE
            and message.member == "Closed"
        ):
            self.closed_signal = True
            if self.on_closed:
                self.on_closed()
        return False

    async def _call(self, path, interface, member, signature="", body=None, fds=None):
        try:
            reply = await asyncio.wait_for(
                self.bus.call(
                    Message(
                        destination=self.owner,
                        path=path,
                        interface=interface,
                        member=member,
                        signature=signature,
                        body=body or [],
                        unix_fds=fds or [],
                    )
                ),
                3,
            )
        except (TimeoutError, OSError, EOFError):
            raise KeyboardError("injection_failed") from None
        if reply.message_type == MessageType.ERROR:
            if reply.error_name in (
                "org.freedesktop.DBus.Error.NameHasNoOwner",
                "org.freedesktop.DBus.Error.ServiceUnknown",
            ):
                raise KeyboardError("session_closed")
            if reply.error_name in (
                "org.freedesktop.DBus.Error.AccessDenied",
                "org.freedesktop.DBus.Error.AuthFailed",
            ):
                raise KeyboardError("permission_denied")
            raise KeyboardError("injection_failed")
        return reply

    async def connect(self):
        if self.bus:
            return
        try:
            self.bus = await asyncio.wait_for(
                MessageBus(negotiate_unix_fd=True).connect(), 3
            )
            reply = await asyncio.wait_for(
                self.bus.call(
                    Message(
                        destination="org.freedesktop.DBus",
                        path="/org/freedesktop/DBus",
                        interface="org.freedesktop.DBus",
                        member="GetNameOwner",
                        signature="s",
                        body=[SERVICE],
                    )
                ),
                3,
            )
            if reply.message_type == MessageType.ERROR:
                raise KeyboardError("display_unavailable")
            self.owner = reply.body[0]
            await self._call(
                ROOT,
                "org.freedesktop.DBus.Properties",
                "Get",
                "ss",
                [SERVICE, "Version"],
            )
        except (TimeoutError, OSError, EOFError):
            raise KeyboardError("display_unavailable") from None

    async def authorize(self, can_continue=lambda: True):
        if self.observer:
            return

        def check():
            if not can_continue():
                raise KeyboardError("input_cancelled")

        try:
            await self._authorize(check)
        except BaseException as error:
            # Disconnect even when CreateSession completed remotely but its reply
            # was cancelled before we received a path. D-Bus client ownership
            # then releases that provisional session without starting input.
            try:
                await self.close()
            except KeyboardError:
                pass
            if isinstance(error, (TimeoutError, OSError, EOFError)):
                raise KeyboardError("injection_failed") from None
            raise

    async def _authorize(self, check):
        check()
        await self.connect()
        check()
        self.path = (await self._call(ROOT, SERVICE, "CreateSession")).body[0]
        check()
        self.bus.add_message_handler(self._message)
        rule = (
            f"type='signal',sender='{self.owner}',path='{self.path}',"
            f"interface='{INTERFACE}',member='Closed'"
        )
        subscription = await asyncio.wait_for(
            self.bus.call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="AddMatch",
                    signature="s",
                    body=[rule],
                )
            ),
            3,
        )
        check()
        if subscription.message_type == MessageType.ERROR:
            raise KeyboardError("display_unavailable")
        await self._call(self.path, INTERFACE, "Start")
        check()
        capabilities = (
            (
                await self._call(
                    self.path,
                    "org.freedesktop.DBus.Properties",
                    "Get",
                    "ss",
                    [INTERFACE, "KeymapCapabilities"],
                )
            )
            .body[0]
            .value
        )
        check()
        # GNOME 50.1 advertises the property but returns an empty dictionary.
        # Validate callable interfaces too; do not index undocumented runtime data.
        if capabilities:
            types = capabilities.get("supported-keymap-types")
            formats = capabilities.get("supported-xkb-keymap-formats")
            if (
                types is None
                or formats is None
                or 0 not in types.value
                or 1 not in formats.value
            ):
                raise KeyboardError("display_unavailable")
        xml = (
            await self._call(
                self.path, "org.freedesktop.DBus.Introspectable", "Introspect"
            )
        ).body[0]
        check()
        try:
            interface = next(
                item
                for item in ET.fromstring(xml).findall("interface")
                if item.get("name") == INTERFACE
            )
            methods = {item.get("name") for item in interface.findall("method")}
        except (ET.ParseError, StopIteration):
            raise KeyboardError("display_unavailable") from None
        if (
            not {
                "SetKeymap",
                "ConnectToEIS",
                "NotifyKeyboardKeycode",
                "NotifyKeyboardKeysym",
            }
            <= methods
        ):
            raise KeyboardError("display_unavailable")
        await self._open_observer()
        check()
        await self.snapshot()
        check()

    async def _open_observer(self):
        if self.observer:
            self.observer.close()
            self.observer = None
        reply = await self._call(
            self.path,
            INTERFACE,
            "ConnectToEIS",
            "a{sv}",
            [{"device-types": Variant("u", 1)}],
        )
        fd = reply.unix_fds[reply.body[0]]
        try:
            self.observer = EISModifierObserver(fd)
        finally:
            os.close(fd)

    async def snapshot(self, *, refresh=False, retry=True):
        if not self.observer:
            if not self.path:
                raise KeyboardError("permission_required")
            await self._open_observer()
        try:
            if refresh:
                await self.observer.refresh_snapshot(timeout=3)
            for _ in range(4):
                state = await self.observer.wait_snapshot(timeout=3)
                try:
                    data = self.observer.keymap_bytes(
                        state["device_generation"], expected_revision=state["revision"]
                    )
                    return state, data
                except ObserverError as error:
                    if error.code not in {"snapshot_changed", "keymap_changed"}:
                        raise
            raise KeyboardError("mapping_changed")
        except ObserverError:
            if retry:
                # This is only a new metadata connection on the same owned
                # session, never a new authorization or another compositor.
                await self._open_observer()
                return await self.snapshot(retry=False)
            raise KeyboardError("mapping_changed") from None

    async def wait_change(self, state, timeout):
        try:
            await self.observer.wait_snapshot(
                timeout=timeout, after_revision=state["revision"]
            )
        except ObserverError:
            raise KeyboardError("keys_held") from None

    async def source(self):
        reply = await self._call(
            self.path,
            "org.freedesktop.DBus.Properties",
            "Get",
            "ss",
            [INTERFACE, "CurrentKeymap"],
        )
        return reply.body[0].value["source"].value

    async def set_map(self, data, group):
        fd = None
        try:
            fd = os.memfd_create(
                "inkecho-keymap", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING
            )
            os.write(fd, data)
            os.lseek(fd, 0, os.SEEK_SET)
            fcntl.fcntl(
                fd,
                # Linux UAPI constants may be absent in portable Python builds.
                getattr(fcntl, "F_ADD_SEALS", 1033),
                getattr(fcntl, "F_SEAL_SHRINK", 2)
                | getattr(fcntl, "F_SEAL_GROW", 4)
                | getattr(fcntl, "F_SEAL_WRITE", 8),
                # Do not F_SEAL_SEAL: Mutter 50.1 adds these same seals again.
            )
            await self._call(
                self.path,
                INTERFACE,
                "SetKeymap",
                "a{sv}",
                [
                    {
                        "keymap-type": Variant("u", 0),
                        "xkb-keymap-format": Variant("u", 1),
                        "xkb-keymap": Variant("h", 0),
                        "xkb-keymap-layout-index": Variant("u", group),
                        "lock-keymap": Variant("b", False),
                    }
                ],
                [fd],
            )
        except OSError:
            raise KeyboardError("injection_failed") from None
        finally:
            if fd is not None:
                os.close(fd)

    async def key(self, code, pressed, *, newline=False):
        await self._call(
            self.path,
            INTERFACE,
            "NotifyKeyboardKeysym" if newline else "NotifyKeyboardKeycode",
            "ub",
            [code, pressed],
        )

    async def close(self):
        if self.observer:
            self.observer.close()
            self.observer = None
        try:
            if self.path:
                await self._call(self.path, INTERFACE, "Stop")
        finally:
            self.path = None
            if self.bus:
                self.bus.disconnect()
                self.bus = None


class Guardian:
    """Transaction state independent of the requester and of any focused window."""

    def __init__(self, remote=None):
        self.remote = remote or MutterSession()
        self.map = None
        self.group = None
        self.last_confirmed = None
        self.pending_map = None
        self.modified = False
        self.pressed = None
        self.stopped = True
        self.permanent_stop = False
        self.deadline = 0.0
        self.closed_callback = None
        self.remote.on_closed = self._session_closed

    def _session_closed(self):
        # Session revocation is not compositor death. Retain recovery state.
        self.stop(permanent=True)
        if self.closed_callback:
            self.closed_callback()

    def stop(self, *, permanent=False):
        self.stopped = True
        self.permanent_stop |= permanent

    def _continue(self):
        if self.stopped or self.permanent_stop or time.monotonic() >= self.deadline:
            raise KeyboardError("input_cancelled")

    async def _idle(self, *, cleanup=False):
        deadline = asyncio.get_running_loop().time() + 3
        while True:
            state, data = await self.remote.snapshot(refresh=cleanup)
            if not cleanup:
                self._continue()
            if not state["depressed"] and not state["latched"]:
                return state, data
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise KeyboardError("cleanup_pending" if cleanup else "keys_held")
            try:
                await self.remote.wait_change(state, remaining)
            except KeyboardError:
                raise KeyboardError(
                    "cleanup_pending" if cleanup else "keys_held"
                ) from None

    async def begin(self, deadline=None):
        if self.map:
            raise KeyboardError("cleanup_pending")
        if self.permanent_stop:
            raise KeyboardError("session_closed")
        self.deadline = time.monotonic() + 60 if deadline is None else deadline
        if not isinstance(self.deadline, (int, float)) or not math.isfinite(
            self.deadline
        ):
            raise KeyboardError("input_cancelled")
        self.stopped = False
        candidate = None
        try:
            state, data = await self._idle()
            candidate = Keymap(data)
            if state["locked"] & candidate.caps_mask:
                candidate.close()
                raise KeyboardError("caps_lock")
            self._continue()
            if not 0 <= state["group"] < candidate.groups:
                candidate.close()
                raise KeyboardError("unsupported_layout")
            self.map = candidate
            self.group = state["group"]
            self.last_confirmed = data
        except BaseException:
            if candidate is not None and self.map is None:
                candidate.close()
            self.stopped = True
            raise

    async def key(self, character):
        if not self.map:
            raise KeyboardError("session_closed")
        if normalize_text(character) != character or len(character) != 1:
            raise KeyboardError("unsupported_text")
        self._continue()
        state, data = await self.remote.snapshot()
        self._continue()
        if state["depressed"] or state["latched"]:
            self.stop()
            raise KeyboardError("keys_held")
        if state["locked"] & self.map.caps_mask:
            self.stop()
            raise KeyboardError("caps_lock")
        if data != self.last_confirmed or state["group"] != self.group:
            self.stop()
            raise KeyboardError("mapping_changed")
        if self.modified and await self.remote.source() != 1:
            self.stop()
            raise KeyboardError("mapping_changed")
        self._continue()
        # The D-Bus source query may have yielded while another keyboard changed
        # modifiers. Re-read the actual map/state immediately before mutation.
        state, data = await self.remote.snapshot()
        self._continue()
        if state["depressed"] or state["latched"]:
            self.stop()
            raise KeyboardError("keys_held")
        if state["locked"] & self.map.caps_mask:
            self.stop()
            raise KeyboardError("caps_lock")
        if data != self.last_confirmed or state["group"] != self.group:
            self.stop()
            raise KeyboardError("mapping_changed")
        newline = character == "\n"
        if not newline:
            mapping = self.map.character(character)
            self.pending_map = mapping.data
            self._continue()
            await self.remote.set_map(mapping.data, self.group)
            self.modified = True
            self._continue()
            await asyncio.sleep(MAP_SETTLE_SECONDS)
            self._continue()
            state, data = await self.remote.snapshot(refresh=True)
            if data != mapping.data or state["group"] != self.group:
                raise KeyboardError("mapping_changed")
            self.last_confirmed, self.pending_map = data, None
            self._continue()
            if state["depressed"] or state["latched"]:
                raise KeyboardError("keys_held")
            if state["locked"] & self.map.caps_mask:
                raise KeyboardError("caps_lock")
            code = mapping.keycode
        else:
            code = 0xFF0D
        self._continue()
        self.pressed = (code, newline)
        try:
            await self.remote.key(code, True, newline=newline)
        finally:
            await self._release_key()
        self._continue()
        return 1

    async def _release_key(self):
        """Release owned input and let its consumers drain before another map."""
        if self.pressed is None:
            return
        code, newline = self.pressed
        try:
            await self.remote.key(code, False, newline=newline)
        finally:
            # Cleanup must retain the same pacing even after cancellation or an
            # ambiguous release failure. It sends no additional body character.
            await asyncio.sleep(RELEASE_SETTLE_SECONDS)
        self.pressed = None

    def _clear(self):
        if self.map:
            self.map.close()
        self.map = self.group = self.last_confirmed = self.pending_map = None
        self.modified = False

    async def finish(self):
        self.stop()
        if self.pressed:
            try:
                await self._release_key()
            except KeyboardError as error:
                if error.code == "session_closed":
                    self.pressed = None
                    self._clear()
                    return
                raise KeyboardError("cleanup_pending") from None
        if not self.map:
            return
        try:
            state, data = await self._idle(cleanup=True)
            source = await self.remote.source()
            # Do not restore using a pre-query idle snapshot: source() can wait.
            state, data = await self.remote.snapshot()
            if state["depressed"] or state["latched"]:
                raise KeyboardError("cleanup_pending")
            # Preserve a newer external layout; never reset Shell policy blindly.
            if source != 1:
                changed = (
                    self.modified
                    or self.pending_map is not None
                    or data != self.map.original
                )
                self._clear()
                if changed:
                    raise KeyboardError("mapping_changed")
                return
            known = {self.last_confirmed, self.pending_map, self.map.original}
            if data not in known:
                self._clear()
                raise KeyboardError("mapping_changed")
            if not 0 <= state["group"] < self.map.groups:
                raise KeyboardError("cleanup_pending")
            original = self.map.original
            if data != original:
                self.pending_map = original
                await self.remote.set_map(original, state["group"])
                after, restored = await self.remote.snapshot(refresh=True)
                if restored != original or after["group"] != state["group"]:
                    raise KeyboardError("cleanup_pending")
            self._clear()
        except KeyboardError as error:
            if error.code == "session_closed":
                # The unique compositor owner vanished; its old seat no longer exists.
                self._clear()
                return
            if (
                error.code == "mapping_changed" and self.map is not None
            ) or error.code not in {"mapping_changed", "cleanup_pending"}:
                raise KeyboardError("cleanup_pending") from None
            raise


async def serve(reader, reply, guardian=None):
    """Process protocol lines while cancellation remains independently readable."""
    guardian = guardian or Guardian()
    queue = asyncio.Queue(maxsize=1)
    closing = asyncio.Event()
    authorization_epoch = 0
    authorization_task = None

    def cancel_authorization():
        nonlocal authorization_epoch
        authorization_epoch += 1
        if authorization_task is not None:
            authorization_task.cancel()

    guardian.closed_callback = lambda: asyncio.create_task(
        reply({"event": "session_closed"})
    )

    async def read_requests():
        last_id = -1
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                if len(raw) > 4096:
                    break
                try:
                    request = json.loads(raw)
                    ident, operation = request["id"], request["op"]
                    if (
                        type(ident) is not int
                        or ident <= last_id
                        or operation
                        not in {
                            "connect",
                            "authorize",
                            "begin",
                            "key",
                            "finish",
                            "cancel",
                            "close",
                        }
                    ):
                        break
                    last_id = ident
                    if operation in {"cancel", "close"}:
                        guardian.stop(permanent=operation == "close")
                        cancel_authorization()
                    if operation == "close":
                        closing.set()
                    if queue.full():
                        await reply({"id": ident, "ok": False, "error": "busy"})
                    else:
                        request["authorization_epoch"] = authorization_epoch
                        queue.put_nowait(request)
                except (ValueError, KeyError, TypeError):
                    break
        finally:
            guardian.stop(permanent=True)
            cancel_authorization()
            closing.set()
            # A pending normal request must not keep text alive after producer EOF.
            if not queue.full():
                queue.put_nowait({"id": None, "op": "close"})

    listener = asyncio.create_task(read_requests())
    try:
        while True:
            request = await queue.get()
            ident, operation = request["id"], request["op"]
            response = {"id": ident, "ok": True}
            try:
                if (
                    operation in {"begin", "key"}
                    and request["authorization_epoch"] != authorization_epoch
                ):
                    raise KeyboardError("input_cancelled")
                if operation == "connect":
                    await guardian.remote.connect()
                elif operation == "authorize":
                    epoch = request["authorization_epoch"]
                    if epoch != authorization_epoch:
                        raise KeyboardError("input_cancelled")
                    authorization_task = asyncio.create_task(
                        guardian.remote.authorize(
                            lambda epoch=epoch: epoch == authorization_epoch
                        )
                    )
                    try:
                        await authorization_task
                    except asyncio.CancelledError:
                        raise KeyboardError("input_cancelled") from None
                    finally:
                        authorization_task = None
                elif operation == "begin":
                    await guardian.begin(request.get("deadline"))
                elif operation == "key":
                    response["count"] = await guardian.key(request.get("value"))
                else:
                    await guardian.finish()
            except (KeyboardError, ObserverError) as error:
                code = (
                    error.code
                    if isinstance(error, KeyboardError)
                    else "mapping_changed"
                )
                try:
                    await guardian.finish()
                except KeyboardError as cleanup:
                    if cleanup.code == "cleanup_pending":
                        code = cleanup.code
                response = {"id": ident, "ok": False, "error": code}
            if ident is not None:
                await reply(response)
            if closing.is_set() and queue.empty():
                break
    finally:
        guardian.stop(permanent=True)
        listener.cancel()
        await asyncio.gather(listener, return_exceptions=True)
        # A dead requester cannot authorize further text. Preserve the guardian
        # while actual held modifiers prevent restoration; each I/O remains bounded.
        while guardian.map:
            try:
                await guardian.finish()
            except KeyboardError as error:
                if error.code == "cleanup_pending":
                    await asyncio.sleep(1)
                    continue
            break
        try:
            await guardian.remote.close()
        except KeyboardError:
            pass


async def main():
    reader = asyncio.StreamReader(limit=4096)
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_running_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)
    guardian = Guardian()

    def stop_process():
        guardian.stop(permanent=True)
        reader.feed_eof()

    for name in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(name, stop_process)
    transport, output_protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout.buffer
    )
    writer = asyncio.StreamWriter(transport, output_protocol, None, loop)

    async def reply(value):
        try:
            writer.write((json.dumps(value, separators=(",", ":")) + "\n").encode())
            await asyncio.wait_for(writer.drain(), 1)
        except (TimeoutError, BrokenPipeError, OSError):
            stop_process()

    await serve(reader, reply, guardian)


if __name__ == "__main__":
    asyncio.run(main())
