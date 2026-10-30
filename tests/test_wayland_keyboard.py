import asyncio
import json
import time

import pytest

from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
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
        if request["op"] == "key" and "sent_at" not in fields:
            fields["sent_at"] = time.monotonic()
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


async def connected(handler=None, *, pacer=None):
    process = Process(handler)

    async def spawn(*_args, **_kwargs):
        return process

    inputs = WaylandKeyboardInput(
        spawn=spawn, timeout=0.1, cleanup_timeout=0.1, pacer=pacer
    )
    await inputs.connect()
    return inputs, process


def test_desktop_selection_does_not_classify_current_focus(monkeypatch):
    def forbidden(*_args):
        pytest.fail("desktop selection must not connect or classify focus")

    monkeypatch.setattr(HybridKeyboardInput, "_x_selected", forbidden)
    monkeypatch.setattr(KeyboardInput, "connect", forbidden)
    monkeypatch.setattr(WaylandKeyboardInput, "connect", forbidden)
    assert isinstance(
        keyboard_for_desktop(
            {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}
        ),
        HybridKeyboardInput,
    )
    assert isinstance(keyboard_for_desktop({"XDG_SESSION_TYPE": "x11"}), KeyboardInput)


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "KDE"},
        {"XDG_SESSION_TYPE": "x11", "XDG_CURRENT_DESKTOP": "GNOME"},
    ],
)
def test_other_desktops_keep_x11_adapter(environ):
    assert type(keyboard_for_desktop(environ)) is KeyboardInput


def test_only_explicit_xorg_uses_global_xtest():
    from inkecho.platform.keyboard import _XDriver, _XTestDriver

    assert keyboard_for_desktop({"XDG_SESSION_TYPE": "x11"})._factory is _XTestDriver
    assert keyboard_for_desktop({})._factory is _XDriver
    assert (
        keyboard_for_desktop(
            {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "KDE"}
        )._factory
        is _XDriver
    )


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


def test_unsupported_authorization_is_reported_after_clean_cancellation():
    async def run():
        def handle(process, request):
            if request["op"] == "authorize":
                process.stdout.feed_data(
                    json.dumps(
                        {
                            "id": request["id"],
                            "ok": False,
                            "error": "unsupported_compositor",
                        }
                    ).encode()
                    + b"\n"
                )
                return True
            return False

        inputs, process = await connected(handle)
        with pytest.raises(KeyboardError, match="unsupported_compositor"):
            await inputs.authorize()
        assert process.requests[-1]["op"] == "cancel"
        assert not inputs.authorized
        await inputs.aclose()

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


@pytest.mark.parametrize(
    "sent_at", [None, True, float("nan"), float("inf"), "1", 0, 1e99]
)
def test_invalid_worker_press_timestamp_rejected_before_callback(sent_at):
    async def run():
        def handle(process, request):
            if request["op"] == "key":
                process.reply(request, count=1, sent_at=sent_at)
                return True
            return False

        inputs, process = await connected(handle)
        await inputs.authorize()
        observed = []
        with pytest.raises(KeyboardError, match="injection_failed"):
            await inputs.insert("中文", lambda: True, on_first_sent=observed.append)
        assert observed == []
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["中"]
        assert process.requests[-1]["op"] == "cancel"
        await inputs.aclose()

    asyncio.run(run())


def test_first_sent_callback_uses_worker_press_not_delayed_ack():
    async def run():
        sent = []

        def handle(process, request):
            if request["op"] == "key":
                stamp = time.monotonic()
                sent.append(stamp)
                asyncio.get_running_loop().call_later(
                    0.02, lambda: process.reply(request, count=1, sent_at=stamp)
                )
                return True
            return False

        inputs, _ = await connected(handle)
        await inputs.authorize()
        observed = []

        def first(stamp):
            assert time.monotonic() - stamp >= 0.015
            observed.append(stamp)

        assert inputs.supports_first_sent_callback
        assert await inputs.insert("中文", lambda: True, on_first_sent=first) == 2
        assert observed == sent[:1]
        await inputs.aclose()

    asyncio.run(run())


