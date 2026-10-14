import asyncio
import json

import pytest

from inkecho.platform.keyboard import KeyboardError, KeyboardInput
from inkecho.platform.wayland_keyboard import WaylandKeyboardInput, keyboard_for_desktop


class Process:
    def __init__(self, handler=None):
        self.stdout = asyncio.StreamReader()
        self.stdin = self
        self.returncode = None
        self.requests = []
        self.handler = handler
        self.closed = asyncio.Event()

    def write(self, data):
        request = json.loads(data)
        self.requests.append(request)
        if self.handler is not None and self.handler(self, request):
            return
        self.reply(request, count=1 if request["op"] == "key" else None)
        if request["op"] == "close":
            self.close()

    def reply(self, request, **fields):
        self.stdout.feed_data(
            json.dumps({"id": request["id"], "ok": True, **fields}).encode() + b"\n"
        )

    async def drain(self):
        await asyncio.sleep(0)

    def close(self):
        if self.returncode is None:
            self.returncode = 0
            self.stdout.feed_eof()
            self.closed.set()

    async def wait(self):
        await self.closed.wait()
        return self.returncode


async def connected(handler=None):
    process = Process(handler)

    async def spawn(*_args, **_kwargs):
        return process

    inputs = WaylandKeyboardInput(spawn=spawn, timeout=0.1, cleanup_timeout=0.1)
    await inputs.connect()
    return inputs, process


def test_desktop_selection_does_not_classify_current_focus():
    assert isinstance(
        keyboard_for_desktop(
            {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}
        ),
        WaylandKeyboardInput,
    )
    assert isinstance(keyboard_for_desktop({"XDG_SESSION_TYPE": "x11"}), KeyboardInput)


def test_connect_is_non_authorizing_and_output_is_sequential_normalized():
    async def run():
        inputs, process = await connected()
        assert inputs.connected and not inputs.authorized
        assert [item["op"] for item in process.requests] == ["connect"]
        await inputs.authorize()
        assert await inputs.insert("中é\r\nΩ", lambda: True) == 4
        assert [item["value"] for item in process.requests if item["op"] == "key"] == [
            "中",
            "é",
            "\n",
            "Ω",
        ]
        await inputs.aclose()
        assert not inputs.connected and not inputs.authorized

    asyncio.run(run())


@pytest.mark.parametrize("text", ["safe😀", "safe\t", "safe\ud800", "safe\x85"])
def test_non_bmp_or_control_preflight_never_starts_map_transaction(text):
    async def run():
        inputs, process = await connected()
        await inputs.authorize()
        with pytest.raises(KeyboardError, match="unsupported_text"):
            await inputs.insert(text, lambda: True)
        assert all(item["op"] not in {"begin", "key"} for item in process.requests)
        await inputs.aclose()

    asyncio.run(run())


def test_cancel_in_flight_key_stops_tail_and_waits_for_cleanup():
    async def run():
        pressed = asyncio.Event()

        def handle(process, request):
            if request["op"] == "key":
                pressed.set()
                return True
            return False

        inputs, process = await connected(handle)
        await inputs.authorize()
        task = asyncio.create_task(inputs.insert("中文后续", lambda: True))
        await pressed.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["中"]
        assert process.requests[-1]["op"] == "cancel"
        await inputs.aclose()

    asyncio.run(run())


def test_expired_predicate_after_mapping_ack_sends_no_keys():
    async def run():
        allowed = True

        def handle(_process, request):
            nonlocal allowed
            if request["op"] == "begin":
                allowed = False
            return False

        inputs, process = await connected(handle)
        await inputs.authorize()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await inputs.insert("中文", lambda: allowed)
        assert all(r["op"] != "key" for r in process.requests)
        assert process.requests[-1]["op"] == "cancel"
        await inputs.aclose()

    asyncio.run(run())


def test_worker_eof_immediately_invalidates_live_state():
    async def run():
        inputs, process = await connected()
        await inputs.authorize()
        process.close()
        await asyncio.sleep(0)
        assert not inputs.connected and not inputs.authorized
        await inputs.aclose()

    asyncio.run(run())


def test_connect_ack_followed_by_session_closed_cannot_restore_readiness():
    async def run():
        def handle(process, request):
            if request["op"] == "connect":
                process.reply(request)
                process.stdout.feed_data(b'{"event":"session_closed"}\n')
                return True
            return False

        process = Process(handle)

        async def spawn(*_args, **_kwargs):
            return process

        inputs = WaylandKeyboardInput(spawn=spawn)
        with pytest.raises(KeyboardError, match="session_closed"):
            await inputs.connect()
        assert not inputs.connected and not inputs.authorized
        assert process.closed.is_set()

    asyncio.run(run())


