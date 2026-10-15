import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from dbus_next import MessageType

from inkecho.platform.keyboard import KeyboardError
from inkecho.platform.wayland_worker import Guardian, serve


class FakeMap:
    def __init__(self, data):
        self.original = data
        self.groups = 2
        self.caps_mask = 2
        self.closed = False

    def character(self, char):
        return SimpleNamespace(data=char.encode() + b"\0", keycode=124)

    def close(self):
        self.closed = True


class Remote:
    def __init__(self):
        self.data = b"original\0"
        self.state = dict(depressed=0, latched=0, locked=16, group=1, revision=1)
        self.origin = 0
        self.writes = []
        self.events = []
        self.on_set = None
        self.on_press = None
        self.closed = False

    async def connect(self):
        pass

    async def authorize(self):
        pass

    async def snapshot(self, *, refresh=False):
        return dict(self.state), self.data

    async def wait_change(self, state, timeout):
        raise KeyboardError("keys_held")

    async def source(self):
        return self.origin

    async def set_map(self, data, group):
        self.writes.append((data, group))
        self.data, self.state["group"], self.origin = data, group, 1
        if self.on_set:
            await self.on_set()

    async def key(self, code, pressed, *, newline=False):
        self.events.append((code, pressed, newline))
        if pressed and self.on_press:
            await self.on_press()

    async def close(self):
        self.closed = True


@pytest.fixture
def remote(monkeypatch):
    monkeypatch.setattr("inkecho.platform.wayland_worker.Keymap", FakeMap)
    return Remote()


def run(coroutine):
    return asyncio.run(coroutine)


def test_normal_input_preserves_group_and_uses_real_return(remote):
    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()
        assert await guardian.key("你") == 1
        assert await guardian.key("\n") == 1
        await guardian.finish()
        assert remote.data == b"original\0"
        assert all(group == 1 for _, group in remote.writes)
        assert remote.events == [
            (124, True, False),
            (124, False, False),
            (0xFF0D, True, True),
            (0xFF0D, False, True),
        ]

    run(scenario())


@pytest.mark.parametrize("kind", ["cancel", "deadline"])
def test_stop_during_map_does_not_press_and_restores_pending_map(remote, kind):
    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()

        async def after_map():
            remote.on_set = None
            if kind == "cancel":
                guardian.stop()
            else:
                guardian.deadline = time.monotonic() - 1

        remote.on_set = after_map
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await guardian.key("你")
        assert remote.events == []
        await guardian.finish()
        assert remote.data == b"original\0"
        assert guardian.map is None

    run(scenario())


def test_ambiguous_set_failure_restores_known_pending_map(remote):
    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()

        async def fail_after_apply():
            remote.on_set = None
            raise KeyboardError("injection_failed")

        remote.on_set = fail_after_apply
        with pytest.raises(KeyboardError):
            await guardian.key("a")
        await guardian.finish()
        assert remote.data == b"original\0"
        assert remote.events == []

    run(scenario())


def test_attempted_press_always_gets_release_on_failure(remote):
    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()

        async def failed_press():
            raise KeyboardError("injection_failed")

        remote.on_press = failed_press
        with pytest.raises(KeyboardError):
            await guardian.key("a")
        assert remote.events == [(124, True, False), (124, False, False)]
        await guardian.finish()

    run(scenario())


@pytest.mark.parametrize("same_bytes", [True, False])
def test_external_owner_is_never_overwritten_even_if_map_bytes_match(
    remote, same_bytes
):
    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()
        await guardian.key("a")
        remote.origin = 0
        if not same_bytes:
            remote.data = b"other-layout\0"
        expected, count = remote.data, len(remote.writes)
        with pytest.raises(KeyboardError, match="mapping_changed"):
            await guardian.finish()
        assert remote.data == expected
        assert len(remote.writes) == count
        assert guardian.map is None

    run(scenario())


