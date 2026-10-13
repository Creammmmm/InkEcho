"""Historical alpha6 captured-target behavior, excluded from production."""

import asyncio
import os
from pathlib import Path

import pytest
from dbus_next import Message, MessageType
from historical_accessibility import (
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


def owned_process_backend(process_id):
    from historical_accessibility import (
        ACTIVE,
        EDITABLE_STATE,
        FOCUSED,
        ROOT,
    )

    backend = AccessibilityInput()
    app = (":1.27", "/application")
    window = (":1.27", "/window")
    control = (":1.27", "/control")
    owner = {"pid": process_id}
    calls = []

    async def call(address, _interface, member, _signature="", body=None):
        calls.append((address, member, body))
        if member == "GetConnectionUnixProcessID":
            if isinstance(owner["pid"], Exception):
                raise owner["pid"]
            return [owner["pid"]]
        if member == "GetChildren":
            return [{ROOT: [app], app: [window], window: [control]}[address]]
        if member == "GetInterfaces":
            return [["org.a11y.atspi.EditableText"]]
        if member == "GetRoleName":
            return ["text"]
        if member == "GetNSelections":
            return [0]
        if member == "InsertText":
            return [True]
        raise AssertionError(member)

    async def state(address):
        return (
            [1 << ACTIVE]
            if address == window
            else [(1 << FOCUSED) | (1 << EDITABLE_STATE)]
        )

    async def property_value(_address, _interface, _name):
        return 3

    backend._call = call
    backend._state = state
    backend._property = property_value
    return backend, owner, calls


def test_capture_rejects_own_process_before_returning_target():
    async def run():
        backend, _owner, calls = owned_process_backend(os.getpid())
        with pytest.raises(InputUnavailable, match="own process"):
            await backend.capture_target()
        assert backend.target is None
        assert not any(member == "InsertText" for _, member, _ in calls)
        assert calls[-1] == (
            ("org.freedesktop.DBus", "/org/freedesktop/DBus"),
            "GetConnectionUnixProcessID",
            [":1.27"],
        )

    asyncio.run(run())


def test_external_process_passes_capture_and_final_owner_checks():
    async def run():
        backend, _owner, calls = owned_process_backend(os.getpid() + 1)
        target = await backend.capture_target()
        assert target.process_id == os.getpid() + 1
        await backend.inject(target, "中文", lambda: True)
        assert calls[-1][1] == "InsertText"
        assert (
            sum(member == "GetConnectionUnixProcessID" for _, member, _ in calls) == 4
        )

    asyncio.run(run())


@pytest.mark.parametrize("pid", [InputUnavailable("Disconnected"), 0, True, "123"])
def test_unverifiable_owner_fails_closed(pid):
    async def run():
        backend, _owner, calls = owned_process_backend(pid)
        with pytest.raises(InputUnavailable, match="could not be verified"):
            await backend.capture_target()
        assert backend.target is None
        assert not any(member == "InsertText" for _, member, _ in calls)

    asyncio.run(run())


def test_owner_recheck_refuses_input_if_identity_no_longer_matches():
    async def run():
        backend, owner, calls = owned_process_backend(os.getpid() + 1)
        target = await backend.capture_target()
        owner["pid"] = os.getpid()
        with pytest.raises(InputUnavailable):
            await backend.inject(target, "NEVER_INSERT_OWN_PROCESS", lambda: True)
        assert not any(member == "InsertText" for _, member, _ in calls)

    asyncio.run(run())


def test_well_known_bus_alias_is_not_trusted_for_ownership():
    async def run():
        backend, _owner, calls = owned_process_backend(123)
        with pytest.raises(InputUnavailable, match="could not be verified"):
            await backend._external_process_id(("org.example.Editor", "/control"))
        assert calls == []

    asyncio.run(run())


@pytest.mark.skipif(
    os.environ.get("INKECHO_TEST_ACCESSIBILITY") != "1",
    reason="requires the actual desktop accessibility bus",
)
def test_live_process_ownership_without_desktop_document_access():
    import json
    import subprocess
    import sys

    from historical_accessibility import UnsupportedTarget

    child_code = f"""
import asyncio
import json
import os
import sys
sys.path.insert(
    0, {str(Path(__file__).resolve().parents[1] / "scripts" / "feasibility")!r}
)
from historical_accessibility import AccessibilityInput
async def run():
    backend = AccessibilityInput()
    try:
        await backend.connect()
        print(json.dumps([backend.bus.unique_name, os.getpid()]), flush=True)
        await asyncio.to_thread(sys.stdin.readline)
    finally:
        backend.close()
asyncio.run(run())
"""

    async def run():
        backend = AccessibilityInput()
        child = subprocess.Popen(
            [sys.executable, "-c", child_code],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            name, pid = json.loads(
                await asyncio.wait_for(asyncio.to_thread(child.stdout.readline), 10)
            )
            await backend.connect()
            with pytest.raises(UnsupportedTarget, match="own process"):
                await backend._external_process_id(
                    (backend.bus.unique_name, "/owned-test")
                )
            assert await backend._external_process_id((name, "/external-test")) == pid
            child.stdin.write("quit\n")
            child.stdin.flush()
            await asyncio.to_thread(child.wait, 5)
            with pytest.raises(UnsupportedTarget, match="could not be verified"):
                await backend._external_process_id((name, "/external-test"))
        finally:
            backend.close()
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)

    asyncio.run(run())


def state_event(path, state, enabled, *, sender=":1.1"):
    return Message(
        message_type=MessageType.SIGNAL,
        sender=sender,
        path=path,
        interface="org.a11y.atspi.Event.Object",
        member="StateChanged",
        signature="si",
        body=[state, enabled],
    )


@pytest.mark.parametrize("sender", [":1.1", ":1.99"])
@pytest.mark.parametrize(
    "state,enabled", [("defunct", 1), ("focused", 0), ("active", 0)]
)
def test_unrelated_notification_or_secondary_process_exit_keeps_target(
    sender, state, enabled
):
    backend, target = backend_with_target()
    lost = []
    backend.on_focus_lost = lambda: lost.append(True)
    backend._event(state_event("/unrelated", state, enabled, sender=sender))
    assert backend.target_is_current(target)
    assert lost == []


@pytest.mark.parametrize(
    "path,state,enabled",
    [
        ("/target", "focused", 0),
        ("/window", "active", 0),
        ("/target", "defunct", 1),
        ("/window", "defunct", 1),
    ],
)
def test_captured_control_or_window_loss_invalidates_immediately(path, state, enabled):
    backend, target = backend_with_target()
    lost = []
    backend.on_focus_lost = lambda: lost.append(True)
    backend._event(state_event(path, state, enabled))
    assert not backend.target_is_current(target)
    assert lost == [True]
    backend._event(state_event("/target", "focused", 1))
    backend._event(state_event("/window", "active", 1))
    assert not backend.target_is_current(target)
    assert lost == [True]


@pytest.mark.parametrize("still_focused", [False, True])
def test_foreign_focus_gain_checks_actual_captured_target(still_focused):
    async def run():
        backend, target = backend_with_target()
        calls, lost = [], []
        backend.on_focus_lost = lambda: lost.append(True)

        async def current(token):
            calls.append(token)
            return still_focused

        backend._current = current
        backend._event(state_event("/notification", "focused", 1, sender=":1.99"))
        pending = backend._verification
        assert backend.target_is_current(target)
        await pending
        assert calls == [target]
        assert backend.target_is_current(target) == still_focused
        assert lost == ([] if still_focused else [True])

    asyncio.run(run())


def test_foreign_verification_cannot_revive_target_after_focus_away_and_back():
    async def run():
        backend, target = backend_with_target()
        entered, release = asyncio.Event(), asyncio.Event()
        lost = []
        backend.on_focus_lost = lambda: lost.append(True)

        async def current(_):
            entered.set()
            await release.wait()
            return True

        backend._current = current
        backend._event(state_event("/other", "active", 1, sender=":1.99"))
        pending = backend._verification
        await entered.wait()
        backend._event(state_event("/target", "focused", 0))
        backend._event(state_event("/target", "focused", 1))
        release.set()
        await pending
        assert not backend.target_is_current(target)
        assert lost == [True]

    asyncio.run(run())


def test_late_foreign_verification_cannot_cancel_new_target():
    async def run():
        backend, target = backend_with_target()
        entered, release = asyncio.Event(), asyncio.Event()
        lost = []
        backend.on_focus_lost = lambda: lost.append(True)

        async def current(_):
            entered.set()
            await release.wait()
            return False

        backend._current = current
        backend._event(state_event("/other", "focused", 1, sender=":1.99"))
        pending = backend._verification
        await entered.wait()
        backend.generation += 1
        new_target = AccessibleTarget(
            target.address, target.window, backend.generation, 4
        )
        backend.target = new_target
        release.set()
        await pending
        assert backend.target_is_current(new_target)
        assert lost == []

    asyncio.run(run())


def test_caret_change_still_invalidates_target():
    backend, target = backend_with_target()
    backend._event(
        Message(
            message_type=MessageType.SIGNAL,
            sender=target.address[0],
            path=target.address[1],
            interface="org.a11y.atspi.Event.Object",
            member="TextCaretMoved",
            signature="i",
            body=[4],
        )
    )
    assert not backend.target_is_current(target)