def test_unknown_worker_failure_never_exposes_body():
    async def run():
        def handle(process, request):
            if request["op"] == "key":
                process.stdout.feed_data(
                    json.dumps(
                        {"id": request["id"], "ok": False, "error": "private text"}
                    ).encode()
                    + b"\n"
                )
                return True
            return False

        inputs, process = await connected(handle)
        await inputs.authorize()
        with pytest.raises(KeyboardError, match="^injection_failed$"):
            await inputs.insert("中", lambda: True)
        await inputs.aclose()

    asyncio.run(run())


def test_cancelled_authorization_does_not_accept_late_success():
    async def run():
        waiting = asyncio.Event()
        late = []

        def handle(_process, request):
            if request["op"] == "authorize":
                late.append(request)
                waiting.set()
                return True
            return False

        inputs, process = await connected(handle)
        task = asyncio.create_task(inputs.authorize())
        await waiting.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        process.reply(late[0])
        await asyncio.sleep(0)
        assert not inputs.authorized
        assert process.requests[-1]["op"] == "cancel"
        await inputs.aclose()

    asyncio.run(run())


def test_close_during_process_creation_cannot_resurrect_connection():
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        process = Process()

        async def spawn(*_args, **_kwargs):
            entered.set()
            await release.wait()
            return process

        inputs = WaylandKeyboardInput(spawn=spawn, timeout=0.1)
        task = asyncio.create_task(inputs.connect())
        await entered.wait()
        await inputs.aclose()
        release.set()
        with pytest.raises(KeyboardError, match="session_closed"):
            await task
        assert not inputs.connected and process.closed.is_set()
        assert process.requests == []

    asyncio.run(run())


def test_hung_cleanup_closes_parent_pipe_without_killing_guardian():
    async def run():
        inputs, process = await connected()
        await inputs.authorize()
        process.handler = lambda _process, request: request["op"] == "close"
        pipe_closed = False

        def eof_only():
            nonlocal pipe_closed
            pipe_closed = True

        process.close = eof_only
        inputs.cleanup_timeout = 0.01
        with pytest.raises(KeyboardError, match="cleanup_pending"):
            await inputs.aclose()
        assert pipe_closed and process.returncode is None
        assert not inputs.connected and not inputs.authorized
        # Simulate later safe restore/exit; no process-kill API is exposed by the fake.
        process.returncode = 0
        process.stdout.feed_eof()
        process.closed.set()
        await inputs._reader

    asyncio.run(run())


def test_old_reader_eof_cannot_close_replacement_worker():
    async def run():
        inputs, old = await connected()
        old_reader = inputs._reader
        old.returncode = 0  # Reaped process; old stdout EOF has not arrived yet.
        replacement = Process()

        async def spawn(*_args, **_kwargs):
            return replacement

        inputs._spawn = spawn
        await inputs.connect()
        await inputs.authorize()
        old.stdout.feed_eof()
        await old_reader
        assert inputs.connected and inputs.authorized
        assert replacement.returncode is None
        assert await inputs.insert("中", lambda: True) == 1
        await inputs.aclose()

    asyncio.run(run())


def test_deadline_is_sent_to_guardian_and_expired_finish_is_not_success():
    async def run():
        import time

        allowed = True

        def handle(_process, request):
            nonlocal allowed
            if request["op"] == "finish":
                allowed = False
            return False

        inputs, process = await connected(handle)
        await inputs.authorize()
        deadline = time.monotonic() + 30
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await inputs.insert("中", lambda: allowed, deadline=deadline)
        assert (
            next(r for r in process.requests if r["op"] == "begin")["deadline"]
            == deadline
        )
        await inputs.aclose()

    asyncio.run(run())


def test_queued_old_cleanup_does_not_cancel_a_new_generation():
    async def run():
        inputs, old = await connected()
        replacement = Process()

        def replace_before_cleanup_runs():
            inputs._process = replacement
            inputs._pending = {}
            inputs._reader = asyncio.create_task(
                inputs._read_replies(replacement, inputs._pending)
            )

        old_reader = inputs._reader
        asyncio.get_running_loop().call_soon(replace_before_cleanup_runs)
        await inputs._cancel_and_clean(old)
        await old_reader
        assert replacement.requests == []
        assert replacement.returncode is None and inputs.connected
        await inputs.aclose()

    asyncio.run(run())


def test_expiry_at_key_ack_never_finishes_as_success():
    async def run():
        allowed = True

        def handle(_process, request):
            nonlocal allowed
            if request["op"] == "key":
                allowed = False
            return False

        inputs, process = await connected(handle)
        await inputs.authorize()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await inputs.insert("中", lambda: allowed)
        assert "finish" not in [item["op"] for item in process.requests]
        assert process.requests[-1]["op"] == "cancel"
        await inputs.aclose()

    asyncio.run(run())


def test_idle_session_closed_event_invalidates_without_reauthorizing():
    async def run():
        inputs, process = await connected()
        await inputs.authorize()
        process.stdout.feed_data(b'{"event":"session_closed"}\n')
        await inputs._reader
        assert not inputs.connected and not inputs.authorized
        assert [item["op"] for item in process.requests] == ["connect", "authorize"]
        await inputs.aclose()

    asyncio.run(run())