def test_busy_cleanup_keeps_recovery_state_and_blocks_new_task(remote):
    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()
        await guardian.key("a")
        remote.state["depressed"] = 4
        count = len(remote.writes)
        with pytest.raises(KeyboardError, match="cleanup_pending"):
            await guardian.finish()
        assert len(remote.writes) == count
        with pytest.raises(KeyboardError, match="cleanup_pending"):
            await guardian.begin()
        remote.state["depressed"] = 0
        await guardian.finish()
        assert guardian.map is None
        assert remote.data == b"original\0"

    run(scenario())


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("depressed", 1, "keys_held"),
        ("latched", 4, "keys_held"),
        ("locked", 18, "caps_lock"),
    ],
)
def test_start_guard_does_not_mutate_any_map(remote, field, value, code):
    async def scenario():
        remote.state[field] = value
        with pytest.raises(KeyboardError, match=code):
            await Guardian(remote).begin()
        assert remote.writes == []
        assert remote.events == []

    run(scenario())


def test_reader_cancellation_is_processed_while_key_map_is_awaited(remote):
    async def scenario():
        reader = asyncio.StreamReader()
        responses = []
        changed = asyncio.Event()
        release = asyncio.Event()
        guardian = Guardian(remote)

        async def after_set():
            remote.on_set = None
            changed.set()
            await release.wait()

        remote.on_set = after_set

        async def reply(value):
            responses.append(value)

        task = asyncio.create_task(serve(reader, reply, guardian))

        def request(ident, op, **values):
            reader.feed_data(
                (json.dumps({"id": ident, "op": op, **values}) + "\n").encode()
            )

        request(1, "begin")
        while not responses:
            await asyncio.sleep(0)
        request(2, "key", value="你")
        await changed.wait()
        request(3, "cancel")
        await asyncio.sleep(0)
        assert guardian.stopped
        release.set()
        while len(responses) < 3:
            await asyncio.sleep(0)
        assert responses[1] == {"id": 2, "ok": False, "error": "input_cancelled"}
        assert responses[2] == {"id": 3, "ok": True}
        assert remote.events == []
        assert remote.data == b"original\0"
        reader.feed_eof()
        await asyncio.wait_for(task, 1)
        assert remote.closed

    run(scenario())


@pytest.mark.parametrize("operation", ["key", "finish"])
def test_modifier_pressed_during_source_query_prevents_map_mutation(remote, operation):
    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()
        await guardian.key("a")
        writes = len(remote.writes)
        events = len(remote.events)

        async def delayed_source():
            await asyncio.sleep(0)
            remote.state["depressed"] = 4
            return 1

        remote.source = delayed_source
        with pytest.raises(
            KeyboardError,
            match="keys_held" if operation == "key" else "cleanup_pending",
        ):
            if operation == "key":
                await guardian.key("b")
            else:
                await guardian.finish()
        assert len(remote.writes) == writes
        assert len(remote.events) == events
        assert guardian.map is not None

    run(scenario())


def test_unobservable_state_retains_map_until_observation_recovers(remote):
    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()
        await guardian.key("a")
        original_snapshot = remote.snapshot

        async def disconnected(*, refresh=False):
            raise KeyboardError("mapping_changed")

        remote.snapshot = disconnected
        with pytest.raises(KeyboardError, match="cleanup_pending"):
            await guardian.finish()
        assert guardian.map is not None
        assert remote.data == b"a\0"
        remote.snapshot = original_snapshot
        await guardian.finish()
        assert remote.data == b"original\0"

    run(scenario())


def test_lost_eis_observer_reopens_metadata_on_same_session():
    from inkecho.platform.eis import ObserverError
    from inkecho.platform.wayland_worker import MutterSession

    class BrokenObserver:
        async def wait_snapshot(self, **_kwargs):
            raise ObserverError("disconnected")

    class RestoredObserver:
        async def wait_snapshot(self, **_kwargs):
            return dict(device_generation=1, revision=1, depressed=0)

        def keymap_bytes(self, generation, *, expected_revision):
            assert generation == expected_revision == 1
            return b"restored-observation\0"

    async def scenario():
        remote = MutterSession()
        remote.path = "/same/session"
        remote.observer = BrokenObserver()
        reopens = []

        async def reopen():
            reopens.append(remote.path)
            remote.observer = RestoredObserver()

        remote._open_observer = reopen
        state, data = await remote.snapshot()
        assert data == b"restored-observation\0"
        assert state["depressed"] == 0
        assert reopens == ["/same/session"]

    run(scenario())


