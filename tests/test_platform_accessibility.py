import asyncio

import pytest
from dbus_next import Message, MessageType

from inkecho.platform.accessibility import (
    AccessibilityInput,
    AccessibleTarget,
    InputUnavailable,
    has_state,
)


def backend_with_target():
    backend = AccessibilityInput()
    target = AccessibleTarget((":1.1", "/target"), (":1.1", "/window"), 0, 3)
    backend.target = target
    return backend, target


def test_focus_away_then_back_never_revives_token():
    backend, target = backend_with_target()
    for focused in (0, 1):
        backend._event(
            Message(
                message_type=MessageType.SIGNAL,
                sender=":1.1",
                path="/target",
                interface="org.a11y.atspi.Event.Object",
                member="StateChanged",
                signature="si",
                body=["focused", focused],
            )
        )
    assert not backend.target_is_current(target)


def test_capture_generation_sees_focus_events_without_active_token():
    backend = AccessibilityInput()
    backend._event(
        Message(
            message_type=MessageType.SIGNAL,
            sender=":1.1",
            path="/target",
            interface="org.a11y.atspi.Event.Object",
            member="StateChanged",
            signature="si",
            body=["focused", 1],
        )
    )
    assert backend.generation == 1


def test_cancellation_during_last_focus_query_prevents_dispatch():
    async def run():
        backend, target = backend_with_target()
        allowed, queries, methods = True, 0, []

        async def current(_):
            nonlocal allowed, queries
            queries += 1
            if queries == 2:
                allowed = False
            return True

        async def call(_address, _interface, member, *_):
            methods.append(member)
            return [0]

        backend._current, backend._call = current, call
        with pytest.raises(InputUnavailable):
            await backend.inject(target, "中文", lambda: allowed)
        assert methods == ["GetNSelections"]

    asyncio.run(run())


def test_utf8_byte_length_and_single_use_target():
    async def run():
        backend, target = backend_with_target()
        calls = []

        async def current(_):
            return True

        async def call(address, interface, member, *args):
            calls.append((address, interface, member, args))
            return [0] if member == "GetNSelections" else [True]

        backend._current, backend._call = current, call
        await backend.inject(target, "中😀", lambda: True)
        assert calls[-1][0] == target.address
        assert calls[-1][-1] == ("isi", [3, "中😀", 7])
        assert backend.target_is_current(target)
        with pytest.raises(InputUnavailable):
            await backend.inject(target, "重复", lambda: True)

    asyncio.run(run())


def test_state_bitmask_spans_words():
    assert has_state([0, 2], 33)
    assert not has_state([0], 33)