def test_first_sent_callback_failure_cleans_worker_and_sends_no_tail():
    async def run():
        inputs, process = await connected()
        await inputs.authorize()

        def failed(_stamp):
            raise RuntimeError("fixture callback failed")

        with pytest.raises(RuntimeError, match="fixture callback failed"):
            await inputs.insert("中文", lambda: True, on_first_sent=failed)
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["中"]
        assert process.requests[-1]["op"] == "cancel"
        await inputs.aclose()

    asyncio.run(run())


def test_private_prefix_finishes_without_sending_unselected_tail():
    async def run():
        inputs, process = await connected()
        await inputs.authorize()

        def selected():
            return not any(item["op"] == "key" for item in process.requests)

        assert await inputs._insert_prefix("中ab", lambda: True, selected=selected) == 1
        assert [item["value"] for item in process.requests if item["op"] == "key"] == [
            "中"
        ]
        assert [item["op"] for item in process.requests].count("begin") == 1
        assert [item["op"] for item in process.requests].count("finish") == 1
        assert not any(item["op"] == "cancel" for item in process.requests)
        await inputs.aclose()

    asyncio.run(run())


def test_output_scope_is_lazy_and_reuses_transaction_across_fragments():
    async def run():
        inputs, process = await connected()
        await inputs.authorize()
        async with inputs.output_session():
            assert await inputs.insert("", lambda: True) == 0
        assert not any(r["op"] == "begin" for r in process.requests)
        callbacks = []
        async with inputs.output_session():
            assert (
                await inputs.insert("中", lambda: True, on_first_sent=callbacks.append)
                == 1
            )
            await asyncio.sleep(0)
            assert (
                await inputs.insert("文", lambda: True, on_first_sent=callbacks.append)
                == 1
            )
            assert not any(r["op"] == "finish" for r in process.requests)
        assert [r["op"] for r in process.requests].count("begin") == 1
        assert [r["op"] for r in process.requests].count("finish") == 1
        assert len(callbacks) == 2
        await inputs.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["preflight", "deadline", "callback"])
def test_failed_owner_scope_cannot_resume_after_swallowed_error(failure):
    async def run():
        inputs, process = await connected()
        await inputs.authorize()
        deadline = time.monotonic() + 20
        with pytest.raises(KeyboardError, match="injection_failed"):
            async with inputs.output_session():
                await inputs.insert("中", lambda: True, deadline=deadline)
                with pytest.raises((KeyboardError, ValueError)):
                    if failure == "preflight":
                        await inputs.insert("😀", lambda: True)
                    elif failure == "deadline":
                        await inputs.insert("a", lambda: True, deadline=deadline + 1)
                    else:

                        def fail(_at):
                            raise ValueError("synthetic_callback")

                        await inputs.insert("a", lambda: True, on_first_sent=fail)
                count = sum(r["op"] == "key" for r in process.requests)
                with pytest.raises(KeyboardError, match="input_cancelled"):
                    await inputs.insert("tail", lambda: True)
                assert sum(r["op"] == "key" for r in process.requests) == count
        assert sum(r["op"] == "cancel" for r in process.requests) == 1
        await inputs.aclose()

    asyncio.run(run())


def test_foreign_busy_does_not_poison_idle_scope_and_close_cancels_owner():
    async def run():
        inputs, process = await connected()
        await inputs.authorize()
        ready = asyncio.Event()
        resume = asyncio.Event()

        async def owner():
            async with inputs.output_session():
                await inputs.insert("中", lambda: True)
                ready.set()
                await resume.wait()
                await inputs.insert("文", lambda: True)
                await asyncio.Event().wait()

        task = asyncio.create_task(owner())
        await ready.wait()
        with pytest.raises(KeyboardError, match="busy"):
            await inputs.insert("foreign", lambda: True)
        resume.set()
        while sum(r["op"] == "key" for r in process.requests) < 2:
            await asyncio.sleep(0)
        await inputs.aclose()
        assert task.cancelled()
        assert sum(r["op"] == "cancel" for r in process.requests) == 1
        assert process.returncode == 0

    asyncio.run(run())


def test_begin_yield_reclassifies_before_first_key():
    async def run():
        selected = True

        def handler(_process, request):
            nonlocal selected
            if request["op"] == "begin":
                selected = False
            return False

        inputs, process = await connected(handler)
        await inputs.authorize()
        assert (
            await inputs._insert_prefix("中", lambda: True, selected=lambda: selected)
            == 0
        )
        assert not any(r["op"] == "key" for r in process.requests)
        assert sum(r["op"] == "finish" for r in process.requests) == 1
        await inputs.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("operation", ["begin", "key"])