def test_deadline_expiring_during_source_wait_never_sends_next_character(remote):
    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()
        await guardian.key("a")
        entered, release = asyncio.Event(), asyncio.Event()
        writes, events = len(remote.writes), list(remote.events)

        async def blocked_source():
            entered.set()
            await release.wait()
            return remote.origin

        remote.source = blocked_source
        task = asyncio.create_task(guardian.key("b"))
        await asyncio.wait_for(entered.wait(), 1)
        guardian.deadline = time.monotonic() - 1
        release.set()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await asyncio.wait_for(task, 1)
        assert len(remote.writes) == writes
        assert remote.events == events
        await guardian.finish()
        assert remote.data == b"original\0"

    run(scenario())


@pytest.mark.parametrize("stage", ["map", "press"])
@pytest.mark.parametrize("stop", ["cancel", "eof"])
def test_protocol_stop_during_inflight_io_releases_owned_press_without_tail(
    remote, stage, stop
):
    async def scenario():
        guardian = Guardian(remote)
        reader = asyncio.StreamReader()
        responses = asyncio.Queue()
        entered, release = asyncio.Event(), asyncio.Event()

        async def block():
            remote.on_set = remote.on_press = None
            entered.set()
            await release.wait()

        if stage == "map":
            remote.on_set = block
        else:
            remote.on_press = block

        def request(ident, operation, **fields):
            reader.feed_data(
                (json.dumps(dict(id=ident, op=operation, **fields)) + "\n").encode()
            )

        task = asyncio.create_task(serve(reader, responses.put, guardian))
        try:
            request(1, "begin")
            assert await asyncio.wait_for(responses.get(), 1) == {"id": 1, "ok": True}
            request(2, "key", value="你")
            await asyncio.wait_for(entered.wait(), 1)
            if stop == "cancel":
                request(3, "cancel")
                await asyncio.sleep(0)
                assert guardian.stopped
                request(4, "key", value="尾")
            else:
                # Even a previously received queued character must not survive EOF.
                request(3, "key", value="尾")
                reader.feed_eof()
                await asyncio.sleep(0)
                assert guardian.permanent_stop
            release.set()
            if stop == "cancel":
                reader.feed_eof()
            await asyncio.wait_for(task, 1)
            expected = (
                [] if stage == "map" else [(124, True, False), (124, False, False)]
            )
            assert remote.events == expected
            assert remote.data == b"original\0"
            assert guardian.map is None and guardian.pressed is None
            assert remote.closed
            assert all(data != "尾".encode() + b"\0" for data, _ in remote.writes)
        finally:
            release.set()
            reader.feed_eof()
            if not task.done():
                await asyncio.wait_for(task, 1)

    run(scenario())


@pytest.mark.parametrize("applied", [False, True])
def test_second_map_timeout_recovers_old_or_pending_map_without_replay(remote, applied):
    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()
        await guardian.key("a")
        original_set = remote.set_map
        previous_events = list(remote.events)
        attempted = []

        async def timeout_set(data, group):
            attempted.append(data)
            if applied:
                await original_set(data, group)
            await asyncio.sleep(0)
            remote.set_map = original_set
            # MutterSession sanitizes its bounded D-Bus timeout to this code.
            raise KeyboardError("injection_failed")

        remote.set_map = timeout_set
        with pytest.raises(KeyboardError, match="injection_failed"):
            await guardian.key("b")
        assert guardian.pending_map == b"b\0"
        assert guardian.last_confirmed == b"a\0"
        assert remote.data == (b"b\0" if applied else b"a\0")
        await guardian.finish()
        assert remote.data == b"original\0"
        assert guardian.map is None
        assert attempted == [b"b\0"]
        assert remote.events == previous_events

    run(scenario())


def test_cleanup_source_wait_then_held_release_retries_without_early_reset(remote):
    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()
        await guardian.key("a")
        writes = len(remote.writes)
        source = remote.source

        async def held_after_source():
            await asyncio.sleep(0)
            remote.state["depressed"] = 1
            remote.source = source
            return 1

        remote.source = held_after_source
        with pytest.raises(KeyboardError, match="cleanup_pending"):
            await guardian.finish()
        assert len(remote.writes) == writes
        assert guardian.map is not None and guardian.last_confirmed == b"a\0"
        remote.state["depressed"] = 0
        remote.state["revision"] += 1
        await guardian.finish()
        assert remote.data == b"original\0"
        assert guardian.map is None
        assert remote.events == [(124, True, False), (124, False, False)]

    run(scenario())


