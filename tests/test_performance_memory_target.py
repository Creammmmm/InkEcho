"""Pure socket/process controls; these tests never start GTK or inspect a desktop."""

import asyncio
import importlib.util
import json
import os
import socket
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts/validation/performance_memory_target.py"
)
SPEC = importlib.util.spec_from_file_location("performance_memory_target", PATH)
parent = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parent)


def encoded(value):
    payload = json.dumps(value).encode()
    return struct.pack("!I", len(payload)) + payload


def fake_process(pid=None):
    process = SimpleNamespace(pid=pid or os.getpid(), returncode=None)
    process.poll = lambda: process.returncode

    def wait():
        process.returncode = 0
        return 0

    process.wait = wait
    process.terminate = process.kill = lambda: pytest.fail("must not kill producer")
    return process


def test_channel_memory_readback_and_close_without_text_files(tmp_path):
    async def run():
        left, right = socket.socketpair()
        channel = parent.PrivateChannel(left)

        async def peer():
            right.setblocking(False)
            loop = asyncio.get_running_loop()
            for value in (
                {"ok": True, "text": "private body 中文"},
                {"ok": True, "closed": True},
            ):
                data = await loop.sock_recv(right, 128)
                assert json.loads(data[4:])["command"] in {"read", "close"}
                await loop.sock_sendall(right, encoded(value))

        task = asyncio.create_task(peer())
        assert await channel.command("read") == "private body 中文"
        assert await channel.command("close") is None
        await task
        left.close()
        right.close()
        assert list(tmp_path.iterdir()) == []

    asyncio.run(run())


@pytest.mark.parametrize(
    "payload",
    [
        b"\0\0\0\0",
        struct.pack("!I", 65537),
        encoded([]),
        struct.pack("!I", 2) + b"\xff\xff",
    ],
)
def test_bad_reply_rejected_without_echoing_data(payload):
    async def run():
        left, right = socket.socketpair()
        right.sendall(payload)
        try:
            with pytest.raises(ValueError, match="memory_frame"):
                await parent.PrivateChannel(left).receive()
        finally:
            left.close()
            right.close()

    asyncio.run(run())


def test_eof_is_failure_not_a_fabricated_empty_text():
    async def run():
        left, right = socket.socketpair()
        right.close()
        try:
            with pytest.raises(ValueError, match="memory_channel_closed"):
                await parent.PrivateChannel(left).receive()
        finally:
            left.close()

    asyncio.run(run())


def test_duplicate_fields_and_integer_close_booleans_are_rejected():
    async def run():
        left, right = socket.socketpair()
        payload = b'{"ok":true,"ok":false,"text":"private"}'
        right.sendall(struct.pack("!I", len(payload)) + payload)
        channel = parent.PrivateChannel(left)
        try:
            with pytest.raises(ValueError, match="memory_frame_invalid"):
                await channel.receive()
            right.sendall(encoded({"ok": 1, "closed": 1}))
            with pytest.raises(ValueError, match="memory_close_failed"):
                await channel.command("close")
        finally:
            left.close()
            right.close()

    asyncio.run(run())


def test_unexpected_ready_keeps_immediate_process_identity(tmp_path, monkeypatch):
    handle = parent.RunHandle.create(tmp_path / "handle.json")
    peers = []
    process = fake_process()

    def popen(argv, **options):
        assert options["pass_fds"] and options["stdout"] == parent.subprocess.DEVNULL
        assert options["start_new_session"] is True
        peer = socket.socket(fileno=os.dup(options["pass_fds"][0]))
        peers.append(peer)
        peer.sendall(encoded({"ready": True, "pid": process.pid + 1, "window_id": 21}))
        return process

    monkeypatch.setattr(parent, "verify_controls", lambda *_args: None)
    monkeypatch.setattr(parent.subprocess, "Popen", popen)

    async def run():
        target = parent.MemoryTarget(handle, Path("/not-executed"))
        with pytest.raises(ValueError, match="memory_target_identity_failed"):
            await target.open({})
        record = json.loads(handle.path.read_text())["targets"][0]
        assert record["pid"] == process.pid and record["start_ticks"]
        assert record["argv"][:2] == ["/usr/bin/python3", str(parent.CHILD)]
        assert record["exit_code"] is None and not record["owner_observed_terminal"]
        target.channel.channel.close()

    try:
        asyncio.run(run())
    finally:
        for peer in peers:
            peer.close()


