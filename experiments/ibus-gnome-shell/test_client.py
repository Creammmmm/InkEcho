import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from dbus_next import MessageType

spec = importlib.util.spec_from_file_location(
    "candidate_client", Path(__file__).with_name("client.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


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
                message_type=MessageType.METHOD_RETURN, body=[":1.12"]
            )
        if message.member in ("Begin", "Cancel"):
            return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=[True])
        value = self.outcomes.pop(0)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=[value])

    def disconnect(self):
        self.disconnected = True


def test_capability_is_exclusive_private_and_never_removes_foreign_file(tmp_path):
    tmp_path.chmod(0o700)
    cap = module.Capability(tmp_path)
    path = cap.path
    assert path.stat().st_mode & 0o777 == 0o600
    assert len(cap.token) == 64
    with pytest.raises(FileExistsError):
        module.Capability(tmp_path)
    path.unlink()
    path.write_text("replacement")
    cap.close()
    assert path.read_text() == "replacement"


def test_rejects_world_accessible_runtime(tmp_path):
    tmp_path.chmod(0o755)
    with pytest.raises(module.CandidateError, match="unsafe_runtime"):
        module.Capability(tmp_path)


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
        assert [m.body[1:] for m in commits] == [[0, "甲"], [1, "乙"]]
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
                    message_type=MessageType.METHOD_RETURN, body=["attempted"]
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
