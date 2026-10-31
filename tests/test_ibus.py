import asyncio
import stat
from types import SimpleNamespace

import pytest
from dbus_next import MessageType

from inkecho.platform import ibus as module
from inkecho.platform import ibus_lifecycle
from inkecho.platform.ibus_lifecycle import LifecycleError


async def trusted_owner(_owner):
    return True


class Bus:
    def __init__(self):
        self.calls = []
        self.outcomes = []
        self.disconnected = False

    async def connect(self):
        return self

    async def call(self, message):
        self.calls.append(message)
        if message.member == "GetNameOwner":
            return SimpleNamespace(
                message_type=MessageType.METHOD_RETURN,
                body=[":1.12"],
                sender="org.freedesktop.DBus",
            )
        if message.member in ("Begin", "Cancel"):
            return SimpleNamespace(
                message_type=MessageType.METHOD_RETURN, body=[True], sender=":1.12"
            )
        value = self.outcomes.pop(0)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(
            message_type=MessageType.METHOD_RETURN, body=[value], sender=":1.12"
        )

    def disconnect(self):
        self.disconnected = True


def test_capability_is_exclusive_private_and_never_removes_foreign_file(tmp_path):
    tmp_path.chmod(0o700)
    cap = module.Capability(tmp_path)
    path = cap.path
    assert path.stat().st_mode & 0o777 == 0o600
    assert len(cap.token) == 64
    other = module.Capability(tmp_path)
    assert other.path != path
    other.close()
    path.unlink()
    path.write_text("replacement")
    with pytest.raises(ibus_lifecycle.LifecycleCleanupError, match="cleanup_failed"):
        cap.close()
    assert path.read_text() == "replacement"


def test_rejects_world_accessible_runtime(tmp_path):
    tmp_path.chmod(0o755)
    with pytest.raises(LifecycleError, match="unsafe_directory"):
        module.Capability(tmp_path)