def test_late_ack_after_process_replacement_never_cleans_new_process(operation):
    async def run():
        replacement = Process()
        inputs = None

        def handler(process, request):
            if request["op"] == operation:
                inputs._process = replacement
            return False

        inputs, original = await connected(handler)
        await inputs.authorize()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await inputs.insert("中文", lambda: True)
        assert original.returncode == 0
        assert replacement.requests == [] and replacement.returncode is None
        # Restore the test reference only to reap the original reply reader.
        inputs._process = original
        await inputs.aclose()

    asyncio.run(run())


def test_slow_streaming_output_uses_one_native_transaction_and_fixed_deadline():
    from inkecho.streaming_output import StreamingOutput, TextDelta

    async def run():
        inputs, process = await connected()
        await inputs.authorize()
        deadline = time.monotonic() + 10

        async def send(text):
            return await inputs.insert(text, lambda: True, deadline=deadline)

        output = StreamingOutput(send, lambda: True)

        async def consume():
            async with inputs.output_session():
                return await output.run()

        consumer = asyncio.create_task(consume())
        await output.append(TextDelta(0, "中"))
        while not any(r["op"] == "key" for r in process.requests):
            await asyncio.sleep(0)
        assert not any(r["op"] == "finish" for r in process.requests)
        await output.append(TextDelta(1, "文"))
        await output.finish("中文")
        assert await consumer == 2
        assert [r["value"] for r in process.requests if r["op"] == "key"] == [
            "中",
            "文",
        ]
        assert [r["deadline"] for r in process.requests if r["op"] == "begin"] == [
            deadline
        ]
        assert sum(r["op"] == "finish" for r in process.requests) == 1
        await inputs.aclose()

    asyncio.run(run())


def test_scope_default_deadline_is_not_renewed_after_idle_expiry(monkeypatch):
    async def run():
        inputs, process = await connected()
        await inputs.authorize()
        clock = time.monotonic()
        from types import SimpleNamespace

        monkeypatch.setattr(
            "inkecho.platform.wayland_keyboard.time",
            SimpleNamespace(monotonic=lambda: clock),
        )
        with pytest.raises(KeyboardError, match="injection_failed"):
            async with inputs.output_session():
                await inputs.insert("中", lambda: True, deadline=clock + 10)
                clock += 11
                with pytest.raises(KeyboardError, match="input_cancelled"):
                    await inputs.insert("tail", lambda: True)
                assert [r["value"] for r in process.requests if r["op"] == "key"] == [
                    "中"
                ]
                assert sum(r["op"] == "cancel" for r in process.requests) == 1
        await inputs.aclose()

    asyncio.run(run())


def test_second_owner_cancel_keeps_cleanup_exclusive_until_ack():
    async def run():
        cleanup_started = asyncio.Event()
        ready = asyncio.Event()

        def handler(_process, request):
            if request["op"] == "cancel":
                cleanup_started.set()
                return True
            return False

        inputs, process = await connected(handler)
        await inputs.authorize()

        async def owner():
            async with inputs.output_session():
                await inputs.insert("中", lambda: True)
                ready.set()
                await asyncio.Event().wait()

        task = asyncio.create_task(owner())
        await ready.wait()
        task.cancel()
        await cleanup_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        cancel = next(r for r in process.requests if r["op"] == "cancel")
        before = len(process.requests)
        try:
            assert not inputs.connected and not inputs.authorized
            with pytest.raises(KeyboardError, match="cleanup_pending"):
                await inputs.connect()
            with pytest.raises(KeyboardError, match="cleanup_pending"):
                await inputs.authorize()
            with pytest.raises(KeyboardError, match="busy|cleanup_pending"):
                await inputs.insert("tail", lambda: True)
            assert len(process.requests) == before
        finally:
            process.reply(cancel)
            await asyncio.sleep(0)
            await inputs.aclose()
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["中"]

    asyncio.run(run())