def test_mutter_snapshot_rechecks_modifiers_when_revision_changes_with_same_map():
    from inkecho.platform.eis import ObserverError
    from inkecho.platform.wayland_worker import MutterSession

    class ChangingObserver:
        def __init__(self):
            self.revision = 1
            self.waits = 0
            self.map_checks = []

        async def wait_snapshot(self, **_kwargs):
            self.waits += 1
            return dict(
                device_generation=1,
                revision=self.revision,
                depressed=0 if self.revision == 1 else 4,
            )

        def keymap_bytes(self, generation, *, expected_revision):
            self.map_checks.append((generation, expected_revision))
            if self.revision == 1:
                self.revision = 2
                raise ObserverError("snapshot_changed")
            return b"same-map\0"

    async def scenario():
        remote = MutterSession()
        remote.observer = ChangingObserver()
        state, data = await remote.snapshot()
        assert state["depressed"] == 4 and state["revision"] == 2
        assert data == b"same-map\0"
        assert remote.observer.waits == 2
        assert remote.observer.map_checks == [(1, 1), (1, 2)]

    run(scenario())


def test_mutter_snapshot_revision_churn_is_bounded_and_never_returns_stale_state():
    from inkecho.platform.eis import ObserverError
    from inkecho.platform.wayland_worker import MutterSession

    class ChangingObserver:
        def __init__(self):
            self.calls = 0

        async def wait_snapshot(self, **_kwargs):
            self.calls += 1
            return dict(device_generation=1, revision=self.calls, depressed=0)

        def keymap_bytes(self, _generation, *, expected_revision):
            assert expected_revision == self.calls
            raise ObserverError("snapshot_changed")

    async def scenario():
        remote = MutterSession()
        remote.observer = ChangingObserver()
        with pytest.raises(KeyboardError, match="mapping_changed"):
            await remote.snapshot()
        assert remote.observer.calls == 4

    run(scenario())


def test_transient_eis_reopen_failure_can_recover_without_new_mutter_session():
    from inkecho.platform.eis import ObserverError
    from inkecho.platform.wayland_worker import MutterSession

    class BrokenObserver:
        async def wait_snapshot(self, **_kwargs):
            raise ObserverError("disconnected")

    class RecoveredObserver:
        async def wait_snapshot(self, **_kwargs):
            return dict(device_generation=1, revision=1, depressed=0)

        def keymap_bytes(self, generation, *, expected_revision):
            assert (generation, expected_revision) == (1, 1)
            return b"recovered-map\0"

    async def scenario():
        remote = MutterSession()
        remote.path = "/still/owned/session"
        remote.observer = BrokenObserver()
        reopens = []

        async def reopen():
            reopens.append(remote.path)
            remote.observer = None
            if len(reopens) == 1:
                raise KeyboardError("injection_failed")
            remote.observer = RecoveredObserver()

        remote._open_observer = reopen
        with pytest.raises(KeyboardError, match="injection_failed"):
            await remote.snapshot()
        # The guardian retains its map transaction and retries cleanup later.
        state, data = await remote.snapshot()
        assert state["depressed"] == 0
        assert data == b"recovered-map\0"
        assert reopens == ["/still/owned/session", "/still/owned/session"]

    run(scenario())


