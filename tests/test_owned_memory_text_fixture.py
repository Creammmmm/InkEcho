"""Anonymous UNIX protocol controls only; these tests never create a GTK window."""

import importlib.util
import json
import socket
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts/feasibility/owned_memory_text_fixture.py"
)
SPEC = importlib.util.spec_from_file_location("owned_memory_text_fixture", PATH)
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)


def collect(channel, parent, steps=12):
    received = bytearray()
    for _ in range(steps):
        channel.step()
        while True:
            try:
                data = parent.recv(fixture.MAX_FRAME_BYTES + 4)
            except BlockingIOError:
                break
            if not data:
                break
            received.extend(data)
    replies = []
    while received:
        length = struct.unpack("!I", received[:4])[0]
        assert 0 < length <= fixture.MAX_FRAME_BYTES
        assert len(received) >= length + 4
        replies.append(json.loads(received[4 : length + 4]))
        del received[: length + 4]
    return replies


@pytest.fixture
def connection():
    parent, child = socket.socketpair()
    parent.setblocking(False)
    child.setblocking(False)
    channel = fixture.MemoryChannel(child, lambda: "", 123)
    try:
        yield parent, channel
    finally:
        channel.close()
        parent.close()


def test_ready_is_metadata_only(connection):
    parent, channel = connection
    replies = collect(channel, parent)
    assert len(replies) == 1
    assert set(replies[0]) == {"ready", "pid", "window_id"}
    assert replies[0]["ready"] is True
    assert replies[0]["pid"] > 0
    assert replies[0]["window_id"] == 123


def test_unicode_multiline_read_and_close_stay_in_socket_memory(
    connection, tmp_path, capsys, monkeypatch
):
    parent, channel = connection
    text = "仅内存 unique-private-sentinel\n中文 café e\u0301 🐈😀\n"
    channel.read_text = lambda: text
    monkeypatch.chdir(tmp_path)
    collect(channel, parent)
    parent.sendall(fixture.frame({"command": "read"}))
    assert collect(channel, parent) == [{"ok": True, "text": text}]
    parent.sendall(fixture.frame({"command": "close"}))
    assert collect(channel, parent) == [{"ok": True, "closed": True}]
    assert channel.closed
    assert list(tmp_path.iterdir()) == []
    assert capsys.readouterr() == ("", "")


def test_fragmented_header_and_body(connection):
    parent, channel = connection
    collect(channel, parent)
    request = fixture.frame({"command": "read"})
    for byte in request[:-1]:
        parent.sendall(bytes([byte]))
        assert collect(channel, parent, 2) == []
    parent.sendall(request[-1:])
    assert collect(channel, parent) == [{"ok": True, "text": ""}]
    assert not channel.closed


def test_pipelining_is_served_one_bounded_request_at_a_time(connection):
    parent, channel = connection
    collect(channel, parent)
    parent.sendall(
        fixture.frame({"command": "read"}) + fixture.frame({"command": "close"})
    )
    assert collect(channel, parent) == [
        {"ok": True, "text": ""},
        {"ok": True, "closed": True},
    ]
    assert channel.closed


@pytest.mark.parametrize("length", [0, fixture.MAX_REQUEST_BYTES + 1, 2**32 - 1])
def test_oversized_header_fails_without_receiving_body(connection, length):
    parent, channel = connection
    collect(channel, parent)
    parent.sendall(struct.pack("!I", length))
    assert collect(channel, parent) == [{"ok": False, "error": "request_too_large"}]
    assert channel.closed and channel.received == b""


@pytest.mark.parametrize(
    "payload",
    [
        b'{"command":"exec","path":"private"}',
        b'{"command":"read","extra":"private"}',
        b'{"command":"read","command":"close"}',
        b'{"command":["read"]}',
        b'"read"',
        b"{}",
        b'{"command":"read"}\xff',
        b'{"command":',
        b"\xff",
    ],
)
def test_invalid_request_is_not_echoed(connection, payload, capsys):
    parent, channel = connection
    collect(channel, parent)
    parent.sendall(struct.pack("!I", len(payload)) + payload)
    assert collect(channel, parent) == [{"ok": False, "error": "invalid_command"}]
    assert channel.closed
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("partial", [b"", b"\0\0", b'\0\0\0\x12{"'])
def test_disconnect_including_partial_frame_exits_normally(connection, partial):
    parent, channel = connection
    collect(channel, parent)
    if partial:
        parent.sendall(partial)
    parent.close()
    for _ in range(4):
        channel.step()
    assert channel.closed
    assert not channel.step()


