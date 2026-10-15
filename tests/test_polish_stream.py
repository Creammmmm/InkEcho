"""Real loopback HTTPS streaming and pure bounded SSE framing checks."""

import asyncio
import json
import ssl
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import httpx
import pytest

from inkecho.config import Provider
from inkecho.polish_stream import _Chat, _Events
from inkecho.providers import ProviderClient, ProviderError


def event(content=None, *, finish=None, usage=None, **delta):
    if content is not None:
        delta["content"] = content
    item = {
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
        "usage": usage,
    }
    return b"data: " + json.dumps(item, ensure_ascii=False).encode() + b"\n\n"


STOP = event(finish="stop")
DONE = b"data: [DONE]\n\n"


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    path = tmp_path_factory.mktemp("polish-stream-tls")
    certificate, key = path / "certificate.pem", path / "private.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(certificate),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    return certificate, key


@pytest.fixture
def server(certificate):
    state = SimpleNamespace(
        requests=[], replies=deque(), accepted=0, completed=False, server_errors=[]
    )

    class Server(ThreadingHTTPServer):
        daemon_threads = False

        def handle_error(self, _request, _address):
            error = sys.exception()
            state.server_errors.append(
                (type(error).__name__, getattr(error, "errno", None))
            )

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            state.accepted += 1

        def log_message(self, *_args):
            pass

        def handle(self):
            try:
                super().handle()
            except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            state.requests.append(
                {
                    "path": self.path,
                    "body": json.loads(body),
                    "authorization": self.headers.get("Authorization"),
                    "accept": self.headers.get("Accept"),
                }
            )
            reply = state.replies.popleft() if state.replies else {}
            steps = reply.get("steps", [(0, event("first")), (0, STOP + DONE)])
            self.send_response(reply.get("status", 200))
            self.send_header("Content-Type", reply.get("type", "text/event-stream"))
            self.send_header("Content-Length", str(sum(len(data) for _, data in steps)))
            if "location" in reply:
                self.send_header("Location", reply["location"])
            self.end_headers()
            try:
                for delay, data in steps:
                    time.sleep(delay)
                    self.wfile.write(data)
                    self.wfile.flush()
                state.completed = True
            except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                pass

    httpd = Server(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(*certificate)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    worker = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.02))
    worker.start()
    state.context = ssl.create_default_context(cafile=str(certificate[0]))
    state.provider = Provider(
        "test",
        "Synthetic",
        "polishing",
        "openai",
        f"https://127.0.0.1:{httpd.server_port}/v1",
        "fixture-model",
    )
    yield state
    httpd.shutdown()
    worker.join()
    httpd.server_close()
    assert state.server_errors == []


def run(server, operation, *, timeout=2):
    async def execute():
        async with httpx.AsyncClient(verify=server.context, trust_env=False) as http:
            async with ProviderClient(http=http, timeout_seconds=timeout) as client:
                return await operation(client)

    return asyncio.run(execute())


def test_actual_tls_first_delta_precedes_completion_and_preserves_unicode(server):
    server.replies.append(
        {
            "steps": [
                (0, event(reasoning_content="private-thought")),
                (0, event("哈")),
                (0.2, event("哈🙂e\u0301")),
                (0, event("尾", finish="stop", usage={"total_tokens": 9})),
                (0, DONE),
            ]
        }
    )
    deltas, observed_before_end = [], []

    async def receive(delta):
        deltas.append(delta)
        observed_before_end.append(not server.completed)

    result = run(
        server,
        lambda client: client.polish_stream(
            server.provider, "synthetic-key", "draft", "polish", receive
        ),
    )
    assert deltas == ["哈", "哈🙂e\u0301", "尾"]
    assert result.text == "哈哈🙂e\u0301尾" and result.usage.total_tokens == 9
    assert observed_before_end[0] and "private-thought" not in result.text
    assert server.requests[0] == {
        "path": "/v1/chat/completions",
        "authorization": "Bearer synthetic-key",
        "accept": "text/event-stream",
        "body": {
            "model": "fixture-model",
            "stream": True,
            "messages": [
                {"role": "system", "content": "polish"},
                {"role": "user", "content": "draft"},
            ],
        },
    }


def test_completed_sse_requests_do_not_close_shared_client(server):
    async def execute(client):
        async def receive(_delta):
            pass

        for _ in range(3):
            await client.polish_stream(server.provider, "test-key", "d", "p", receive)
        assert not client.http.is_closed

    run(server, execute)
    assert len(server.requests) == 3


def test_polishing_capability_can_exercise_actual_sse_not_buffered_chat(server):
    result = run(
        server,
        lambda client: client.test_capability(
            server.provider, "fixture-key", streaming=True
        ),
    )
    assert result.text == "first"
    assert server.requests[0]["body"]["stream"] is True
    assert len(server.requests) == 1