@pytest.mark.parametrize("stage", ["CreateSession", "Start"])
@pytest.mark.parametrize("stop", ["cancel", "eof"])
@pytest.mark.parametrize("late_reply", [False, True])
def test_provisional_authorization_cancel_closes_resources_without_advancing(
    stage, stop, late_reply
):
    from inkecho.platform.wayland_worker import MutterSession

    async def scenario():
        remote = MutterSession()
        entered, release, disconnected = (
            asyncio.Event(),
            asyncio.Event(),
            asyncio.Event(),
        )
        calls, responses = [], []
        replies = asyncio.Queue()
        path = "/owned/provisional/session"

        class Bus:
            def disconnect(self):
                disconnected.set()

            def add_message_handler(self, _callback):
                pass

            async def call(self, _message):
                return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=[])

        remote.bus = Bus()
        remote.owner = ":1.owned"

        async def connect():
            pass

        async def call(_path, _interface, member, *_args, **_kwargs):
            calls.append(member)
            if member == stage:
                entered.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    if not late_reply:
                        raise
                    # A remote operation can complete despite local cancellation.
                    # The late path must be closed, never advanced to input setup.
            if member == "CreateSession":
                return SimpleNamespace(body=[path])
            if member in {"Start", "Stop"}:
                return SimpleNamespace(body=[])
            raise AssertionError("Cancelled authorization advanced to " + member)

        remote.connect = connect
        remote._call = call
        guardian = Guardian(remote)
        reader = asyncio.StreamReader()

        async def reply(value):
            responses.append(value)
            await replies.put(value)

        def request(ident, op):
            reader.feed_data((json.dumps(dict(id=ident, op=op)) + "\n").encode())

        task = asyncio.create_task(serve(reader, reply, guardian))
        try:
            request(1, "authorize")
            await asyncio.wait_for(entered.wait(), 1)
            if stop == "cancel":
                request(2, "cancel")
            else:
                reader.feed_eof()
            await asyncio.wait_for(disconnected.wait(), 1)
            if stop == "cancel":
                while True:
                    response = await asyncio.wait_for(replies.get(), 1)
                    if response["id"] == 2:
                        assert response["ok"]
                        break
                assert {"id": 1, "ok": False, "error": "input_cancelled"} in responses
                reader.feed_eof()
            await asyncio.wait_for(task, 1)
            assert remote.path is None and remote.bus is None
            assert not any(r["id"] == 1 and r["ok"] for r in responses)
            if stage == "CreateSession":
                assert "Start" not in calls
            assert "ConnectToEIS" not in calls
            if stage == "Start" or late_reply:
                assert "Stop" in calls  # Known returned path is reclaimed.
        finally:
            release.set()
            reader.feed_eof()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    run(scenario())


def test_cancel_after_completed_authorization_preserves_reusable_session():
    from inkecho.platform.wayland_worker import MutterSession

    async def scenario():
        remote = MutterSession()
        closed = []

        class Observer:
            def close(self):
                closed.append("observer")

        class Bus:
            def disconnect(self):
                closed.append("bus")

        remote.path = "/already/authorized"
        remote.observer = Observer()
        remote.bus = Bus()

        async def call(_path, _interface, member, *_args, **_kwargs):
            closed.append(member)
            return SimpleNamespace(body=[])

        remote._call = call
        guardian = Guardian(remote)
        reader = asyncio.StreamReader()
        replies = asyncio.Queue()
        task = asyncio.create_task(serve(reader, replies.put, guardian))
        try:
            for ident, op in [(1, "authorize"), (2, "cancel")]:
                reader.feed_data((json.dumps(dict(id=ident, op=op)) + "\n").encode())
                assert await asyncio.wait_for(replies.get(), 1) == {
                    "id": ident,
                    "ok": True,
                }
            assert remote.path == "/already/authorized"
            assert remote.observer is not None
            assert closed == []
        finally:
            reader.feed_eof()
            await asyncio.wait_for(task, 1)
        assert "Stop" in closed and "bus" in closed

    run(scenario())


@pytest.mark.parametrize("queued_operation", ["begin", "key"])
def test_cancel_invalidates_queued_epoch_but_allows_new_task(remote, queued_operation):
    async def scenario():
        guardian = Guardian(remote)
        reader = asyncio.StreamReader()
        replies = asyncio.Queue()
        entered, release = asyncio.Event(), asyncio.Event()
        next_id = 0

        async def blocked_connect():
            entered.set()
            await release.wait()

        remote.connect = blocked_connect

        def request(op, **fields):
            nonlocal next_id
            next_id += 1
            reader.feed_data(
                (json.dumps(dict(id=next_id, op=op, **fields)) + "\n").encode()
            )
            return next_id

        async def response():
            return await asyncio.wait_for(replies.get(), 1)

        task = asyncio.create_task(serve(reader, replies.put, guardian))
        try:
            if queued_operation == "key":
                ident = request("begin")
                assert await response() == {"id": ident, "ok": True}
            connect_id = request("connect")
            await asyncio.wait_for(entered.wait(), 1)
            stale_id = request(
                queued_operation,
                **({"value": "旧"} if queued_operation == "key" else {}),
            )
            cancel_id = request("cancel")
            # Queue saturation must not suppress the cancellation side effect.
            assert await response() == {"id": cancel_id, "ok": False, "error": "busy"}
            assert guardian.stopped
            release.set()
            assert await response() == {"id": connect_id, "ok": True}
            assert await response() == {
                "id": stale_id,
                "ok": False,
                "error": "input_cancelled",
            }
            assert guardian.stopped and guardian.map is None
            assert remote.events == [] and remote.writes == []

            begin_id = request("begin")
            assert await response() == {"id": begin_id, "ok": True}
            assert not guardian.stopped and guardian.map is not None
            key_id = request("key", value="新")
            assert await response() == {"id": key_id, "ok": True, "count": 1}
            finish_id = request("finish")
            assert await response() == {"id": finish_id, "ok": True}
            assert remote.events == [(124, True, False), (124, False, False)]
            assert remote.writes == [("新".encode() + b"\0", 1), (b"original\0", 1)]
        finally:
            release.set()
            reader.feed_eof()
            await asyncio.wait_for(task, 1)
        assert remote.closed

    run(scenario())