def test_cleanup_failure_keeps_backend_unavailable_without_new_body():
    async def run():
        def handler(process, request):
            if request["op"] == "cancel":
                process.stdout.feed_data(
                    json.dumps(
                        {
                            "id": request["id"],
                            "ok": False,
                            "error": "mapping_changed",
                        }
                    ).encode()
                    + b"\n"
                )
                return True
            return False

        inputs, process = await connected(handler)
        await inputs.authorize()
        with pytest.raises(KeyboardError, match="cleanup_pending"):
            await inputs._cancel_and_clean(process)
        assert inputs._cleanup_pending and inputs._cleanup_task is None
        assert not inputs.connected and not inputs.authorized
        count = len(process.requests)
        with pytest.raises(KeyboardError, match="cleanup_pending"):
            await inputs.authorize()
        with pytest.raises(KeyboardError, match="cleanup_pending"):
            await inputs.insert("tail", lambda: True)
        assert len(process.requests) == count
        await inputs.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("old_failure", [False, True])
def test_old_cleanup_completion_cannot_unlock_or_poison_replacement(old_failure):
    async def run():
        def hold_cancel(_process, request):
            return request["op"] == "cancel"

        inputs, original = await connected(hold_cancel)
        await inputs.authorize()
        old_reader = inputs._reader
        old_cleanup = asyncio.create_task(inputs._cancel_and_clean(original))
        while not any(r["op"] == "cancel" for r in original.requests):
            await asyncio.sleep(0)
        old_request = next(r for r in original.requests if r["op"] == "cancel")
        replacement = Process(hold_cancel)
        inputs._process = replacement
        inputs._pending = {}
        inputs._reader = asyncio.create_task(
            inputs._read_replies(replacement, inputs._pending)
        )
        new_cleanup = asyncio.create_task(inputs._cancel_and_clean(replacement))
        while not replacement.requests:
            await asyncio.sleep(0)
        new_lock = inputs._cleanup_task
        if old_failure:
            original.stdout.feed_data(
                json.dumps(
                    {
                        "id": old_request["id"],
                        "ok": False,
                        "error": "mapping_changed",
                    }
                ).encode()
                + b"\n"
            )
            with pytest.raises(KeyboardError, match="cleanup_pending"):
                await old_cleanup
        else:
            original.reply(old_request)
            await old_cleanup
        assert inputs._cleanup_task is new_lock
        assert inputs._cleanup_process is replacement
        assert not inputs._cleanup_pending and not inputs.connected
        assert replacement.returncode is None
        with pytest.raises(KeyboardError, match="cleanup_pending"):
            await inputs.insert("tail", lambda: True)
        assert [r["op"] for r in replacement.requests] == ["cancel"]
        # Repeated requests for this process share the same cleanup and ACK.
        repeated = asyncio.create_task(inputs._cancel_and_clean(replacement))
        await asyncio.sleep(0)
        assert inputs._cleanup_task is new_lock and len(replacement.requests) == 1
        replacement.reply(replacement.requests[0])
        await asyncio.gather(new_cleanup, repeated)
        assert inputs._cleanup_task is None and inputs.connected and inputs.authorized
        assert original.returncode is None or original.returncode == 0
        original.close()
        await old_reader
        await inputs.aclose()

    asyncio.run(run())


def test_failed_cleanup_reconnects_only_after_original_guardian_exits():
    async def run():
        def handler(process, request):
            if request["op"] == "cancel":
                process.stdout.feed_data(
                    json.dumps(
                        {
                            "id": request["id"],
                            "ok": False,
                            "error": "mapping_changed",
                        }
                    ).encode()
                    + b"\n"
                )
                return True
            return False

        inputs, original = await connected(handler)
        await inputs.authorize()
        original_reader = inputs._reader
        pipe_closed = []
        original.close = lambda: pipe_closed.append(True)
        replacement = Process()
        spawned = []

        async def spawn(*_args, **_kwargs):
            spawned.append(replacement)
            return replacement

        inputs._spawn = spawn
        with pytest.raises(KeyboardError, match="cleanup_pending"):
            await inputs._cancel_and_clean(original)
        assert pipe_closed and original.returncode is None
        assert inputs._cleanup_pending
        with pytest.raises(KeyboardError, match="cleanup_pending"):
            await inputs.connect()
        assert spawned == []
        # Simulate the guardian's eventual natural restoration and exit.
        original.returncode = 0
        original.stdout.feed_eof()
        original.closed.set()
        await original_reader
        await inputs.connect()
        await inputs.authorize()
        assert spawned == [replacement]
        assert inputs.connected and inputs.authorized and not inputs._cleanup_pending
        assert [r["op"] for r in replacement.requests] == ["connect", "authorize"]
        assert not any(r["op"] == "key" for r in original.requests)
        assert await inputs.insert("新", lambda: True) == 1
        assert [r["value"] for r in replacement.requests if r["op"] == "key"] == ["新"]
        await inputs.aclose()

    asyncio.run(run())