def test_done_returns_before_http_peer_finishes_without_emitting_tail(server):
    server.replies.append(
        {"steps": [(0, event("a") + STOP + DONE), (0.3, event("late"))]}
    )
    deltas = []

    async def receive(delta):
        deltas.append(delta)

    async def execute(client):
        result = await client.polish_stream(server.provider, "key", "d", "p", receive)
        assert result.text == "a" and not server.completed
        assert deltas == ["a"]

    run(server, execute, timeout=0.15)


def test_backpressure_awaits_callback_before_next_delta(server):
    async def execute(client):
        deltas = []
        entered, release = asyncio.Event(), asyncio.Event()

        async def receive(delta):
            deltas.append(delta)
            entered.set()
            await release.wait()

        server.replies.append({"steps": [(0, event("a") + event("b") + STOP + DONE)]})
        task = asyncio.create_task(
            client.polish_stream(server.provider, "key", "d", "p", receive)
        )
        await entered.wait()
        await asyncio.sleep(0.04)
        assert deltas == ["a"] and not task.done()
        release.set()
        assert (await task).text == "ab" and deltas == ["a", "b"]

    run(server, execute)


@pytest.mark.parametrize("during_callback", [False, True])
def test_cancel_after_partial_output_has_no_late_delta_or_replay(
    server, during_callback
):
    server.replies.append(
        {"steps": [(0, event("prefix")), (0.25, event("late") + STOP + DONE)]}
    )

    async def execute(client):
        deltas, first = [], asyncio.Event()

        async def receive(delta):
            deltas.append(delta)
            first.set()
            if during_callback:
                await asyncio.Event().wait()

        task = asyncio.create_task(
            client.polish_stream(server.provider, "key", "d", "p", receive)
        )
        await first.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0.3)
        assert deltas == ["prefix"] and len(server.requests) == 1

    run(server, execute)


def test_total_timeout_includes_callback_backpressure(server):
    async def execute(client):
        deltas = []

        async def receive(delta):
            deltas.append(delta)
            await asyncio.sleep(1)

        with pytest.raises(ProviderError) as caught:
            await client.polish_stream(server.provider, "key", "d", "p", receive)
        assert caught.value.code == "timeout" and deltas == ["first"]

    run(server, execute, timeout=0.08)
    assert len(server.requests) == 1


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "authentication"),
        (429, "rate_limit"),
        (503, "unavailable"),
        (302, "response"),
    ],
)
def test_errors_are_sanitized_without_post_retries(server, status, code):
    server.replies.append(
        {
            "status": status,
            "location": "/leak",
            "steps": [(0, b"private-key private-text")],
        }
    )

    async def execute(client):
        async def receive(_delta):
            raise AssertionError("must not emit")

        with pytest.raises(ProviderError) as caught:
            await client.polish_stream(
                server.provider, "private-key", "d", "p", receive
            )
        assert caught.value.code == code
        assert "private" not in str(caught.value)

    run(server, execute)
    assert len(server.requests) == 1


@pytest.mark.parametrize(
    "wire,content_type,expected_prefix,code",
    [
        (event("a") + STOP, "text/event-stream", "a", "response"),
        (event("a") + DONE, "text/event-stream", "a", "response"),
        (
            event("a") + event("tail", finish="length") + DONE,
            "text/event-stream",
            "a",
            "response",
        ),
        (
            event("a") + event("tail", finish="tool_calls") + DONE,
            "text/event-stream",
            "a",
            "response",
        ),
        (event("a") + b"data: not json\n\n", "text/event-stream", "a", "response"),
        (
            event("a") + b'data: {"error":"private-text"}\n\n',
            "text/event-stream",
            "a",
            "response",
        ),
        (event("a") + b"data: \xff\n\n", "text/event-stream", "a", "response"),
        (STOP + DONE, "text/event-stream", "", "empty"),
        (event(" ") + STOP + DONE, "text/event-stream", "", "empty"),
        (event("a") + STOP + DONE, "application/json", "", "response"),
    ],
)
def test_invalid_or_partial_stream_never_falls_back_or_replays(
    server, wire, content_type, expected_prefix, code
):
    server.replies.append({"steps": [(0, wire)], "type": content_type})
    deltas = []

    async def receive(delta):
        deltas.append(delta)

    async def execute(client):
        with pytest.raises(ProviderError) as caught:
            await client.polish_stream(server.provider, "key", "d", "p", receive)
        assert caught.value.code == code and "private" not in str(caught.value)

    run(server, execute)
    assert "".join(deltas) == expected_prefix and len(server.requests) == 1


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_framing_split_at_every_byte_multiline_json_bom_comments(newline):
    wire = b"\xef\xbb\xbf: keepalive" + newline + newline
    wire += b'data: {"choices": [' + newline
    wire += (
        b'data: {"delta": {"content": "'
        + "中🙂".encode()
        + b'"}, "finish_reason": "stop"}]}'
        + newline
        + newline
    )
    wire += b"data: [DONE]" + newline + newline
    events, chat, deltas = _Events(), _Chat(), []
    for byte in wire:
        for payload in events.feed(bytes([byte])):
            delta = chat.receive(payload)
            if delta:
                deltas.append(delta)
    for payload in events.feed(b"", eof=True):
        chat.receive(payload)
    assert deltas == ["中🙂"] and chat.done and chat.finished