@pytest.mark.parametrize("operation", ["read", "close"])
def test_observation_timeout_preserves_same_operation_and_process(tmp_path, operation):
    handle = parent.RunHandle.create(tmp_path / "handle.json")
    process = fake_process()
    item = handle.add_process(process, ["fake-only"], producer=False)

    async def run():
        event = asyncio.Event()
        operations = []

        async def command(value):
            operations.append(value)
            await event.wait()
            return "private readback" if value == "read" else None

        original = handle.observe

        async def short(observed, phase, seconds=8):
            return await original(observed, phase, seconds=0.001)

        handle.observe = short
        target = parent.MemoryTarget(handle, Path("/not-executed"))
        target.process, target.item = process, item
        left, right = socket.socketpair()
        target.channel = SimpleNamespace(command=command, channel=left)
        task = asyncio.create_task(
            target.text() if operation == "read" else target.close()
        )
        await asyncio.sleep(0.02)
        assert not task.done() and handle.timed_out
        assert handle.record["phase"] == "observation_pending"
        assert operations == [operation] and not item["owner_observed_terminal"]
        assert item["exit_code"] is None and process.poll() is None
        assert "private readback" not in handle.path.read_text()
        event.set()
        result = await task
        if operation == "read":
            assert result == "private readback"
        else:
            assert process.returncode == 0 and item["owner_observed_terminal"]
        assert operations == [operation]
        left.close()
        right.close()

    asyncio.run(run())


def test_missing_pid_does_not_imply_success(tmp_path, monkeypatch):
    handle = parent.RunHandle.create(tmp_path / "handle.json")
    process = fake_process()
    handle.add_process(process, ["fake-only"], producer=True)
    monkeypatch.setattr(parent, "process_start", lambda _pid: None)
    record = parent.observe_handle(handle.path)["producer"]
    assert not record["identity_alive"]
    assert record["exit_code"] is None and not record["owner_observed_terminal"]
    with pytest.raises(ValueError, match="producer_not_terminal"):
        handle.terminal(process, handle.record["producer"])


def test_press_guard_accepts_any_owned_target_and_release_survives_focus_change(
    monkeypatch,
):
    state = {"active": 21, "pid": 101, "start": "first"}
    driver = SimpleNamespace(root=1, active_atom=2, pid_atom=3)
    driver.focus = lambda: state["active"]
    driver._property = lambda _window, atom: (
        state["active"] if atom == 2 else state["pid"]
    )
    sent = []
    inputs = SimpleNamespace(_driver=driver, _send=lambda *event: sent.append(event))
    targets = [
        SimpleNamespace(
            window=21, process=fake_process(101), item={"start_ticks": "first"}
        ),
        SimpleNamespace(
            window=22, process=fake_process(102), item={"start_ticks": "second"}
        ),
    ]
    monkeypatch.setattr(parent, "process_start", lambda _pid: state["start"])
    guard = parent.DeliveryGuard(inputs, targets)
    assert guard.focus_reads == 0 and not sent
    inputs._send(21, 248, True)
    state.update(active=22, pid=102, start="second")
    inputs._send(21, 248, False)
    inputs._send(22, 248, True)
    state.update(active=999, pid=500)
    inputs._send(22, 248, False)
    assert sent == [
        (21, 248, True),
        (21, 248, False),
        (22, 248, True),
        (22, 248, False),
    ]
    with pytest.raises(ValueError, match="delivery_outside_owned_targets"):
        inputs._send(999, 248, True)
    assert len(sent) == 4 and guard.presses == guard.releases == 2


