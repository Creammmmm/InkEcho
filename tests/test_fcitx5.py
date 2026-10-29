import asyncio
from types import SimpleNamespace

import pytest
from dbus_next import MessageType

from inkecho.platform import fcitx5
from inkecho.platform.fcitx5 import INTERFACE, Fcitx5Bridge, FcitxOutputError


def reply(body, kind=MessageType.METHOD_RETURN, sender=":1.42"):
    return SimpleNamespace(body=body, message_type=kind, sender=sender)


class FakeCapability:
    def __init__(self, _runtime):
        self.token = "a" * 64

    def close(self):
        self.token = ""


class FakeBus:
    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)
        self.calls = []
        self.disconnected = False
        self.owner = ":1.42"
        self.handlers = []

    def add_message_handler(self, handler):
        self.handlers.append(handler)

    def change_owner(self, owner):
        old, self.owner = self.owner, owner
        signal = SimpleNamespace(
            message_type=MessageType.SIGNAL,
            sender="org.freedesktop.DBus",
            path="/org/freedesktop/DBus",
            interface="org.freedesktop.DBus",
            member="NameOwnerChanged",
            body=[fcitx5.SERVICE, old, owner],
        )
        for handler in self.handlers:
            handler(signal)

    async def connect(self):
        return self

    async def call(self, message):
        self.calls.append(message)
        if message.member == "AddMatch":
            return reply([], sender=fcitx5.DBUS_SERVICE)
        if message.member == "GetNameOwner":
            return reply([self.owner], sender=fcitx5.DBUS_SERVICE)
        if message.member == "Introspect":
            return reply(
                [
                    f'<node><interface name="{INTERFACE}">'
                    '<method name="Begin"/><method name="Begin3"/>'
                    '<method name="Commit"/>'
                    '<method name="Cancel"/></interface></node>'
                ]
            )
        if message.member in ("Begin3", "Cancel"):
            return reply([True])
        result = self.outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def disconnect(self):
        self.disconnected = True


def test_sends_individual_scalars_to_pinned_owner():
    async def run():
        bus = FakeBus([reply([1])] * 3)
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        assert await client.insert("中a😀", lambda: True) == 3
        sends = [call for call in bus.calls if call.member == "Commit"]
        assert [call.body[1:] for call in sends] == [[0, "中"], [1, "a"], [2, "😀"]]
        assert all(call.destination == ":1.42" for call in sends)
        await client.aclose()
        assert bus.disconnected

    asyncio.run(run())


def test_detected_owner_change_is_rejected_before_capability_creation():
    async def run():
        bus = FakeBus()
        created = []

        def capability(_runtime):
            created.append(True)
            return FakeCapability(_runtime)

        bridge = Fcitx5Bridge(bus_factory=lambda: bus, capability_factory=capability)
        with pytest.raises(FcitxOutputError, match="unavailable"):
            await bridge.connect(expected_owner=":1.99")
        assert created == [] and bus.disconnected
        assert [message.member for message in bus.calls] == ["AddMatch", "GetNameOwner"]

    asyncio.run(run())


def test_unrepresentable_deadline_fails_closed_without_commit():
    async def run():
        bus = FakeBus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: True, deadline=10**400)
        assert caught.value.code == "cancelled"
        assert caught.value.accepted == 0 and not caught.value.safe_to_fallback
        assert all(message.member != "Commit" for message in bus.calls)
        with pytest.raises(FcitxOutputError, match="session_failed"):
            await client.insert("甲", lambda: True)
        await client.aclose()

    asyncio.run(run())