def test_set_map_fd_can_be_resealed_by_mutter_but_cannot_be_changed():
    import errno
    import fcntl
    import os

    from inkecho.platform.wayland_worker import MutterSession

    async def scenario():
        remote = MutterSession()
        remote.path = "/owned/session"
        data = b"xkb_keymap { /* owned fixture */ };\0"
        received = []

        async def call(path, interface, member, signature, body, fds):
            assert path == remote.path and member == "SetKeymap"
            assert signature == "a{sv}" and body[0]["xkb-keymap"].value == 0
            fd = fds[0]
            received.append(fd)
            mask = (
                getattr(fcntl, "F_SEAL_WRITE", 8)
                | getattr(fcntl, "F_SEAL_GROW", 4)
                | getattr(fcntl, "F_SEAL_SHRINK", 2)
            )
            seals = fcntl.fcntl(fd, getattr(fcntl, "F_GET_SEALS", 1034))
            assert seals == mask
            # Mutter 50.1 repeats this operation when importing the descriptor.
            fcntl.fcntl(fd, getattr(fcntl, "F_ADD_SEALS", 1033), mask)
            for mutation in (
                lambda: os.pwrite(fd, b"!", 0),
                lambda: os.ftruncate(fd, 0),
                lambda: os.ftruncate(fd, len(data) + 1),
            ):
                with pytest.raises(OSError) as error:
                    mutation()
                assert error.value.errno == errno.EPERM
            assert os.pread(fd, len(data), 0) == data
            return SimpleNamespace(body=[])

        remote._call = call
        await remote.set_map(data, 0)
        assert len(received) == 1
        with pytest.raises(OSError) as error:
            os.fstat(received[0])
        assert error.value.errno == errno.EBADF

    run(scenario())


@pytest.mark.parametrize("failure", ["memfd_create", "write", "fcntl"])
def test_local_map_fd_errors_are_sanitized_and_recovery_state_is_retained(
    remote, monkeypatch, failure
):
    from inkecho.platform import wayland_worker

    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()
        await guardian.key("a")
        original_set = remote.set_map
        session = wayland_worker.MutterSession()

        def fail(*_args, **_kwargs):
            raise OSError("sensitive synthetic OS details")

        module = wayland_worker.fcntl if failure == "fcntl" else wayland_worker.os
        with monkeypatch.context() as scope:
            scope.setattr(module, failure, fail)
            with pytest.raises(KeyboardError) as error:
                await session.set_map(b"candidate\0", 1)
            assert "sensitive" not in str(error.value)
            remote.set_map = session.set_map
            with pytest.raises(KeyboardError, match="cleanup_pending"):
                await guardian.finish()
            assert guardian.map is not None
            assert remote.data == b"a\0"
        remote.set_map = original_set
        await guardian.finish()
        assert remote.data == b"original\0" and guardian.map is None

    run(scenario())