@pytest.mark.parametrize("mismatch", ["pid", "start", "exited"])
def test_owned_window_is_insufficient_without_current_process_identity(
    monkeypatch, mismatch
):
    process = fake_process(101)
    process.returncode = 0 if mismatch == "exited" else None
    driver = SimpleNamespace(root=1, active_atom=2, pid_atom=3, focus=lambda: 21)
    driver._property = lambda _window, atom: (
        21 if atom == 2 else (102 if mismatch == "pid" else 101)
    )
    inputs = SimpleNamespace(
        _driver=driver, _send=lambda *_args: pytest.fail("no press")
    )
    monkeypatch.setattr(
        parent, "process_start", lambda _pid: "new" if mismatch == "start" else "old"
    )
    parent.DeliveryGuard(
        inputs,
        [SimpleNamespace(window=21, process=process, item={"start_ticks": "old"})],
    )
    with pytest.raises(ValueError, match="delivery_outside_owned_targets"):
        inputs._send(21, 248, True)


def test_child_environment_strips_package_gi_pollution():
    environment = {
        "HOME": "/isolated",
        "DISPLAY": ":7",
        "XAUTHORITY": "/auth",
        "PYTHONHOME": "/package/usr",
        "PYTHONPATH": "/package/packages",
        "LD_LIBRARY_PATH": "/package/lib",
        "QT_PLUGIN_PATH": "/package/Qt",
    }
    result = parent.child_environment(environment)
    assert not set(result) & {
        "PYTHONHOME",
        "PYTHONPATH",
        "LD_LIBRARY_PATH",
        "QT_PLUGIN_PATH",
    }
    assert (
        result["GDK_BACKEND"] == "x11"
        and result["GTK_IM_MODULE"] == "gtk-im-context-simple"
    )
    assert result["HOME"] == "/isolated" and result["DISPLAY"] == ":7"


@pytest.mark.parametrize(
    "dispatch,active,accepted", [(211, 21, True), (212, 21, False), (211, 99, False)]
)
def test_owned_top_level_allows_its_current_focused_child(
    monkeypatch, dispatch, active, accepted
):
    driver = SimpleNamespace(root=1, active_atom=2, pid_atom=3, focus=lambda: 211)
    driver._property = lambda window, atom: (
        active if atom == 2 else (101 if window == 21 else 0)
    )
    sent = []
    inputs = SimpleNamespace(_driver=driver, _send=lambda *event: sent.append(event))
    target = SimpleNamespace(
        window=21, process=fake_process(101), item={"start_ticks": "old"}
    )
    monkeypatch.setattr(parent, "process_start", lambda _pid: "old")
    guard = parent.DeliveryGuard(inputs, [target])
    if accepted:
        inputs._send(dispatch, 248, True)
        assert sent == [(211, 248, True)]
        assert guard.last_check["active_top_owned"]
        assert guard.last_check["focus_matches_dispatch"]
        assert not guard.last_check["dispatch_equals_owned_top"]
    else:
        with pytest.raises(ValueError, match="delivery_outside_owned_targets"):
            inputs._send(dispatch, 248, True)
        assert sent == []


def test_fixed_arm_metadata_is_preserved_before_acceptance_without_private_text(
    tmp_path,
):
    from inkecho.performance import TaskTiming

    handle = parent.RunHandle.create(tmp_path / "handle.json")
    handle.phase("arm_acceptance")
    handle.arm(
        {
            "configuration": "A",
            "scenario": "normal",
            "performance": TaskTiming().finish("failed"),
            "calls": {"http_asr": 1, "wss_asr": 0, "polishing": 1},
            "exact_expected": False,
            "presses_sent": 0,
            "releases_sent": 1,
            "session_diagnostics": ["injection_failed", "PRIVATE BODY AND KEY"],
            "text": "PRIVATE BODY AND KEY",
            "exception": RuntimeError("PRIVATE BODY AND KEY"),
        }
    )
    handle.failure(ValueError("comparison_acceptance_failed"))
    handle.phase("target_exit")
    handle.failure(RuntimeError("PRIVATE BODY AND KEY"))
    text = handle.path.read_text()
    assert "PRIVATE BODY" not in text
    record = json.loads(text)
    assert record["failed_phase"] == "arm_acceptance"
    assert record["failure_code"] == "comparison_acceptance_failed"
    row = record["arm_metadata"][0]
    assert row["flags"]["exact_expected"] is False
    assert row["session_diagnostics"] == ["injection_failed", "other"]
    assert row["performance"]["outcome"] == "failed"
    assert (
        parent.failure_code(RuntimeError("PRIVATE BODY AND KEY"))
        == "comparison_unexpected_failure"
    )