def test_rejects_symlink_runtime_and_cleanup_uses_open_directory(tmp_path):
    root = tmp_path / "runtime"
    root.mkdir(mode=0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(OSError):
        module.Capability(alias)
    cap = module.Capability(root)
    moved = tmp_path / "moved"
    root.rename(moved)
    root.symlink_to(tmp_path, target_is_directory=True)
    cap.close()
    assert not (moved / cap.name).exists()


def test_old_capability_does_not_block_or_get_deleted_by_new_task(tmp_path):
    tmp_path.chmod(0o700)
    abandoned = module.Capability(tmp_path)
    new = module.Capability(tmp_path)
    assert abandoned.path != new.path
    new.close()
    assert abandoned.path.exists()
    abandoned.close()


def test_cleanup_removes_only_own_consumed_file(tmp_path):
    tmp_path.chmod(0o700)
    cap = module.Capability(tmp_path)
    consumed = tmp_path / ("used-" + cap.name)
    cap.path.rename(consumed)
    cap.close()
    assert not consumed.exists()


@pytest.mark.parametrize("failure", ["flock", "write", "fsync"])
def test_capability_creation_failure_removes_its_file(tmp_path, monkeypatch, failure):
    tmp_path.chmod(0o700)

    def fail(*_args):
        raise OSError("simulated creation failure")

    target = ibus_lifecycle.fcntl if failure == "flock" else ibus_lifecycle.os
    monkeypatch.setattr(target, failure, fail)
    with pytest.raises(OSError, match="simulated creation failure"):
        module.Capability(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_failed_creation_preserves_replacement_file(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)

    def replace_then_fail(_fd, _data):
        original = next(tmp_path.iterdir())
        original.unlink()
        original.write_text("foreign replacement")
        raise OSError("simulated write failure")

    monkeypatch.setattr(ibus_lifecycle.os, "write", replace_then_fail)
    with pytest.raises(ibus_lifecycle.LifecycleCleanupError, match="cleanup_failed"):
        module.Capability(tmp_path)
    assert [path.read_text() for path in tmp_path.iterdir()] == ["foreign replacement"]


def test_failed_identity_check_preserves_unverified_file(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    original_fstat = ibus_lifecycle.os.fstat

    def fail_regular_file(fd):
        result = original_fstat(fd)
        if stat.S_ISREG(result.st_mode):
            raise OSError("identity unavailable")
        return result

    monkeypatch.setattr(ibus_lifecycle.os, "fstat", fail_regular_file)
    with pytest.raises(ibus_lifecycle.LifecycleCleanupError, match="cleanup_failed"):
        module.Capability(tmp_path)
    assert len(list(tmp_path.iterdir())) == 1


def test_sequential_fragments_and_token_cleanup(tmp_path):
    async def run():
        tmp_path.chmod(0o700)
        cap = module.Capability(tmp_path)
        bus = Bus()
        bus.outcomes = ["attempted"] * 2
        client = module.Client(
            cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
        )
        await client.begin()
        assert await client.insert("甲", lambda: True) == 1
        assert await client.insert("乙", lambda: True) == 1
        commits = [m for m in bus.calls if m.member == "Commit"]
        assert [m.body for m in commits] == [[0, "甲"], [1, "乙"]]
        assert all(m.destination == ":1.12" for m in commits)
        path = cap.path
        await client.close()
        assert not path.exists() and bus.disconnected

    asyncio.run(run())


def test_unknown_delivery_and_invalid_input_never_replays(tmp_path):
    async def run():
        tmp_path.chmod(0o700)
        cap = module.Capability(tmp_path)
        bus = Bus()
        bus.outcomes = [TimeoutError()]
        client = module.Client(
            cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
        )
        await client.begin()
        with pytest.raises(module.CandidateError, match="unsupported_text"):
            await client.insert("\x01", lambda: True)
        with pytest.raises(module.CandidateError, match="delivery_unknown"):
            await client.insert("甲", lambda: True)
        with pytest.raises(module.CandidateError, match="not_ready"):
            await client.insert("甲", lambda: True)
        assert len([m for m in bus.calls if m.member == "Commit"]) == 1
        await client.close()

    asyncio.run(run())


def test_lf_and_tab_are_sent_in_order(tmp_path):
    async def run():
        tmp_path.chmod(0o700)
        cap = module.Capability(tmp_path)
        bus = Bus()
        bus.outcomes = ["attempted"] * 3
        client = module.Client(
            cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
        )
        await client.begin()
        assert await client.insert("甲\n\t", lambda: True) == 3
        commits = [m.body[1] for m in bus.calls if m.member == "Commit"]
        assert commits == ["甲", "\n", "\t"]
        await client.close()

    asyncio.run(run())


def test_cancel_during_pending_send_stops_remaining_chars(tmp_path):
    async def run():
        tmp_path.chmod(0o700)
        cap = module.Capability(tmp_path)
        bus = Bus()
        started, release = asyncio.Event(), asyncio.Event()
        original = bus.call

        async def call(message):
            if message.member == "Commit":
                bus.calls.append(message)
                started.set()
                await release.wait()
                return SimpleNamespace(
                    message_type=MessageType.METHOD_RETURN,
                    body=["attempted"],
                    sender=":1.12",
                )
            return await original(message)

        bus.call = call
        client = module.Client(
            cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
        )
        await client.begin()
        sending = asyncio.create_task(client.insert("甲乙", lambda: True))
        await started.wait()
        await client.cancel()
        release.set()
        with pytest.raises(module.CandidateError, match="cancelled"):
            await sending
        assert len([m for m in bus.calls if m.member == "Commit"]) == 1
        await client.close()

    asyncio.run(run())


def test_untrusted_service_owner_receives_no_token_and_is_closed(tmp_path):
    async def reject(_owner):
        return False

    async def run():
        tmp_path.chmod(0o700)
        cap = module.Capability(tmp_path)
        path, bus = cap.path, Bus()
        client = module.Client(cap, bus_factory=lambda: bus, owner_verifier=reject)
        with pytest.raises(module.CandidateError, match="untrusted_owner"):
            await client.begin()
        assert [m.member for m in bus.calls] == ["GetNameOwner"]
        assert bus.disconnected and not path.exists()

    asyncio.run(run())


@pytest.mark.parametrize(
    "failure, expected",
    [
        (module.CandidateError("untrusted_owner"), "untrusted_owner"),
        (module.CandidateError("authorization_failed"), "authorization_failed"),
        (PermissionError(13, "private path"), "permission_denied"),
        (RuntimeError("private text"), "unavailable"),
    ],
)
def test_bridge_preparation_errors_are_categorized_and_sanitized(failure, expected):
    async def run():
        def create(_runtime):
            raise failure

        bridge = module.IBusBridge(runtime_dir="/synthetic", capability_factory=create)
        with pytest.raises(module.IBusBridgeError) as caught:
            await bridge.connect()
        assert caught.value.code == expected
        assert "private" not in str(caught.value)

    asyncio.run(run())


def test_begin_rejection_reports_authorization_failure(tmp_path):
    async def run():
        tmp_path.chmod(0o700)
        bus = Bus()
        original = bus.call

        async def reject_begin(message):
            if message.member == "Begin":
                return SimpleNamespace(
                    message_type=MessageType.METHOD_RETURN, body=[False], sender=":1.12"
                )
            return await original(message)

        bus.call = reject_begin
        bridge = module.IBusBridge(
            runtime_dir=tmp_path,
            client_factory=lambda cap: module.Client(
                cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
            ),
        )
        with pytest.raises(module.IBusBridgeError, match="authorization_failed"):
            await bridge.connect()
        assert bus.disconnected and not list(tmp_path.iterdir())

    asyncio.run(run())


class FakeCapability:
    def __init__(self, root):
        self.root = root
        self.closed = False

    def close(self):
        self.closed = True


class FakeClient:
    def __init__(self, capability):
        self.capability = capability
        self.fragments = []
        self.cancelled = self.closed = False
        self.failure = None

    async def begin(self):
        if self.failure:
            raise self.failure

    async def insert(self, text, active, *, on_first_sent=None):
        if not active():
            raise module.CandidateError("cancelled")
        self.fragments.append(text)
        if self.failure:
            raise self.failure
        if on_first_sent:
            on_first_sent(None)
        return len(text)

    async def cancel(self):
        self.cancelled = True

    async def close(self):
        self.closed = True
        self.capability.close()


def test_bridge_reuses_client_across_fragments_and_closes():
    async def run():
        clients = []

        def make_client(cap):
            result = FakeClient(cap)
            clients.append(result)
            return result

        bridge = module.IBusBridge(
            runtime_dir="/test",
            capability_factory=FakeCapability,
            client_factory=make_client,
        )
        await bridge.connect()
        assert await bridge.insert("甲", lambda: True) == 1
        assert await bridge.insert("乙", lambda: True) == 1
        assert clients[0].fragments == ["甲", "乙"]
        await bridge.aclose()
        assert (
            clients[0].cancelled and clients[0].closed and clients[0].capability.closed
        )

    asyncio.run(run())


@pytest.mark.parametrize(
    "deadline", [0, float("nan"), float("inf"), "invalid", 10**400]
)
def test_bridge_rejects_expired_or_invalid_deadline_before_send(deadline):
    async def run():
        clients = []

        def make_client(cap):
            result = FakeClient(cap)
            clients.append(result)
            return result

        bridge = module.IBusBridge(
            runtime_dir="/test",
            capability_factory=FakeCapability,
            client_factory=make_client,
        )
        await bridge.connect()
        with pytest.raises(module.IBusBridgeError, match="cancelled"):
            await bridge.insert("甲", lambda: True, deadline=deadline)
        assert not clients[0].fragments
        await bridge.aclose()

    asyncio.run(run())


def test_bridge_failure_is_sanitized_and_not_replayed():
    async def run():
        clients = []

        def make_client(cap):
            result = FakeClient(cap)
            clients.append(result)
            return result

        bridge = module.IBusBridge(
            runtime_dir="/test",
            capability_factory=FakeCapability,
            client_factory=make_client,
        )
        await bridge.connect()
        clients[0].failure = module.CandidateError("delivery_unknown")
        with pytest.raises(module.IBusBridgeError, match="delivery_unknown"):
            await bridge.insert("甲", lambda: True)
        assert clients[0].fragments == ["甲"]
        await bridge.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("member", ["GetNameOwner", "Begin"])
def test_untrusted_setup_reply_rejected(tmp_path, member):
    async def run():
        tmp_path.chmod(0o700)
        cap = module.Capability(tmp_path)
        bus = Bus()
        original = bus.call

        async def spoof(message):
            result = await original(message)
            if message.member == member:
                result.sender = ":1.99"
            return result

        bus.call = spoof
        client = module.Client(
            cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
        )
        with pytest.raises(module.CandidateError, match="unavailable"):
            await client.begin()
        assert bus.disconnected
        assert all(call.member != "Commit" for call in bus.calls)

    asyncio.run(run())


def test_untrusted_commit_reply_is_unknown_and_never_replayed(tmp_path):
    async def run():
        tmp_path.chmod(0o700)
        cap = module.Capability(tmp_path)
        bus = Bus()
        bus.outcomes = ["attempted"]
        original = bus.call

        async def spoof(message):
            result = await original(message)
            if message.member == "Commit":
                result.sender = ":1.99"
            return result

        bus.call = spoof
        client = module.Client(
            cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
        )
        await client.begin()
        with pytest.raises(module.CandidateError, match="delivery_unknown"):
            await client.insert("甲乙", lambda: True)
        with pytest.raises(module.CandidateError, match="not_ready"):
            await client.insert("甲", lambda: True)
        assert len([call for call in bus.calls if call.member == "Commit"]) == 1
        await client.close()

    asyncio.run(run())


def test_untrusted_daemon_identity_reply_is_rejected(tmp_path):
    async def run():
        tmp_path.chmod(0o700)
        cap = module.Capability(tmp_path)
        bus = Bus()

        async def spoof(_message):
            return SimpleNamespace(
                message_type=MessageType.METHOD_RETURN, body=[1], sender=":1.99"
            )

        bus.call = spoof
        client = module.Client(cap, bus_factory=lambda: bus)
        client._bus = bus
        with pytest.raises(module.CandidateError, match="unavailable"):
            await client._verify_shell_owner(":1.12")
        await client.close()

    asyncio.run(run())
