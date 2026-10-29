import asyncio

import pytest
from test_fcitx5 import FakeBus, FakeCapability, reply

from inkecho.platform.fcitx5 import INTERFACE, Fcitx5Bridge, FcitxOutputError
from inkecho.streaming_output import StreamingOutput, TextDelta

XML = (
    "<node>"
    f'<interface name="{INTERFACE}">'
    '<method name="Begin"/>'
    '<method name="Commit"/>'
    '<method name="Begin3"/>'
    '<method name="Begin4">'
    '<arg type="s"/>'
    '<arg type="u" direction="in"/>'
    '<arg type="b" direction="out"/>'
    "</method>"
    '<method name="CommitBatch">'
    '<arg type="s"/>'
    '<arg type="u"/>'
    '<arg type="s"/>'
    '<arg type="u" direction="out"/>'
    "</method>"
    '<method name="Cancel">'
    '<arg type="s"/>'
    '<arg type="b" direction="out"/>'
    "</method>"
    "</interface>"
    "</node>"
)


class Bus(FakeBus):
    def __init__(self, outcomes=(), xml=XML):
        super().__init__(outcomes)
        self.xml = xml

    async def call(self, m):
        if m.member == "Introspect":
            self.calls.append(m)
            return reply([self.xml])
        if m.member == "Begin4":
            self.calls.append(m)
            assert m.body[1] == 4
            r = reply([True])
            r.signature = "b"
            return r
        if m.member == "CommitBatch":
            self.calls.append(m)
            r = self.outcomes.pop(0) if self.outcomes else reply([1])
            r.signature = getattr(r, "signature", "u")
            return r
        return await super().call(m)


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x.replace('name="CommitBatch"', 'name="Wrong"'),
        lambda x: x.replace(
            '<arg type="u" direction="out"/></method><method name="Cancel"',
            '<arg type="b" direction="out"/></method><method name="Cancel"',
        ),
        lambda x: x.replace(
            '<arg type="b" direction="out"/></method></interface>',
            '<arg type="u" direction="out"/></method></interface>',
        ),
        lambda x: x.replace(
            '<method name="Begin4">', '<method name="Begin4"/><method name="Begin4">'
        ),
    ],
)
def test_new_advertisement_must_be_complete_and_exact(change):
    async def run():
        b = Bus(xml=change(XML))
        c = Fcitx5Bridge(bus_factory=lambda: b, capability_factory=FakeCapability)
        with pytest.raises(FcitxOutputError, match="composition_guard_unavailable"):
            await c.connect()
        assert b.disconnected and not any(
            x.member in {"Begin4", "CommitBatch", "Commit"} for x in b.calls
        )

    asyncio.run(run())


@pytest.mark.parametrize("text", ["甲乙\n\n\n丙\n", "\n甲", "\n\n\n"])
def test_new_protocol_general_direct_text_offsets_and_first_callback(text):
    async def run():
        b = Bus()
        c = Fcitx5Bridge(bus_factory=lambda: b, capability_factory=FakeCapability)
        await c.connect()
        assert c.supports_neighbor_batch
        first = []
        assert await c.insert(text, lambda: True, on_first_sent=first.append) == len(
            text
        )
        units = [m.body[2] for m in b.calls if m.member == "CommitBatch"]
        assert "".join(units) == text and all(u != "\n" and len(u) <= 3 for u in units)
        assert len(first) == 1 and c._accepted == len(text)
        assert [m.body[1] for m in b.calls if m.member == "CommitBatch"] == list(
            range(len(units))
        )
        await c.aclose()
        assert not c.supports_neighbor_batch

    asyncio.run(run())


def test_old_running_protocol_keeps_plain_text_but_never_attempts_lf():
    async def run():
        b = FakeBus([reply([1])])
        c = Fcitx5Bridge(bus_factory=lambda: b, capability_factory=FakeCapability)
        await c.connect()
        assert not c.supports_neighbor_batch
        assert await c.insert("甲", lambda: True) == 1
        with pytest.raises(FcitxOutputError) as e:
            await c.insert("乙\n", lambda: True)
        assert e.value.code == "linefeed_protocol_unavailable" and e.value.accepted == 1
        assert [m.body[2] for m in b.calls if m.member == "Commit"] == ["甲"]
        with pytest.raises(FcitxOutputError, match="session_failed"):
            await c.insert("乙", lambda: True)
        await c.aclose()

    asyncio.run(run())


def test_malformed_batch_reply_is_uncertain_and_terminal():
    async def run():
        r = reply([1])
        r.signature = "i"
        b = Bus([r])
        c = Fcitx5Bridge(bus_factory=lambda: b, capability_factory=FakeCapability)
        await c.connect()
        with pytest.raises(FcitxOutputError) as e:
            await c.insert("甲\n", lambda: True)
        assert (
            e.value.code == "delivery_unknown"
            and e.value.uncertain
            and e.value.accepted == 0
        )
        with pytest.raises(FcitxOutputError, match="session_failed"):
            await c.insert("甲\n", lambda: True)
        assert len([x for x in b.calls if x.member == "CommitBatch"]) == 1
        await c.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("enabled", [False, True])