def test_owner_change_after_first_commit_stops_without_replay():
    async def run():
        bus = FakeBus([reply([1]), reply([1])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert(
                "甲乙", lambda: True, on_first_sent=lambda _: bus.change_owner(":1.99")
            )
        assert caught.value.code == "owner_changed"
        assert caught.value.accepted == 1 and not caught.value.safe_to_fallback
        assert [call.body[2] for call in bus.calls if call.member == "Commit"] == ["甲"]
        await client.aclose()

    asyncio.run(run())


def test_owner_query_detects_silent_replacement_before_commit():
    async def run():
        bus = FakeBus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        bus.owner = ":1.99"
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: True)
        assert caught.value.code == "owner_changed"
        assert caught.value.accepted == 0 and not caught.value.safe_to_fallback
        assert all(call.member != "Commit" for call in bus.calls)
        await client.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("reason", ["cancelled", "expired"])
def test_owner_query_cannot_start_commit_after_cancel_or_deadline(reason, monkeypatch):
    class SlowOwnerBus(FakeBus):
        def __init__(self):
            super().__init__()
            self.queries = 0
            self.entered = asyncio.Event()
            self.resume = asyncio.Event()

        async def call(self, message):
            if message.member == "GetNameOwner":
                self.queries += 1
                if self.queries == 2:
                    self.entered.set()
                    await self.resume.wait()
            return await super().call(message)

    async def run():
        bus = SlowOwnerBus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        active = True
        clock = [0.0]
        monkeypatch.setattr(fcitx5, "time", SimpleNamespace(monotonic=lambda: clock[0]))
        deadline = 10.0
        task = asyncio.create_task(
            client.insert("甲", lambda: active, deadline=deadline)
        )
        await asyncio.wait_for(bus.entered.wait(), 1)
        if reason == "expired":
            clock[0] = deadline
        else:
            active = False
        bus.resume.set()
        with pytest.raises(FcitxOutputError) as caught:
            await task
        assert caught.value.code == reason
        assert caught.value.accepted == 0 and not caught.value.safe_to_fallback
        assert all(call.member != "Commit" for call in bus.calls)
        await client.aclose()

    asyncio.run(run())


def test_owner_change_during_no_target_reply_disables_keyboard_fallback():
    class ChangingBus(FakeBus):
        async def call(self, message):
            if message.member == "Commit":
                self.change_owner(":1.99")
            return await super().call(message)

    async def run():
        bus = ChangingBus([reply([3])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: True)
        assert caught.value.code == "owner_changed"
        assert caught.value.accepted == 0 and caught.value.unsent_offset is None
        await client.aclose()

    asyncio.run(run())


def test_newline_and_tab_are_sent_as_individual_text_fragments():
    async def run():
        bus = FakeBus([reply([1])] * 5)
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        assert await client.insert("甲\n乙\tZ", lambda: True) == 5
        sends = [call.body[2] for call in bus.calls if call.member == "Commit"]
        assert sends == ["甲", "\n", "乙", "\t", "Z"]

    asyncio.run(run())


def test_cancel_after_newline_stops_and_prevents_replay():
    async def run():
        bus = FakeBus([reply([1]), reply([1])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        checks = iter([True, True, True, True, False])
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲\n乙\tZ", lambda: next(checks))
        assert caught.value.code == "cancelled"
        assert caught.value.accepted == 2
        assert not caught.value.safe_to_fallback
        assert [call.body[2] for call in bus.calls if call.member == "Commit"] == [
            "甲",
            "\n",
        ]
        with pytest.raises(FcitxOutputError, match="session_failed"):
            await client.insert("乙\tZ", lambda: True)

    asyncio.run(run())


@pytest.mark.parametrize("first", [False, True])
def test_no_target_never_uses_fallback(first, monkeypatch):
    monkeypatch.setattr(fcitx5, "FOCUS_WAIT_SECONDS", 0)

    async def run():
        outcomes = [reply([3])] if not first else [reply([1])] + [reply([3])] * 100
        bus = FakeBus(outcomes)
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert(
                "abc", lambda: True, deadline=fcitx5.time.monotonic() + 0.025
            )
        assert caught.value.code == ("expired" if first else "no_target")
        assert caught.value.unsent_offset == (None if first else 0)
        assert not caught.value.safe_to_fallback
        assert len([call for call in bus.calls if call.member == "Commit"]) >= 1

    asyncio.run(run())


def test_lost_reply_is_never_safe_to_retry():
    async def run():
        bus = FakeBus([TimeoutError("private content")])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("secret", lambda: True)
        assert caught.value.code == "delivery_unknown"
        assert caught.value.uncertain and not caught.value.safe_to_fallback
        assert "secret" not in str(caught.value)
        assert len([call for call in bus.calls if call.member == "Commit"]) == 1
        with pytest.raises(FcitxOutputError) as repeated:
            await client.insert("secret", lambda: True)
        assert repeated.value.code == "session_failed"
        assert not repeated.value.safe_to_fallback

    asyncio.run(run())


def test_cancel_between_sends_stops_without_replay():
    async def run():
        bus = FakeBus([reply([1])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        checks = iter([True, True, False])
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("ab", lambda: next(checks))
        assert caught.value.code == "cancelled"
        assert caught.value.accepted == 1
        assert not caught.value.safe_to_fallback
        assert len([call for call in bus.calls if call.member == "Commit"]) == 1

    asyncio.run(run())


def test_missing_bridge_is_safe_before_any_send():
    async def run():
        bus = FakeBus()

        async def unavailable(message):
            bus.calls.append(message)
            return reply([], MessageType.ERROR)

        bus.call = unavailable
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        with pytest.raises(FcitxOutputError) as caught:
            await client.connect()
        assert caught.value.safe_to_fallback
        assert bus.disconnected
        assert all(call.member != "Commit" for call in bus.calls)

    asyncio.run(run())


def test_cancel_before_first_send_does_not_allow_fallback():
    async def run():
        bus = FakeBus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("a", lambda: False)
        assert caught.value.code == "cancelled"
        assert not caught.value.safe_to_fallback
        assert all(call.member != "Commit" for call in bus.calls)

    asyncio.run(run())


def test_cancelling_in_flight_never_starts_a_second_send():
    async def run():
        bus = FakeBus()
        original = bus.call
        started = asyncio.Event()

        async def call(message):
            if message.member != "Commit":
                return await original(message)
            bus.calls.append(message)
            started.set()
            await asyncio.Event().wait()

        bus.call = call
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        task = asyncio.create_task(client.insert("abc", lambda: True))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len([call for call in bus.calls if call.member == "Commit"]) == 1
        with pytest.raises(FcitxOutputError) as repeated:
            await client.insert("abc", lambda: True)
        assert repeated.value.code == "session_failed"

    asyncio.run(run())


def test_previous_fragment_prevents_whole_task_fallback(monkeypatch):
    monkeypatch.setattr(fcitx5, "FOCUS_WAIT_SECONDS", 0)

    async def run():
        bus = FakeBus([reply([1])] + [reply([3])] * 100)
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        assert await client.insert("甲", lambda: True) == 1
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert(
                "乙", lambda: True, deadline=fcitx5.time.monotonic() + 0.025
            )
        assert caught.value.code == "expired"
        assert caught.value.accepted == 1
        assert not caught.value.safe_to_fallback

    asyncio.run(run())


def test_expired_budget_after_check_never_sends(monkeypatch):
    async def run():
        bus = FakeBus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        moments = iter([0.5, 1.1])
        monkeypatch.setattr(
            fcitx5, "time", SimpleNamespace(monotonic=lambda: next(moments))
        )
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: True, deadline=1)
        assert caught.value.code == "expired"
        assert not caught.value.safe_to_fallback
        assert all(call.member != "Commit" for call in bus.calls)

    asyncio.run(run())


@pytest.mark.parametrize("invalid", ["\x00", "\r", "\x7f", "\x85", "\ud800", "\udfff"])
def test_invalid_unicode_rejects_without_sending_and_closes_sequence(invalid):
    async def run():
        bus = FakeBus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert(invalid, lambda: True)
        assert caught.value.code == "unsupported_text"
        assert all(call.member != "Commit" for call in bus.calls)
        with pytest.raises(FcitxOutputError) as repeated:
            await client.insert("a", lambda: True)
        assert repeated.value.code == "session_failed"

    asyncio.run(run())


def test_refused_authorization_never_sends_or_falls_back():
    async def run():
        bus = FakeBus()
        original = bus.call

        async def call(message):
            if message.member == "Begin3":
                bus.calls.append(message)
                return reply([False])
            return await original(message)

        bus.call = call
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        with pytest.raises(FcitxOutputError) as caught:
            await client.connect()
        assert caught.value.code == "authorization_failed"
        assert not caught.value.safe_to_fallback
        assert bus.disconnected
        assert all(message.member != "Commit" for message in bus.calls)

    asyncio.run(run())


def test_cancelling_authorization_preserves_async_cancellation():
    async def run():
        bus = FakeBus()
        original = bus.call
        started = asyncio.Event()

        async def call(message):
            if message.member == "Begin3":
                started.set()
                await asyncio.Event().wait()
            return await original(message)

        bus.call = call
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        task = asyncio.create_task(client.connect())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert bus.disconnected
        assert all(message.member != "Commit" for message in bus.calls)

    asyncio.run(run())


def test_cancelling_aclose_during_remote_cancel_always_cleans_resources():
    async def run():
        bus = FakeBus()
        original = bus.call
        started = asyncio.Event()
        caps = []

        def make_cap(runtime):
            cap = FakeCapability(runtime)
            caps.append(cap)
            return cap

        async def call(message):
            if message.member == "Cancel":
                started.set()
                await asyncio.Event().wait()
            return await original(message)

        bus.call = call
        client = Fcitx5Bridge(bus_factory=lambda: bus, capability_factory=make_cap)
        await client.connect()
        task = asyncio.create_task(client.aclose())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert bus.disconnected
        assert caps[0].token == ""
        assert client._bus is None
        assert client._capability is None

    asyncio.run(run())


def test_server_reports_uncertain_delivery_without_replay():
    async def run():
        bus = FakeBus([reply([2])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲乙", lambda: True)
        assert caught.value.code == "delivery_unknown"
        assert caught.value.uncertain and not caught.value.safe_to_fallback
        with pytest.raises(FcitxOutputError, match="session_failed"):
            await client.insert("甲乙", lambda: True)
        assert len([call for call in bus.calls if call.member == "Commit"]) == 1

    asyncio.run(run())


def test_recording_over_two_minutes_remains_valid_until_real_task_deadline(monkeypatch):
    async def run():
        bus = FakeBus([reply([1])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        monkeypatch.setattr(fcitx5, "time", SimpleNamespace(monotonic=lambda: 181.0))
        assert await client.insert("甲", lambda: True, deadline=600.0) == 1
        assert [
            message.body[2] for message in bus.calls if message.member == "Commit"
        ] == ["甲"]

    asyncio.run(run())


def test_expiry_is_distinct_from_cancellation_and_no_target(monkeypatch):
    async def run():
        bus = FakeBus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        monkeypatch.setattr(fcitx5, "time", SimpleNamespace(monotonic=lambda: 601.0))
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: False, deadline=600.0)
        assert caught.value.code == "expired"
        assert not caught.value.safe_to_fallback
        assert all(message.member != "Commit" for message in bus.calls)

    asyncio.run(run())


def test_confirmed_no_focus_retries_same_sequence_without_replaying_sent_text():
    async def run():
        bus = FakeBus([reply([1]), reply([3]), reply([3]), reply([1])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        assert await client.insert("甲乙", lambda: True) == 2
        calls = [call.body[1:] for call in bus.calls if call.member == "Commit"]
        assert calls == [[0, "甲"], [1, "乙"], [1, "乙"], [1, "乙"]]
        await client.aclose()

    asyncio.run(run())


def test_focus_recovers_after_350ms_without_replaying_prefix():
    class DelayedFocusBus(FakeBus):
        def __init__(self):
            super().__init__()
            self.first_missing = None

        async def call(self, message):
            if message.member != "Commit":
                return await super().call(message)
            self.calls.append(message)
            if message.body[1] == 0:
                return reply([1])
            now = fcitx5.time.monotonic()
            if self.first_missing is None:
                self.first_missing = now
            return reply([1 if now - self.first_missing >= 0.35 else 3])

    async def run():
        bus = DelayedFocusBus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        assert await client.insert("甲乙", lambda: True) == 2
        calls = [call.body[1:] for call in bus.calls if call.member == "Commit"]
        assert calls[0] == [0, "甲"] and len(calls) > 2
        assert all(call == [1, "乙"] for call in calls[1:])
        await client.aclose()

    asyncio.run(run())


def test_waiting_for_focus_checks_cancellation_before_retry():
    async def run():
        bus = FakeBus([reply([3])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        checks = iter([True, True, False])
        with pytest.raises(FcitxOutputError, match="cancelled"):
            await client.insert("甲", lambda: next(checks))
        assert len([x for x in bus.calls if x.member == "Commit"]) == 1
        await client.aclose()

    asyncio.run(run())


def test_protocol_error_is_not_treated_as_unambiguous_no_focus():
    async def run():
        bus = FakeBus([reply([0])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: True)
        assert caught.value.code == "protocol_error"
        assert caught.value.unsent_offset is None
        assert len([x for x in bus.calls if x.member == "Commit"]) == 1
        await client.aclose()

    asyncio.run(run())


def test_ambiguous_reply_after_confirmed_no_focus_is_never_retried():
    async def run():
        bus = FakeBus([reply([3]), TimeoutError("private")])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: True)
        assert caught.value.code == "delivery_unknown"
        assert caught.value.uncertain and caught.value.unsent_offset is None
        assert len([x for x in bus.calls if x.member == "Commit"]) == 2
        await client.aclose()

    asyncio.run(run())


def test_deadline_during_focus_wait_never_retries_or_falls_back(monkeypatch):
    async def run():
        bus = FakeBus([reply([3])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert(
                "甲", lambda: True, deadline=fcitx5.time.monotonic() + 0.005
            )
        assert caught.value.code == "expired"
        assert caught.value.unsent_offset is None
        assert len([x for x in bus.calls if x.member == "Commit"]) == 1
        await client.aclose()

    asyncio.run(run())


def test_inflight_commit_retains_confirmation_window_near_focus_grace(monkeypatch):
    monkeypatch.setattr(fcitx5, "FOCUS_WAIT_SECONDS", 0.1)
    monkeypatch.setattr(fcitx5, "FOCUS_POLL_SECONDS", 0.09)

    class SlowSecondReply(FakeBus):
        async def call(self, message):
            if message.member == "Commit" and any(
                call.member == "Commit" for call in self.calls
            ):
                await asyncio.sleep(0.03)
            return await super().call(message)

    async def run():
        bus = SlowSecondReply([reply([3]), reply([3])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability, timeout=0.08
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert(
                "甲", lambda: True, deadline=fcitx5.time.monotonic() + 1
            )
        assert caught.value.code == "no_target"
        assert caught.value.accepted == 0 and caught.value.unsent_offset == 0
        assert not caught.value.uncertain
        assert len([call for call in bus.calls if call.member == "Commit"]) == 2
        await client.aclose()

    asyncio.run(run())


def test_partial_commit_waits_for_focus_until_task_deadline(monkeypatch):
    monkeypatch.setattr(fcitx5, "FOCUS_WAIT_SECONDS", 0.005)
    monkeypatch.setattr(fcitx5, "FOCUS_POLL_SECONDS", 0.001)

    async def run():
        bus = FakeBus([reply([1])] + [reply([3])] * 100)
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert(
                "甲乙丙", lambda: True, deadline=fcitx5.time.monotonic() + 0.025
            )
        assert caught.value.code == "expired"
        assert caught.value.accepted == 1
        assert caught.value.unsent_offset is None
        calls = [x.body[1:] for x in bus.calls if x.member == "Commit"]
        assert calls[0] == [0, "甲"] and len(calls) > 1
        assert all(call == [1, "乙"] for call in calls[1:])
        await client.aclose()

    asyncio.run(run())


def test_partial_commit_resumes_when_focus_returns_after_grace(monkeypatch):
    monkeypatch.setattr(fcitx5, "FOCUS_WAIT_SECONDS", 0)
    monkeypatch.setattr(fcitx5, "FOCUS_POLL_SECONDS", 0.001)

    async def run():
        bus = FakeBus([reply([1]), reply([3]), reply([3]), reply([1])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        assert await client.insert("甲", lambda: True) == 1
        assert await client.insert("乙", lambda: True) == 1
        calls = [x.body[1:] for x in bus.calls if x.member == "Commit"]
        assert calls == [[0, "甲"], [1, "乙"], [1, "乙"], [1, "乙"]]
        await client.aclose()

    asyncio.run(run())


def test_cancel_during_partial_focus_wait_stops_without_sending_tail(monkeypatch):
    monkeypatch.setattr(fcitx5, "FOCUS_POLL_SECONDS", 0.001)

    async def run():
        bus = FakeBus([reply([1])] + [reply([3])] * 100)
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        assert await client.insert("甲", lambda: True) == 1
        checks = iter([True, True, False])
        with pytest.raises(FcitxOutputError, match="cancelled"):
            await client.insert("乙丙", lambda: next(checks))
        assert [x.body[1:] for x in bus.calls if x.member == "Commit"] == [
            [0, "甲"],
            [1, "乙"],
        ]
        await client.aclose()

    asyncio.run(run())


def test_focus_retry_call_hanging_at_limit_is_unknown_and_never_falls_back(monkeypatch):
    monkeypatch.setattr(fcitx5, "FOCUS_WAIT_SECONDS", 0.025)
    monkeypatch.setattr(fcitx5, "FOCUS_POLL_SECONDS", 0.001)

    class HangingBus(FakeBus):
        async def call(self, message):
            if message.member == "Commit" and any(
                call.member == "Commit" for call in self.calls
            ):
                self.calls.append(message)
                await asyncio.Event().wait()
            return await super().call(message)

    async def run():
        bus = HangingBus([reply([3])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability, timeout=0.08
        )
        await client.connect()
        started = fcitx5.time.monotonic()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: True)
        elapsed = fcitx5.time.monotonic() - started
        assert caught.value.code == "delivery_unknown" and caught.value.uncertain
        assert caught.value.unsent_offset is None and not caught.value.safe_to_fallback
        assert len([x for x in bus.calls if x.member == "Commit"]) == 2
        assert elapsed < 0.5
        with pytest.raises(FcitxOutputError, match="session_failed"):
            await client.insert("甲", lambda: True)
        await client.aclose()

    asyncio.run(run())


def test_cancelled_close_with_filesystem_error_keeps_cancellation_and_releases_lock(
    tmp_path, monkeypatch
):
    import os

    from inkecho.platform.fcitx5_capability import Capability

    async def run():
        bus = FakeBus()
        original_call = bus.call
        started = asyncio.Event()
        caps = []

        def make_cap(_runtime):
            cap = Capability(tmp_path)
            caps.append(cap)
            return cap

        async def call(message):
            if message.member == "Cancel":
                started.set()
                await asyncio.Event().wait()
            return await original_call(message)

        bus.call = call
        client = Fcitx5Bridge(bus_factory=lambda: bus, capability_factory=make_cap)
        await client.connect()
        original_stat = os.stat
        monkeypatch.setattr(
            os,
            "stat",
            lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("private")),
        )
        task = asyncio.create_task(client.aclose())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        monkeypatch.setattr(os, "stat", original_stat)
        assert bus.disconnected
        assert caps[0].fd is None and caps[0].lock_fd is None and caps[0].token == ""
        again = Capability(tmp_path)
        again.close()

    asyncio.run(run())


def test_close_filesystem_error_is_sanitized(tmp_path, monkeypatch):
    import os

    from inkecho.platform.fcitx5_capability import Capability

    async def run():
        bus = FakeBus()
        caps = []

        def make_cap(_runtime):
            cap = Capability(tmp_path)
            caps.append(cap)
            return cap

        client = Fcitx5Bridge(bus_factory=lambda: bus, capability_factory=make_cap)
        await client.connect()
        original_stat = os.stat
        monkeypatch.setattr(
            os,
            "stat",
            lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("private")),
        )
        with pytest.raises(FcitxOutputError, match="cleanup_failed") as caught:
            await client.aclose()
        monkeypatch.setattr(os, "stat", original_stat)
        assert "private" not in str(caught.value)
        assert bus.disconnected and caps[0].token == "" and caps[0].lock_fd is None
        again = Capability(tmp_path)
        again.close()

    asyncio.run(run())


def test_partial_focus_gap_backs_off_and_resumes_only_unsent_character():
    class RecoveringBus(FakeBus):
        def __init__(self):
            super().__init__()
            self.start = None
            self.commit_times = []

        async def call(self, message):
            if message.member != "Commit":
                return await super().call(message)
            self.calls.append(message)
            now = fcitx5.time.monotonic()
            self.commit_times.append(now)
            if self.start is None:
                self.start = now
                return reply([1])
            return reply([1 if len(self.commit_times) >= 7 else 3])

    async def run():
        bus = RecoveringBus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        assert (
            await client.insert(
                "甲乙", lambda: True, deadline=fcitx5.time.monotonic() + 2
            )
            == 2
        )
        calls = [call.body[1:] for call in bus.calls if call.member == "Commit"]
        assert calls[0] == [0, "甲"]
        assert all(call == [1, "乙"] for call in calls[1:])
        assert len(calls) == 7
        assert bus.commit_times[-1] - bus.start >= 0.20  # fixed polling takes 0.05 s
        await client.aclose()

    asyncio.run(run())


def test_cancel_during_backoff_stops_before_next_commit():
    async def run():
        bus = FakeBus([reply([1])] + [reply([3])] * 30)
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        active = True
        task = asyncio.create_task(client.insert("甲乙", lambda: active))
        await asyncio.sleep(0.18)
        active = False
        calls_at_cancel = len([call for call in bus.calls if call.member == "Commit"])
        with pytest.raises(FcitxOutputError) as caught:
            await asyncio.wait_for(task, 0.06)
        assert caught.value.code == "cancelled" and caught.value.accepted == 1
        assert (
            len([call for call in bus.calls if call.member == "Commit"])
            == calls_at_cancel
        )
        await client.aclose()

    asyncio.run(run())


def test_first_focus_gap_backs_off_but_fallback_retains_zero_prefix():
    async def run():
        bus = FakeBus([reply([3])] * 100)
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        start = fcitx5.time.monotonic()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("甲", lambda: True, deadline=start + 2)
        elapsed = fcitx5.time.monotonic() - start
        sends = [call.body[1:] for call in bus.calls if call.member == "Commit"]
        assert caught.value.code == "no_target"
        assert caught.value.accepted == 0 and caught.value.unsent_offset == 0
        assert not caught.value.uncertain
        assert elapsed >= 0.49
        assert 1 <= len(sends) <= 16
        assert all(call == [0, "甲"] for call in sends)
        await client.aclose()

    asyncio.run(run())


def test_first_focus_gap_recovers_without_replay_and_cancel_is_prompt():
    class RecoveringBus(FakeBus):
        def __init__(self):
            super().__init__()
            self.first = None

        async def call(self, message):
            if message.member != "Commit":
                return await super().call(message)
            self.calls.append(message)
            now = fcitx5.time.monotonic()
            if self.first is None:
                self.first = now
            return reply([1 if now - self.first >= 0.12 else 3])

    async def run():
        bus = RecoveringBus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        assert await client.insert("甲", lambda: True) == 1
        calls = [call.body[1:] for call in bus.calls if call.member == "Commit"]
        assert all(call == [0, "甲"] for call in calls)
        assert len(calls) < 10
        await client.aclose()

        bus = FakeBus([reply([3])] * 100)
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        active = True
        task = asyncio.create_task(client.insert("乙", lambda: active))
        await asyncio.sleep(0.13)
        active = False
        count = sum(call.member == "Commit" for call in bus.calls)
        with pytest.raises(FcitxOutputError) as caught:
            await asyncio.wait_for(task, 0.06)
        assert caught.value.code == "cancelled" and caught.value.accepted == 0
        assert sum(call.member == "Commit" for call in bus.calls) == count
        await client.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("member", ["AddMatch", "GetNameOwner", "Introspect", "Begin3"])
def test_untrusted_setup_reply_never_prepares_bridge(member):
    class SpoofBus(FakeBus):
        async def call(self, message):
            result = await super().call(message)
            if message.member == member:
                result.sender = ":1.99"
            return result

    async def run():
        bus = SpoofBus()
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        with pytest.raises(FcitxOutputError):
            await bridge.connect(expected_owner=":1.42")
        assert bus.disconnected
        assert all(call.member != "Commit" for call in bus.calls)

    asyncio.run(run())


def test_untrusted_commit_reply_is_uncertain_and_never_retried():
    async def run():
        bus = FakeBus([reply([3], sender=":1.99")])
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await bridge.connect(expected_owner=":1.42")
        with pytest.raises(FcitxOutputError) as caught:
            await bridge.insert("甲乙", lambda: True)
        assert caught.value.code == "delivery_unknown"
        assert caught.value.uncertain is True and caught.value.unsent_offset is None
        assert len([call for call in bus.calls if call.member == "Commit"]) == 1
        await bridge.aclose()

    asyncio.run(run())


def test_untrusted_owner_query_before_commit_stops_without_send():
    class SpoofOwner(FakeBus):
        def __init__(self):
            super().__init__()
            self.queries = 0

        async def call(self, message):
            result = await super().call(message)
            if message.member == "GetNameOwner":
                self.queries += 1
                if self.queries == 2:
                    result.sender = ":1.99"
            return result

    async def run():
        bus = SpoofOwner()
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await bridge.connect(expected_owner=":1.42")
        with pytest.raises(FcitxOutputError, match="owner_changed"):
            await bridge.insert("甲", lambda: True)
        assert all(call.member != "Commit" for call in bus.calls)
        await bridge.aclose()

    asyncio.run(run())


def test_abort_preflight_disconnects_without_waiting_for_remote_cancel():
    async def run():
        bus = FakeBus()
        caps = []

        def make_cap(runtime):
            cap = FakeCapability(runtime)
            caps.append(cap)
            return cap

        client = Fcitx5Bridge(bus_factory=lambda: bus, capability_factory=make_cap)
        await client.connect()
        await client.abort_preflight()
        assert bus.disconnected and caps[0].token == ""
        assert client._bus is None and client._capability is None
        assert not any(call.member in ("Cancel", "Commit") for call in bus.calls)

    asyncio.run(run())


def test_abort_preflight_refuses_after_uncertain_commit():
    async def run():
        bus = FakeBus([reply([2])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError, match="delivery_unknown"):
            await client.insert("甲", lambda: True)
        with pytest.raises(FcitxOutputError):
            await client.abort_preflight()
        assert not bus.disconnected
        await client.aclose()
        assert bus.disconnected
        assert sum(call.member == "Commit" for call in bus.calls) == 1
        assert sum(call.member == "Cancel" for call in bus.calls) == 1

    asyncio.run(run())


def test_abort_preflight_sanitizes_capability_cleanup_failure():
    async def run():
        class BrokenCapability(FakeCapability):
            def close(self):
                super().close()
                raise OSError("private path")

        bus = FakeBus()
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=BrokenCapability
        )
        await bridge.connect()
        with pytest.raises(FcitxOutputError, match="cleanup_failed") as exc:
            await bridge.abort_preflight()
        assert "private path" not in str(exc.value)
        assert bus.disconnected and bridge._bus is None and bridge._capability is None

    asyncio.run(run())


def test_router_cancel_preserved_on_real_bridge_cleanup_failure():
    from inkecho.platform.output_router import OutputRouter

    async def run():
        class BrokenCapability(FakeCapability):
            def close(self):
                super().close()
                raise OSError("private cleanup detail")

        bus = FakeBus()
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=BrokenCapability
        )
        router = OutputRouter(object(), bridge_factory=lambda: bridge)
        diagnostics = []
        router.set_diagnostic_handler(diagnostics.append)
        started = asyncio.Event()
        calls = 0

        async def detect():
            nonlocal calls
            calls += 1
            if calls == 2:
                started.set()
                await asyncio.Event().wait()
            return ("fcitx", ":1.42")

        router._system_detector = detect
        await router.prepare_task("auto")
        task = asyncio.create_task(router.insert("甲", lambda: True))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert bus.disconnected and bridge._capability is None
        assert diagnostics == ["input_cleanup_failed"]
        assert not any(call.member == "Commit" for call in bus.calls)

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["cancel", "predicate", "expired", "service"])
def test_router_begin_cleanup_failure_disconnects_and_never_sends(mode):
    import time

    from inkecho.platform.output_router import OutputRouter, OutputRouterError

    async def run():
        started = asyncio.Event()

        class BrokenCapability(FakeCapability):
            def close(self):
                raise OSError("sensitive cleanup path")

        class BeginBus(FakeBus):
            async def call(self, message):
                if message.member == "Begin3":
                    self.calls.append(message)
                    started.set()
                    if mode == "service":
                        raise OSError("service disappeared")
                    await asyncio.Event().wait()
                return await super().call(message)

        bus = BeginBus()
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=BrokenCapability
        )
        router = OutputRouter(object(), bridge_factory=lambda: bridge)
        diagnostics = []
        router.set_diagnostic_handler(diagnostics.append)

        async def detector():
            return ("fcitx", ":1.42")

        router._system_detector = detector
        active = [True]
        await router.prepare_task("auto")
        deadline = time.monotonic() + 0.12 if mode == "expired" else None
        task = asyncio.create_task(
            router.insert("甲", lambda: active[0], deadline=deadline)
        )
        await started.wait()
        if mode == "cancel":
            task.cancel()
        elif mode == "predicate":
            active[0] = False
        expected = asyncio.CancelledError if mode == "cancel" else OutputRouterError
        with pytest.raises(expected) as caught:
            await asyncio.wait_for(task, 1)
        if mode in {"predicate", "expired"}:
            assert caught.value.code == (
                "expired" if mode == "expired" else "input_cancelled"
            )
        if mode == "service":
            assert caught.value.code == "fcitx_cleanup_failed"
        assert diagnostics == ["input_cleanup_failed"]
        assert bus.disconnected
        assert not any(call.member == "Commit" for call in bus.calls)

    asyncio.run(run())


@pytest.mark.parametrize("cancel", [True, False])
def test_explicit_begin_cleanup_failure_reports_and_disconnects(cancel):
    from inkecho.platform.output_router import OutputRouter, OutputRouterError

    async def run():
        started = asyncio.Event()

        class BrokenCapability(FakeCapability):
            def close(self):
                raise OSError("sensitive cleanup path")

        class BeginBus(FakeBus):
            async def call(self, message):
                if message.member == "Begin3":
                    self.calls.append(message)
                    started.set()
                    if cancel:
                        await asyncio.Event().wait()
                    raise OSError("service disappeared")
                return await super().call(message)

        bus = BeginBus()
        bridge = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=BrokenCapability
        )
        router = OutputRouter(object(), bridge_factory=lambda: bridge)
        router._explicit_fcitx_detector = lambda: asyncio.sleep(0, result=":1.42")
        diagnostics = []
        router.set_diagnostic_handler(diagnostics.append)
        task = asyncio.create_task(router.prepare_task("fcitx"))
        await started.wait()
        if cancel:
            task.cancel()
        with pytest.raises(
            asyncio.CancelledError if cancel else OutputRouterError
        ) as caught:
            await task
        if not cancel:
            assert caught.value.code == "fcitx_cleanup_failed"
        assert diagnostics == ["input_cleanup_failed"]
        assert bus.disconnected
        assert not any(call.member == "Commit" for call in bus.calls)

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["owner_replaced", "commit_reply_lost"])
def test_auto_router_never_replays_after_service_failure_and_next_task_recovers(
    failure,
):
    from inkecho.platform.output_router import OutputRouter, OutputRouterError

    async def run():
        class Keyboard:
            def __init__(self):
                self.sent = []

            async def insert(self, text, *args, **kwargs):
                self.sent.append(text)
                return len(text)

        class FailedBus(FakeBus):
            async def call(self, message):
                if message.member == "Commit":
                    self.calls.append(message)
                    if failure == "owner_replaced":
                        self.change_owner(":1.43")
                        return reply([1], sender=":1.42")
                    raise TimeoutError("synthetic lost reply")
                return await super().call(message)

        class FreshBus(FakeBus):
            def __init__(self):
                super().__init__([reply([1], sender=":1.43")])
                self.owner = ":1.43"

            async def call(self, message):
                response = await super().call(message)
                if message.member in {"Introspect", "Begin3", "Cancel"}:
                    response.sender = self.owner
                return response

        failed, fresh = FailedBus(), FreshBus()
        buses = iter([failed, fresh])
        keyboard = Keyboard()
        router = OutputRouter(
            keyboard,
            bridge_factory=lambda: Fcitx5Bridge(
                bus_factory=lambda: next(buses), capability_factory=FakeCapability
            ),
        )
        owner = [":1.42"]

        async def detect():
            return ("fcitx", owner[0])

        router._system_detector = detect
        await router.prepare_task("auto")
        with pytest.raises(OutputRouterError) as caught:
            await router.insert("甲乙", lambda: True)
        assert caught.value.code == (
            "partial_input_failed"
            if failure == "owner_replaced"
            else "fcitx_delivery_unknown"
        )
        assert [m.body[2] for m in failed.calls if m.member == "Commit"] == ["甲"]
        assert keyboard.sent == [] and failed.disconnected and router.selected is None
        owner[0] = ":1.43"
        assert await router.prepare_task("auto") == "keyboard"
        assert await router.insert("丙", lambda: True) == 1
        assert [m.body[2] for m in fresh.calls if m.member == "Commit"] == ["丙"]
        assert keyboard.sent == [] and fresh.disconnected and router.selected is None

    asyncio.run(run())


@pytest.mark.parametrize("cancel_mode", ["task", "predicate"])
def test_auto_cancel_during_commit_never_replays_and_next_task_is_clean(cancel_mode):
    from inkecho.platform.output_router import OutputRouter, OutputRouterError

    async def run():
        started, release = asyncio.Event(), asyncio.Event()

        class Keyboard:
            def __init__(self):
                self.sent = []

            async def insert(self, text, *args, **kwargs):
                self.sent.append(text)
                return len(text)

        class InFlightBus(FakeBus):
            async def call(self, message):
                if message.member == "Commit":
                    self.calls.append(message)
                    started.set()
                    await release.wait()
                    return reply([1])
                return await super().call(message)

        first = InFlightBus()
        second = FakeBus([reply([1])])
        buses = iter([first, second])
        keyboard = Keyboard()
        router = OutputRouter(
            keyboard,
            bridge_factory=lambda: Fcitx5Bridge(
                bus_factory=lambda: next(buses), capability_factory=FakeCapability
            ),
        )

        async def detect():
            return ("fcitx", ":1.42")

        router._system_detector = detect
        active = [True]
        await router.prepare_task("auto")
        task = asyncio.create_task(router.insert("甲乙", lambda: active[0]))
        await started.wait()
        if cancel_mode == "task":
            task.cancel()
        else:
            active[0] = False
            release.set()
        expected = (
            asyncio.CancelledError if cancel_mode == "task" else OutputRouterError
        )
        with pytest.raises(expected):
            await task
        assert [m.body[2] for m in first.calls if m.member == "Commit"] == ["甲"]
        assert first.disconnected and keyboard.sent == [] and router.selected is None
        await router.prepare_task("auto")
        assert await router.insert("丙", lambda: True) == 1
        assert [m.body[2] for m in second.calls if m.member == "Commit"] == ["丙"]
        assert second.disconnected and keyboard.sent == []

    asyncio.run(run())