def test_usage_only_trailing_chunk_and_repeated_text_are_not_replayed():
    events, chat, deltas = _Events(), _Chat(), []
    wire = event("哈") + event("哈") + STOP
    wire += b'data: {"choices":[],"usage":{"total_tokens":12}}\n\n' + DONE
    for payload in events.feed(wire):
        value = chat.receive(payload)
        if value:
            deltas.append(value)
    assert deltas == ["哈", "哈"] and chat.usage == {"total_tokens": 12}


def test_leading_whitespace_is_buffered_then_delivered_once():
    chat = _Chat()
    assert chat.receive(event(" \n")[6:].decode().strip()) is None
    assert chat.receive(event("中")[6:].decode().strip()) == " \n中"
    assert chat.receive(event("文")[6:].decode().strip()) == "文"
    assert "".join(chat.parts) == " \n中文"


def test_stream_identifier_is_consistent_but_is_not_a_deduplication_key():
    chat = _Chat()
    item = {"id": "same", "choices": [{"delta": {"content": "哈"}}]}
    assert chat.receive(json.dumps(item)) == chat.receive(json.dumps(item)) == "哈"
    item["id"] = "different"
    with pytest.raises(ProviderError):
        chat.receive(json.dumps(item))


def test_callback_failure_propagates_without_retry_or_next_delta(server):
    server.replies.append({"steps": [(0, event("a") + event("b") + STOP + DONE)]})

    async def execute(client):
        deltas = []

        async def receive(delta):
            deltas.append(delta)
            raise RuntimeError("delivery_refused")

        with pytest.raises(RuntimeError, match="delivery_refused"):
            await client.polish_stream(server.provider, "key", "d", "p", receive)
        assert deltas == ["a"] and len(server.requests) == 1

    run(server, execute)


@pytest.mark.parametrize("key", ["", "bad\nheader"])
def test_bad_credentials_fail_before_sse_request(server, key):
    async def execute(client):
        async def receive(_delta):
            raise AssertionError("must not emit")

        with pytest.raises(ProviderError) as caught:
            await client.polish_stream(server.provider, key, "d", "p", receive)
        assert caught.value.code == "credentials"

    run(server, execute)
    assert server.requests == []


def test_untrusted_tls_never_yields_text(server):
    async def execute():
        async def receive(_delta):
            raise AssertionError("must not emit")

        async with ProviderClient() as client:
            with pytest.raises(ProviderError) as caught:
                await client.polish_stream(server.provider, "key", "d", "p", receive)
            assert caught.value.code == "network"

    asyncio.run(execute())
    assert server.requests == []


@pytest.mark.parametrize("wire", [b"data: {}", b"data: {}\n", b"data: {}\r\n"])
def test_incomplete_sse_event_at_eof_is_not_dispatched(wire):
    events = _Events()
    assert list(events.feed(wire)) == list(events.feed(b"", eof=True)) == []


@pytest.mark.parametrize(
    "payload",
    [
        "[]",
        "null",
        "{}",
        '{"choices":{}}',
        '{"choices":[{"delta":{"content":[]}}]}',
        '{"choices":[{"index":1,"delta":{"content":"x"}}]}',
        '{"choices":[{"index":false,"delta":{"content":"x"}}]}',
        '{"choices":[{"delta":{"content":"\\ud800"}}]}',
        '{"choices":[{"delta":{"tool_calls":[{}]}}]}',
        '{"choices":[],"usage":{"total_tokens":1}}',
        '{"choices":[{},{}]}',
    ],
)
def test_invalid_chat_events_are_rejected(payload):
    with pytest.raises(ProviderError) as caught:
        _Chat().receive(payload)
    assert caught.value.code == "response"


def test_all_stream_bounds_are_enforced(monkeypatch):
    monkeypatch.setattr("inkecho.polish_stream.MAX_WIRE_BYTES", 8)
    with pytest.raises(ProviderError):
        list(_Events().feed(b":" * 9))
    monkeypatch.setattr("inkecho.polish_stream.MAX_WIRE_BYTES", 100)
    monkeypatch.setattr("inkecho.polish_stream.MAX_EVENT_BYTES", 8)
    for wire in (b"x" * 9, b"x" * 9 + b"\n", b"data:123\ndata:456\ndata:789\n\n"):
        with pytest.raises(ProviderError):
            list(_Events().feed(wire))
    monkeypatch.setattr("inkecho.polish_stream.MAX_TEXT_CHARACTERS", 1)
    with pytest.raises(ProviderError):
        _Chat().receive(event("ab")[6:].decode().strip())