def test_stream_scope_only_prepares_after_body_and_keyboard_has_no_tail(enabled):
    async def run():
        calls = []
        prepares = []

        async def prepare():
            prepares.append(True)
            return enabled

        async def send(t):
            calls.append(t)
            return len(t)

        s = StreamingOutput(
            send, lambda: True, prepare=prepare, batch_enabled=lambda: enabled
        )
        task = asyncio.create_task(s.run())
        await asyncio.sleep(0)
        assert not prepares
        await s.append(TextDelta(0, "甲"))
        await asyncio.sleep(0)
        assert prepares == [True]
        assert calls == ([] if enabled else ["甲"])
        await s.finish("甲")
        assert await task == 1
        assert calls == ["甲"]

    asyncio.run(run())


def test_confirmed_zero_handoff_flushes_tail_and_restores_chunk_timing():
    async def run():
        enabled = True
        calls = []

        async def prepare():
            return True

        async def send(t):
            nonlocal enabled
            calls.append(t)
            enabled = False
            return len(t)

        s = StreamingOutput(
            send, lambda: True, prepare=prepare, batch_enabled=lambda: enabled
        )
        task = asyncio.create_task(s.run())
        await s.append(TextDelta(0, "甲\n乙"))
        await asyncio.sleep(0)
        assert "".join(calls) == "甲\n乙" and s._planner is None
        await s.append(TextDelta(3, "丙"))
        await asyncio.sleep(0)
        assert "".join(calls) == "甲\n乙丙"
        await s.finish("甲\n乙丙")
        assert await task == 4

    asyncio.run(run())


def test_new_fail_closed_diagnostics_are_registered(tmp_path):
    from inkecho.app import KEYBOARD_LABELS
    from inkecho.logging import DiagnosticLog

    log = DiagnosticLog(tmp_path)
    try:
        for code in ("fcitx_linefeed_protocol_unavailable", "fcitx_unsupported_text"):
            assert code in KEYBOARD_LABELS
            log.record("error", code)
    finally:
        log.close()


def test_first_neighbor_batch_cancel_counts_all_attempted_scalars_once():
    async def run():
        bus = Bus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        active = True
        callbacks = []

        def first(at):
            nonlocal active
            callbacks.append(at)
            active = False

        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("\n甲乙", lambda: active, on_first_sent=first)
        assert caught.value.code == "cancelled"
        assert caught.value.accepted == 2 and len(callbacks) == 1
        assert len([m for m in bus.calls if m.member == "CommitBatch"]) == 1
        with pytest.raises(FcitxOutputError, match="session_failed"):
            await client.insert("乙", lambda: True)
        await client.aclose()

    asyncio.run(run())


def test_partial_batch_unknown_is_terminal_without_fallback():
    async def run():
        bus = Bus([reply([1]), reply([2])])
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        with pytest.raises(FcitxOutputError) as caught:
            await client.insert("\n甲乙\n", lambda: True)
        assert caught.value.code == "delivery_unknown" and caught.value.uncertain
        assert caught.value.accepted == 2 and not caught.value.safe_to_fallback
        assert len([m for m in bus.calls if m.member == "CommitBatch"]) == 2
        await client.aclose()

    asyncio.run(run())


def test_owner_replacement_during_begin4_does_not_enable_batch():
    async def run():
        bus = Bus()
        original = bus.call

        async def call(message):
            response = await original(message)
            if message.member == "Begin4":
                bus.change_owner(":1.99")
            return response

        bus.call = call
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        with pytest.raises(FcitxOutputError, match="authorization_failed"):
            await client.connect()
        assert not client.supports_neighbor_batch and bus.disconnected
        assert not any(m.member == "CommitBatch" for m in bus.calls)

    asyncio.run(run())


def test_complete_iterator_matches_fragment_planner_and_is_lazy():
    import itertools

    from inkecho.text_units import NeighborPlanner, iter_text_units

    for length in range(2, 9):
        for chars in itertools.product("A\n", repeat=length):
            text = "".join(chars)
            expected = list(iter_text_units(text))
            for split in range(length + 1):
                planner = NeighborPlanner()
                assert (
                    planner.feed(text[:split])
                    + planner.feed(text[split:])
                    + planner.finish()
                    == expected
                )

    class Tracked(str):
        accesses = 0

        def __getitem__(self, index):
            self.accesses += 1
            return super().__getitem__(index)

    text = Tracked("A" * 128_000)
    units = iter_text_units(text)
    assert text.accesses == 0
    assert next(units) == "A" and text.accesses <= 2


def test_large_direct_text_cancel_does_not_materialize_or_send_remainder():
    async def run():
        bus = Bus()
        client = Fcitx5Bridge(
            bus_factory=lambda: bus, capability_factory=FakeCapability
        )
        await client.connect()
        active = True

        def first(_):
            nonlocal active
            active = False

        with pytest.raises(FcitxOutputError) as caught:
            await client.insert(
                "甲" * 128_000 + "\n", lambda: active, on_first_sent=first
            )
        assert caught.value.code == "cancelled" and caught.value.accepted == 1
        assert len([m for m in bus.calls if m.member == "CommitBatch"]) == 1
        await client.aclose()

    asyncio.run(run())