def test_authorization_subscription_timeout_is_sanitized_and_reclaims_session():
    from inkecho.platform.wayland_worker import MutterSession

    async def scenario():
        remote = MutterSession()
        closed = []

        class Bus:
            def add_message_handler(self, _callback):
                pass

            async def call(self, _message):
                raise TimeoutError("sensitive transport details")

            def disconnect(self):
                closed.append("bus")

        remote.bus = Bus()
        remote.owner = ":1.owned"

        async def connect():
            pass

        async def call(_path, _interface, member, *_args, **_kwargs):
            if member == "CreateSession":
                return SimpleNamespace(body=["/owned/provisional"])
            assert member == "Stop"
            closed.append("Stop")
            return SimpleNamespace(body=[])

        remote.connect, remote._call = connect, call
        with pytest.raises(KeyboardError) as error:
            await remote.authorize()
        assert "sensitive" not in str(error.value)
        assert closed == ["Stop", "bus"]
        assert remote.path is None and remote.bus is None

    run(scenario())


@pytest.mark.parametrize("boundary", ["map", "release"])
@pytest.mark.parametrize("stop_kind", ["cancel", "deadline"])
def test_stop_during_settle_never_acknowledges_or_sends_a_tail(
    remote, monkeypatch, boundary, stop_kind
):
    from inkecho.platform import wayland_worker

    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()
        reached, resume = asyncio.Event(), asyncio.Event()
        sleeps = []
        original_sleep = asyncio.sleep

        async def controlled_sleep(duration):
            sleeps.append(duration)
            target = 1 if boundary == "map" else 2
            if len(sleeps) == target:
                reached.set()
                await resume.wait()
            else:
                await original_sleep(0)

        monkeypatch.setattr(wayland_worker.asyncio, "sleep", controlled_sleep)
        delivery = asyncio.create_task(guardian.key("a"))
        await asyncio.wait_for(reached.wait(), 1)
        expected_events = (
            [] if boundary == "map" else [(124, True, False), (124, False, False)]
        )
        assert remote.events == expected_events
        assert remote.data == b"a\0"
        if stop_kind == "cancel":
            guardian.stop()
        else:
            guardian.deadline = time.monotonic() - 1
        assert not delivery.done()
        resume.set()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await delivery
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await guardian.key("b")
        assert remote.events == expected_events
        await guardian.finish()
        assert remote.data == b"original\0"
        assert guardian.map is None
        assert remote.events == expected_events
        assert sleeps == [0.05] * (1 if boundary == "map" else 2)

    run(scenario())


def test_failed_release_settles_before_cleanup_retry_or_restore(remote, monkeypatch):
    from inkecho.platform import wayland_worker

    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()
        sequence = []
        original_key = remote.key
        original_set = remote.set_map
        fail_release = True

        async def key(code, pressed, *, newline=False):
            nonlocal fail_release
            await original_key(code, pressed, newline=newline)
            sequence.append("press" if pressed else "release")
            if not pressed and fail_release:
                fail_release = False
                raise KeyboardError("injection_failed")

        async def set_map(data, group):
            sequence.append("restore" if data == b"original\0" else "map")
            await original_set(data, group)

        async def settle(duration):
            sequence.append("settle")

        monkeypatch.setattr(wayland_worker.asyncio, "sleep", settle)
        remote.key, remote.set_map = key, set_map
        with pytest.raises(KeyboardError, match="injection_failed"):
            await guardian.key("a")
        assert guardian.pressed == (124, False)
        await guardian.finish()
        assert sequence == [
            "map",
            "settle",
            "press",
            "release",
            "settle",
            "release",
            "settle",
            "restore",
        ]
        assert guardian.pressed is None
        assert guardian.map is None
        assert remote.data == b"original\0"

    run(scenario())


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("depressed", 4, "keys_held"),
        ("latched", 4, "keys_held"),
        ("locked", 18, "caps_lock"),
    ],
)
def test_map_settle_refreshes_new_modifier_state_before_press(
    remote, monkeypatch, field, value, error
):
    from inkecho.platform import wayland_worker

    async def scenario():
        guardian = Guardian(remote)
        await guardian.begin()

        async def settle(duration):
            remote.state[field] = value

        monkeypatch.setattr(wayland_worker.asyncio, "sleep", settle)
        with pytest.raises(KeyboardError, match=error):
            await guardian.key("a")
        assert remote.events == []
        remote.state.update(depressed=0, latched=0, locked=16)
        await guardian.finish()
        assert remote.data == b"original\0"
        assert guardian.map is None

    run(scenario())