def test_parent_bounds_nonemitting_hint_and_never_crosses_newline():
    async def run():
        inputs, process = await connected()
        await inputs.authorize()
        assert await inputs.insert("ab\ncd", lambda: True) == 5
        keys = [r for r in process.requests if r["op"] == "key"]
        assert [(r["value"], r.get("hint")) for r in keys] == [
            ("a", "b"),
            ("b", None),
            ("\n", None),
            ("c", "d"),
            ("d", None),
        ]
        await inputs.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("cancel", [False, True])
def test_hint_cannot_emit_after_native_to_x_switch_or_cancel(cancel):
    async def run():
        allowed = True
        native_borrowed = False
        events = []

        class Driver:
            is_x = False
            mapped = None
            applied = None

            def focus(self):
                if not self.is_x:
                    raise KeyboardError("unsupported_target")
                return 42

            def map(self, char):
                assert not native_borrowed
                self.mapped = self.applied = char
                return 248

            def verify(self):
                pass

            def send(self, window, code, pressed):
                events.append((self.mapped, pressed))

            def restore(self):
                self.mapped = self.applied = None

            def close(self):
                self.restore()

        driver = Driver()

        def handler(_process, request):
            nonlocal allowed, native_borrowed
            if request["op"] == "begin":
                native_borrowed = True
            elif request["op"] in {"finish", "cancel", "close"}:
                native_borrowed = False
            elif request["op"] == "key":
                assert request["value"] == "a" and request["hint"] == "b"
                driver.is_x = True
                if cancel:
                    allowed = False
            return False

        native, process = await connected(handler)
        hybrid = HybridKeyboardInput(
            native=native, x11=KeyboardInput(driver_factory=lambda: driver)
        )
        await hybrid.connect()
        await hybrid.authorize()
        if cancel:
            with pytest.raises(KeyboardError, match="input_cancelled"):
                await hybrid.insert("ab", lambda: allowed)
            assert events == []
        else:
            assert await hybrid.insert("ab", lambda: allowed) == 2
            assert events == [("b", True), ("b", False)]
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["a"]
        assert not native_borrowed
        await hybrid.aclose()

    asyncio.run(run())


def test_parent_lookahead_is_at_most_three_and_stops_at_newline():
    async def run():
        inputs, process = await connected()
        await inputs.authorize()
        assert await inputs.insert("abcde\nfghi", lambda: True) == 10
        keys = [r for r in process.requests if r["op"] == "key"]
        assert [(r["value"], r.get("hint")) for r in keys] == [
            ("a", "bcd"),
            ("b", "cde"),
            ("c", "de"),
            ("d", "e"),
            ("e", None),
            ("\n", None),
            ("f", "ghi"),
            ("g", "hi"),
            ("h", "i"),
            ("i", None),
        ]
        await inputs.aclose()

    asyncio.run(run())


