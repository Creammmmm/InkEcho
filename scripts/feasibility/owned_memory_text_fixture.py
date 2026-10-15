#!/usr/bin/python3
"""Owned GTK 3 editor; text readback uses only an inherited anonymous socket.

Launch with /usr/bin/python3 and --fd N (subprocess pass_fds). Messages are a
four-byte big-endian byte length followed by UTF-8 JSON. The first reply is
{ready, pid, window_id}; X11 supplies an XID, native Wayland supplies null.
Requests are exactly {"command":"read"} or {"command":"close"}. Replies are
{ok:true,text:...}, {ok:true,closed:true}, or {ok:false,error:fixed_code}.
Neither this module nor its protocol writes text to files or process streams.
"""

import argparse
import json
import os
import socket
import struct
from collections.abc import Callable

MAX_REQUEST_BYTES = 128
MAX_TEXT_BYTES = 32768
MAX_FRAME_BYTES = 65536
POLL_MS = 10


def frame(value: dict) -> bytes:
    """Encode one bounded JSON reply, without exposing its content on errors."""
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    if not 0 < len(payload) <= MAX_FRAME_BYTES:
        raise ValueError("reply_too_large")
    return struct.pack("!I", len(payload)) + payload


def unique_object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("invalid_command")
        result[key] = value
    return result


def parse_command(payload: bytes) -> str:
    """Accept only the two fixed commands; never echo invalid request data."""
    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("invalid_command") from None
    if (
        not isinstance(value, dict)
        or set(value) != {"command"}
        or value["command"] not in ("read", "close")
    ):
        raise ValueError("invalid_command")
    return value["command"]


def inherited_socket(fd: int) -> socket.socket:
    """Take ownership only of a connected, unnamed AF_UNIX stream socket."""
    channel = socket.socket(fileno=fd)
    try:
        if (
            channel.family != socket.AF_UNIX
            or channel.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE)
            != socket.SOCK_STREAM
            or channel.getsockname() not in ("", b"")
            or channel.getpeername() not in ("", b"")
        ):
            raise ValueError("invalid_socket")
        channel.setblocking(False)
        return channel
    except Exception:
        channel.close()
        raise ValueError("invalid_socket") from None


class MemoryChannel:
    """Bounded, nonblocking single-request protocol, polled by the GTK thread."""

    def __init__(
        self,
        channel: socket.socket,
        read_text: Callable[[], str],
        window_id: int | None,
    ) -> None:
        self.channel = channel
        self.read_text = read_text
        self.received = bytearray()
        self.expected: int | None = None
        self.pending = frame(
            {"ready": True, "pid": os.getpid(), "window_id": window_id}
        )
        self.closing = False
        self.closed = False

    def close(self) -> None:
        if not self.closed:
            self.channel.close()
            self.closed = True
        self.received.clear()
        self.pending = b""

    def fail(self, code: str) -> None:
        self.pending = frame({"ok": False, "error": code})
        self.closing = True

    def step(self) -> bool:
        """Advance without blocking; False means close/EOF/protocol failure."""
        if self.closed:
            return False
        try:
            if self.pending:
                sent = self.channel.send(self.pending)
                if sent == 0:
                    self.close()
                    return False
                self.pending = self.pending[sent:]
                return True
            if self.closing:
                self.close()
                return False
            needed = (4 if self.expected is None else self.expected) - len(
                self.received
            )
            chunk = self.channel.recv(needed)
            if not chunk:
                self.close()
                return False
            self.received.extend(chunk)
            if len(self.received) != (4 if self.expected is None else self.expected):
                return True
            if self.expected is None:
                self.expected = struct.unpack("!I", self.received)[0]
                self.received.clear()
                if not 0 < self.expected <= MAX_REQUEST_BYTES:
                    self.fail("request_too_large")
                return True
            try:
                command = parse_command(bytes(self.received))
            except ValueError:
                self.fail("invalid_command")
                return True
            finally:
                self.received.clear()
                self.expected = None
            if command == "close":
                self.pending = frame({"ok": True, "closed": True})
                self.closing = True
                return True
            text = self.read_text()
            if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_TEXT_BYTES:
                self.fail("text_too_large")
            else:
                self.pending = frame({"ok": True, "text": text})
            return True
        except BlockingIOError:
            return True
        except (BrokenPipeError, ConnectionResetError):
            self.close()
            return False
        except OSError:
            self.close()
            return False
        except Exception:
            # A GTK/Python exception might contain the buffer: send no details.
            self.fail("fixture_failure")
            return True


class PrivateParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError("invalid_arguments")


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = PrivateParser(description=__doc__, allow_abbrev=False, add_help=False)
    parser.add_argument("--fd", type=int, required=True)
    args = parser.parse_args(argv)
    if args.fd < 3:
        raise ValueError("invalid_arguments")
    return args


def run_editor(channel: socket.socket) -> int:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    window = Gtk.Window(title="InkEcho owned memory editor")
    window.set_default_size(640, 360)
    widget = Gtk.TextView()
    buffer = widget.get_buffer()

    def read_text() -> str:
        if buffer.get_char_count() > MAX_TEXT_BYTES:
            raise ValueError("text_too_large")
        return buffer.get_text(*buffer.get_bounds(), True)

    window.add(widget)
    window.show_all()
    widget.grab_focus()
    surface = window.get_window()
    window_id = None
    if surface.get_display().__gtype__.name == "GdkX11Display":
        gi.require_version("GdkX11", "3.0")
        from gi.repository import GdkX11

        window_id = GdkX11.X11Window.get_xid(surface)
    protocol = MemoryChannel(channel, read_text, window_id)

    def poll() -> bool:
        if protocol.step():
            return True
        Gtk.main_quit()
        return False

    def destroyed(*_args) -> None:
        protocol.close()
        if Gtk.main_level():
            Gtk.main_quit()

    window.connect("destroy", destroyed)
    source = GLib.timeout_add(POLL_MS, poll)
    try:
        Gtk.main()
    finally:
        if not protocol.closed:
            GLib.source_remove(source)
        protocol.close()
        window.destroy()
    return 0


def main(argv: list[str] | None = None) -> int:
    channel = None
    try:
        args = arguments(argv)
        channel = inherited_socket(args.fd)
        return run_editor(channel)
    except Exception:
        # No traceback or arbitrary argument/exception text reaches the streams.
        return 2
    finally:
        if channel is not None:
            channel.close()


if __name__ == "__main__":
    raise SystemExit(main())