def test_text_byte_limit_and_reply_frame_limit(connection):
    parent, channel = connection
    collect(channel, parent)
    channel.read_text = lambda: "😀" * (fixture.MAX_TEXT_BYTES // 4)
    parent.sendall(fixture.frame({"command": "read"}))
    assert collect(channel, parent)[0]["text"] == channel.read_text()
    channel.read_text = lambda: "😀" * (fixture.MAX_TEXT_BYTES // 4 + 1)
    parent.sendall(fixture.frame({"command": "read"}))
    assert collect(channel, parent) == [{"ok": False, "error": "text_too_large"}]
    assert channel.closed
    with pytest.raises(ValueError, match="^reply_too_large$"):
        fixture.frame({"text": "x" * fixture.MAX_FRAME_BYTES})


def test_arbitrary_read_exception_never_reaches_streams_or_reply(connection, capsys):
    parent, channel = connection
    collect(channel, parent)

    def broken():
        raise RuntimeError("private-body-that-must-not-be-logged")

    channel.read_text = broken
    parent.sendall(fixture.frame({"command": "read"}))
    assert collect(channel, parent) == [{"ok": False, "error": "fixture_failure"}]
    assert channel.closed
    assert capsys.readouterr() == ("", "")


def test_backpressure_does_not_read_another_request_or_drop_pending(connection):
    _parent, channel = connection
    pending = channel.pending
    original = channel.channel

    def blocked(_data):
        raise BlockingIOError

    channel.channel = SimpleNamespace(send=blocked, close=original.close)
    assert channel.step()
    assert channel.pending == pending and channel.received == b""


def test_short_write_retains_unsent_reply_bytes(connection):
    _parent, channel = connection
    pending = channel.pending
    original = channel.channel
    channel.channel = SimpleNamespace(send=lambda _data: 3, close=original.close)
    assert channel.step()
    assert channel.pending == pending[3:]


def test_startup_exception_is_silent_and_closes_owned_socket(monkeypatch, capsys):
    closed = []
    monkeypatch.setattr(
        fixture,
        "inherited_socket",
        lambda _fd: SimpleNamespace(close=lambda: closed.append(True)),
    )

    def broken(_socket):
        raise RuntimeError("private-startup-error")

    monkeypatch.setattr(fixture, "run_editor", broken)
    assert fixture.main(["--fd", "99"]) == 2
    assert closed == [True]
    assert capsys.readouterr() == ("", "")


def test_inherited_socket_accepts_only_anonymous_stream():
    parent, child = socket.socketpair()
    owned = fixture.inherited_socket(child.detach())
    try:
        assert owned.family == socket.AF_UNIX and not owned.getblocking()
    finally:
        owned.close()
        parent.close()
    parent, child = socket.socketpair(type=socket.SOCK_DGRAM)
    try:
        with pytest.raises(ValueError, match="^invalid_socket$"):
            fixture.inherited_socket(child.detach())
    finally:
        parent.close()


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--fd", "1"],
        ["--fd", "-1"],
        ["--fd", "private"],
        ["--fd", "5", "--output", "private"],
        ["--fd", "5", "--help"],
        ["--f", "5"],
        ["--fd", "5", "--address", "private"],
    ],
)
def test_invalid_cli_is_silent_and_never_starts_gtk(argv, capsys, monkeypatch):
    monkeypatch.setattr(
        fixture, "run_editor", lambda _socket: pytest.fail("GTK was started")
    )
    assert fixture.main(argv) == 2
    assert capsys.readouterr() == ("", "")


def test_cli_accepts_only_fd():
    assert fixture.arguments(["--fd", "123"]).fd == 123