@pytest.mark.parametrize(
    "feedback",
    [
        None,
        {},
        {"map_changed": 1},
        {
            "map_changed": True,
            "cache_hit": False,
            "map_set_seconds": 10**1000,
            "map_confirm_seconds": 0,
        },
        {
            "map_changed": True,
            "cache_hit": False,
            "map_set_seconds": 0,
            "map_confirm_seconds": 10**1000,
        },
        {
            "map_changed": True,
            "cache_hit": False,
            "map_set_seconds": -1,
            "map_confirm_seconds": 0,
        },
        {
            "map_changed": False,
            "cache_hit": True,
            "map_set_seconds": float("nan"),
            "map_confirm_seconds": 0,
        },
        {
            "map_changed": False,
            "cache_hit": True,
            "map_set_seconds": 0,
            "map_confirm_seconds": float("inf"),
        },
        {
            "map_changed": True,
            "cache_hit": True,
            "map_set_seconds": 0,
            "map_confirm_seconds": 0,
        },
    ],
)
def test_invalid_advisory_feedback_drops_sample_but_never_replays_success(feedback):
    from inkecho.platform.output_pacing import OutputPacer

    class Pacer(OutputPacer):
        def __init__(self):
            super().__init__()
            self.samples = self.resets = 0

        def ack(self, *args, **kwargs):
            self.samples += 1
            return super().ack(*args, **kwargs)

        def reset_input(self, token):
            self.resets += 1
            return super().reset_input(token)

    async def run():
        def handle(process, request):
            if request["op"] == "key":
                process.reply(request, count=1, input_feedback=feedback)
                return True
            return False

        pacer = Pacer()
        inputs, process = await connected(handle, pacer=pacer)
        await inputs.authorize()
        calls = []
        assert (
            await inputs.insert("中文", lambda: True, on_first_sent=calls.append) == 2
        )
        assert pacer.samples == 0 and pacer.resets == 2
        assert len(calls) == 1
        assert [r["value"] for r in process.requests if r["op"] == "key"] == [
            "中",
            "文",
        ]
        assert process.requests[-1]["op"] == "finish"
        assert inputs._pacing_token is None
        await inputs.aclose()

    asyncio.run(run())


def test_valid_input_feedback_and_legacy_ack_both_use_input_rtt_only():
    from inkecho.platform.output_pacing import FeedbackLevel, OutputPacer

    class Pacer(OutputPacer):
        def __init__(self):
            super().__init__()
            self.samples = []

        def ack(self, token, **kwargs):
            accepted = super().ack(token, **kwargs)
            self.samples.append((token, accepted, self.snapshot(token)))
            return accepted

    async def run():
        def handle(process, request):
            if request["op"] == "key" and request["value"] == "中":
                process.reply(
                    request,
                    count=1,
                    input_feedback={
                        "map_changed": True,
                        "cache_hit": False,
                        "map_set_seconds": 0.001,
                        "map_confirm_seconds": 0.002,
                    },
                )
                return True
            return False

        pacer = Pacer()
        inputs, process = await connected(handle, pacer=pacer)
        await inputs.authorize()
        assert await inputs.insert("中文", lambda: True) == 2
        assert len(pacer.samples) == 2
        assert pacer.samples[0][0] == pacer.samples[1][0]
        assert all(
            accepted and snapshot.level == FeedbackLevel.INPUT and snapshot.pending == 0
            for _, accepted, snapshot in pacer.samples
        )
        old = pacer.samples[-1][0]
        assert not OutputPacer.ack(pacer, old, started=0, completed=0)
        assert await inputs.insert("后", lambda: True) == 1
        assert pacer.samples[-1][0] != old
        await inputs.aclose()

    asyncio.run(run())


