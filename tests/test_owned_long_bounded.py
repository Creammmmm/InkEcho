"""Long owned sessions retain task bounds and never retry uncertain output."""

import asyncio
import time
import types

import pytest
from dbus_next import MessageType
from test_owned_bounded_protocol import Bus, Cap, async_true, xml

from inkecho.platform.ibus_owned import CandidateError, Client


def long_schema():
    return (
        xml()
        .replace("BeginBounded", "BeginLongBounded")
        .replace("CommitBounded", "CommitLongBounded")
    )


class LongBus(Bus):
    async def call(self, message):
        if message.member in {"BeginLongBounded", "CommitLongBounded"}:
            self.calls.append((message.member, message.signature, message.body))
            if message.member == "CommitLongBounded" and self.mode == "timeout":
                raise TimeoutError
            if message.member == "CommitLongBounded" and self.mode == "cancel":
                await self.client.cancel()
            return types.SimpleNamespace(
                message_type=MessageType.METHOD_RETURN,
                sender=":1.23",
                signature="b" if message.member == "BeginLongBounded" else "s",
                body=[True] if message.member == "BeginLongBounded" else ["attempted"],
            )
        return await super().call(message)


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    "deadline", [None, True, False, "4", 0, -1, float("nan"), float("inf"), 10**100]
)
def test_invalid_explicit_deadline_stops_before_begin(deadline):
    async def check():
        bus = LongBus(long_schema())
        client = Client(
            Cap(), bus_factory=lambda: bus, owner_verifier=lambda _: async_true()
        )
        # None is a legacy compatibility default; it intentionally stays bounded.
        if deadline is None:
            await client.begin()
            begin = next(call for call in bus.calls if call[0] == "BeginLongBounded")
            assert begin[2][3] <= int((time.monotonic() + 59) * 1_000_000)
            await client.close()
            return
        with pytest.raises(CandidateError, match="cancelled"):
            await client.begin(deadline=deadline)
        assert not bus.calls

    run(check())


@pytest.mark.parametrize("mode", ["timeout", "cancel"])
def test_long_session_stops_after_unknown_or_cancellation(mode):
    async def check():
        bus = LongBus(long_schema())
        client = Client(
            Cap(), bus_factory=lambda: bus, owner_verifier=lambda _: async_true()
        )
        bus.client = client
        deadline = time.monotonic() + 180
        await client.begin(deadline=deadline)
        begin = next(call for call in bus.calls if call[0] == "BeginLongBounded")
        assert begin[2][2] == 2 and begin[2][3] <= int(deadline * 1_000_000)
        bus.mode = mode
        with pytest.raises(CandidateError):
            await client.insert("甲乙", lambda: True, deadline=deadline)
        with pytest.raises(CandidateError, match="not_ready"):
            await client.insert("丙", lambda: True, deadline=deadline)
        commits = [call for call in bus.calls if call[0] == "CommitLongBounded"]
        assert len(commits) == 1
        assert commits[0][2][2] <= int((time.monotonic() + 3) * 1_000_000)
        await client.close()

    run(check())


def test_partial_long_protocol_does_not_fall_back_to_complete_old_protocol():
    async def check():
        schema = xml().replace(
            "</interface>", '<method name="BeginLongBounded"/></interface>'
        )
        bus = Bus(schema)
        client = Client(
            Cap(), bus_factory=lambda: bus, owner_verifier=lambda _: async_true()
        )
        with pytest.raises(CandidateError, match="unavailable"):
            await client.begin(deadline=time.monotonic() + 180)
        assert not any("Begin" in call[0] for call in bus.calls)
        assert bus.disconnected

    run(check())


def test_expiry_during_negotiation_never_creates_a_session():
    async def check():
        class ExpiringBus(LongBus):
            async def call(self, message):
                if message.member == "Introspect":
                    await asyncio.sleep(0.03)
                return await super().call(message)

        bus = ExpiringBus(long_schema())
        client = Client(
            Cap(), bus_factory=lambda: bus, owner_verifier=lambda _: async_true()
        )
        with pytest.raises(CandidateError, match="cancelled"):
            await client.begin(deadline=time.monotonic() + 0.01)
        assert not any("Begin" in call[0] for call in bus.calls)
        assert bus.disconnected

    run(check())


def test_owned_bus_observes_discarded_write_future_without_masking_failure(monkeypatch):
    from dbus_next.aio import MessageBus

    from inkecho.platform.ibus_owned import _OwnedMessageBus

    async def check():
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        monkeypatch.setattr(MessageBus, "send", lambda _self, _message: future)
        bus = object.__new__(_OwnedMessageBus)
        returned = bus.send(object())
        assert returned is future
        future.set_exception(BrokenPipeError("synthetic"))
        await asyncio.sleep(0)
        # The callback marks the separately ignored write future observed; an
        # actual caller awaiting it still receives the original exception.
        assert not future._log_traceback
        with pytest.raises(BrokenPipeError, match="synthetic"):
            await returned

    run(check())