def test_cancel_during_input_pacing_wait_never_starts_key_and_cleans_scope():
    from inkecho.platform.output_pacing import OutputPacer

    class Pacer(OutputPacer):
        def __init__(self):
            super().__init__()
            self.waiting = asyncio.Event()
            self.token = None

        async def before_send(self, token, **kwargs):
            self.token = token
            self.waiting.set()
            await asyncio.Event().wait()

    async def run():
        pacer = Pacer()
        inputs, process = await connected(pacer=pacer)
        await inputs.authorize()
        task = asyncio.create_task(inputs.insert("未发送", lambda: True))
        await asyncio.wait_for(pacer.waiting.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not any(r["op"] == "key" for r in process.requests)
        assert process.requests[-1]["op"] == "cancel"
        assert inputs._pacing_token is None
        assert not pacer.invalidate(pacer.token)
        await inputs.aclose()

    asyncio.run(run())


def test_selection_changed_during_pacing_sends_no_old_route_character():
    from inkecho.platform.output_pacing import OutputPacer

    async def run():
        selected = True

        class Pacer(OutputPacer):
            async def before_send(self, token, **kwargs):
                nonlocal selected
                await super().before_send(token, **kwargs)
                selected = False

        inputs, process = await connected(pacer=Pacer())
        await inputs.authorize()
        async with inputs.output_session():
            assert (
                await inputs._insert_prefix(
                    "未发送", lambda: True, selected=lambda: selected
                )
                == 0
            )
        assert not any(r["op"] == "key" for r in process.requests)
        assert process.requests[-1]["op"] == "finish"
        await inputs.aclose()

    asyncio.run(run())


def test_replaced_worker_ack_never_updates_input_pacer():
    from inkecho.platform.output_pacing import OutputPacer

    async def run():
        replacement = Process()
        inputs = None

        class Pacer(OutputPacer):
            def ack(self, *args, **kwargs):
                pytest.fail("old worker ACK must not update a pacing generation")

        def handle(_process, request):
            if request["op"] == "key":
                inputs._process = replacement
            return False

        inputs, original = await connected(handle, pacer=Pacer())
        await inputs.authorize()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await inputs.insert("中文", lambda: True)
        assert replacement.requests == []
        assert inputs._pacing_token is None
        inputs._process = original
        await inputs.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("field", ["map_set_seconds", "map_confirm_seconds"])
@pytest.mark.parametrize(
    "number",
    [
        True,
        False,
        None,
        "0.1",
        [],
        {},
        -1,
        -0.1,
        float("nan"),
        float("inf"),
        -float("inf"),
        10**1000,
        -(10**1000),
    ],
)
def test_optional_feedback_numeric_shapes_never_raise(field, number):
    from inkecho.platform.wayland_keyboard import _input_feedback

    value = {
        "map_changed": True,
        "cache_hit": False,
        "map_set_seconds": 0.001,
        "map_confirm_seconds": 0.002,
    }
    value[field] = number
    assert _input_feedback(value) is None


def test_active_predicate_failure_during_pacing_invalidates_scope_and_cleans():
    from inkecho.platform.output_pacing import OutputPacer

    async def run():
        allowed = True

        class Pacer(OutputPacer):
            async def before_send(self, token, **kwargs):
                nonlocal allowed
                allowed = False
                await super().before_send(token, **kwargs)

        pacer = Pacer()
        inputs, process = await connected(pacer=pacer)
        await inputs.authorize()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await inputs.insert("未发送", lambda: allowed)
        assert not any(r["op"] == "key" for r in process.requests)
        assert process.requests[-1]["op"] == "cancel"
        assert inputs._pacing_token is None
        assert not pacer.invalidate(1)
        await inputs.aclose()

    asyncio.run(run())


def test_fragments_retain_input_baselines_and_fixed_deadline_until_scope_exit():
    from inkecho.platform.output_pacing import OutputPacer

    class Pacer(OutputPacer):
        def __init__(self):
            super().__init__()
            self.binds = []
            self.samples = []

        def bind(self, level):
            token = super().bind(level)
            self.binds.append(token)
            return token

        def ack(self, token, **kwargs):
            accepted = super().ack(token, **kwargs)
            self.samples.append(
                (
                    token,
                    accepted,
                    self._scope.deadline,
                    dict(self._scope.input_baselines),
                )
            )
            return accepted

    async def run():
        pacer = Pacer()
        inputs, process = await connected(pacer=pacer)
        await inputs.authorize()
        deadline = time.monotonic() + 5
        async with inputs.output_session():
            assert await inputs.insert("中", lambda: True, deadline=deadline) == 1
            first = pacer.samples[-1]
            assert first[3]
            assert await inputs.insert("文", lambda: True, deadline=deadline) == 1
            second = pacer.samples[-1]
            assert first[0] == second[0]
            assert first[2] == second[2] == deadline
            assert first[3].keys() == second[3].keys()
            assert len(pacer.binds) == 1
        assert inputs._pacing_token is None
        assert [r["deadline"] for r in process.requests if r["op"] == "begin"] == [
            deadline
        ]
        await inputs.aclose()

    asyncio.run(run())


def test_native_acknowledged_key_visible_before_synchronous_cancel():
    async def scenario():
        inputs, process = await connected()
        await inputs.authorize()
        active = True
        observed = []

        def cancel(_at):
            nonlocal active
            observed.append(inputs.acknowledged_attempts)
            active = False

        with pytest.raises(KeyboardError, match="input_cancelled"):
            async with inputs.output_session():
                await inputs.insert("甲乙", lambda: active, on_first_sent=cancel)
        assert observed == [1]
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["甲"]
        assert inputs.acknowledged_attempts == 0
        await inputs.aclose()

    asyncio.run(scenario())


def test_native_unknown_inflight_key_never_counted():
    async def scenario():
        entered = asyncio.Event()

        def handle(_process, request):
            if request["op"] == "key":
                entered.set()
                return True
            return False

        inputs, process = await connected(handle)
        await inputs.authorize()
        snapshots = []

        async def output():
            async with inputs.output_session():
                try:
                    await inputs.insert("甲乙", lambda: True)
                finally:
                    snapshots.append(inputs.acknowledged_attempts)

        task = asyncio.create_task(output())
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert snapshots == [0]
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["甲"]
        await inputs.aclose()

    asyncio.run(scenario())


def test_valid_worker_reply_is_counted_before_active_stop():
    async def scenario():
        active = True
        callbacks = []

        def handle(process, request):
            nonlocal active
            if request["op"] == "key":
                active = False
                process.reply(request, count=1)
                return True
            return False

        inputs, process = await connected(handle)
        await inputs.authorize()
        snapshots = []
        with pytest.raises(KeyboardError, match="input_cancelled") as failure:
            async with inputs.output_session():
                try:
                    await inputs.insert(
                        "甲乙", lambda: active, on_first_sent=callbacks.append
                    )
                finally:
                    snapshots.append(inputs.acknowledged_attempts)
        assert snapshots == [1]
        assert failure.value.acknowledged_attempts == 1
        assert callbacks == []
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["甲"]
        await inputs.aclose()

    asyncio.run(scenario())


def test_valid_worker_reply_is_counted_before_expired_deadline(monkeypatch):
    async def scenario():
        offset = 0.0
        real_time = time.monotonic

        def clock():
            return real_time() + offset

        def handle(process, request):
            nonlocal offset
            if request["op"] == "key":
                process.reply(request, count=1)
                offset = 10.0
                return True
            return False

        inputs, process = await connected(handle)
        await inputs.authorize()
        deadline = time.monotonic() + 5
        monkeypatch.setattr("inkecho.platform.wayland_keyboard.time.monotonic", clock)
        snapshots = []
        with pytest.raises(KeyboardError, match="input_cancelled") as failure:
            async with inputs.output_session():
                try:
                    await inputs.insert("甲乙", lambda: True, deadline=deadline)
                finally:
                    snapshots.append(inputs.acknowledged_attempts)
        assert snapshots == [1]
        assert failure.value.acknowledged_attempts == 1
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["甲"]
        await inputs.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("malformed", ["count", "sent_at"])
def test_malformed_worker_reply_after_active_stop_prioritizes_cancel(malformed):
    async def scenario():
        active = True
        callbacks = []

        def handle(process, request):
            nonlocal active
            if request["op"] == "key":
                active = False
                fields = (
                    {"count": 0}
                    if malformed == "count"
                    else {"count": 1, "sent_at": "bad"}
                )
                process.reply(request, **fields)
                return True
            return False

        inputs, process = await connected(handle)
        await inputs.authorize()
        with pytest.raises(KeyboardError, match="input_cancelled") as failure:
            await inputs.insert("甲乙", lambda: active, on_first_sent=callbacks.append)
        assert failure.value.acknowledged_attempts == 0
        assert callbacks == []
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["甲"]
        await inputs.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("malformed", ["count", "sent_at"])
def test_malformed_worker_reply_after_deadline_prioritizes_cancel(
    monkeypatch, malformed
):
    async def scenario():
        offset = 0.0
        real_time = time.monotonic

        def clock():
            return real_time() + offset

        def handle(process, request):
            nonlocal offset
            if request["op"] == "key":
                fields = (
                    {"count": 0}
                    if malformed == "count"
                    else {"count": 1, "sent_at": "bad"}
                )
                process.reply(request, **fields)
                offset = 10.0
                return True
            return False

        inputs, process = await connected(handle)
        await inputs.authorize()
        deadline = time.monotonic() + 5
        monkeypatch.setattr("inkecho.platform.wayland_keyboard.time.monotonic", clock)
        with pytest.raises(KeyboardError, match="input_cancelled") as failure:
            await inputs.insert("甲乙", lambda: True, deadline=deadline)
        assert failure.value.acknowledged_attempts == 0
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["甲"]
        await inputs.aclose()

    asyncio.run(scenario())
