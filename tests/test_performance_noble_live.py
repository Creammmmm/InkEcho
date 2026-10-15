"""Local pipes and control doubles; never invoke Docker, SSH, keys or GUI."""

import asyncio
import copy
import importlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

LOCAL_POPEN = subprocess.Popen


@pytest.fixture
def node(monkeypatch):
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "scripts/validation")
    )
    module = importlib.import_module("performance_noble_live")
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_a, **_k: pytest.fail("no subprocess query allowed"),
    )
    monkeypatch.setattr(
        module.subprocess, "Popen", lambda *_a, **_k: pytest.fail("no producer allowed")
    )
    monkeypatch.setattr(module.resource, "setrlimit", lambda *_: None)
    return module


@pytest.fixture
def plan(node):
    configuration = {
        "hashes": {
            name: "a" * 64
            for name in (
                "config.json",
                "providers/qwen.json",
                "providers/deepseek.json",
            )
        },
        "references": node.core.REFS.copy(),
        "selected_models": {"qwen": "qwen3-asr-flash", "deepseek": "deepseek-flash"},
    }
    return node.fingerprint(
        node.spec(
            "offline-handoff",
            configuration,
            {"version": "0.1.0a13"},
            {name: "b" * 64 for name in node.SOURCES},
        )
    )


def test_default_host_plan_is_readonly_and_verifies_public_file_first(
    node, monkeypatch
):
    args = node.arguments([])
    seen = []
    monkeypatch.setattr(
        node.core, "read_metadata", lambda path: seen.append("config") or {}
    )
    monkeypatch.setattr(
        node.core.previous, "verify_package", lambda *_: seen.append("package") or {}
    )
    monkeypatch.setattr(
        node.core.previous,
        "verify_wave",
        lambda *_: seen.append("wave") or {"bytes": 571456},
    )
    monkeypatch.setattr(node, "source_hashes", lambda _: seen.append("sources") or {})
    report = node.host_plan(args, "live")
    assert seen == ["config", "package", "wave", "sources"]
    assert (
        not report["plan_is_authorization"]
        and report["background_guest_network_possible"]
    )
    assert report["budget"]["total"] == 4
    assert report["A"]["model"] == "qwen3-asr-flash"
    assert report["B"]["model"] == "qwen3-asr-flash-realtime"


def test_offline_and_live_have_distinct_audio_and_fingerprints(node, plan):
    live = node.fingerprint(
        node.spec("live", plan["configuration"], plan["package"], plan["sources"])
    )
    assert live["plan_sha256"] != plan["plan_sha256"]
    assert live["audio"]["sha256"] == node.handoff.PUBLIC_AUDIO.sha256
    assert live["audio"]["bytes"] == 571456
    assert plan["audio"]["frames"] == 3200 and plan["network"] == "unchanged_none"
    node.handoff.validate_audio(*node.synthetic_audio())
    with pytest.raises(node.handoff.HandoffError):
        node.handoff.validate_audio(node.synthetic_audio()[0])


@pytest.mark.parametrize(
    "argv",
    [
        ["--offline-handoff"],
        ["--mode", "offline-handoff", "--live"],
        ["--role", "node", "--prepare"],
        ["--credential-fd", "3"],
        ["--role", "worker", "--live"],
    ],
)
def test_incompatible_cli_modes_fail_before_actions(node, argv):
    with pytest.raises(node.ControlError, match="^mode_mismatch$"):
        node.arguments(argv)


def test_commands_have_no_credential_payload_and_no_pty(node, plan):
    command = node.ssh_command("offline-handoff", plan["plan_sha256"])
    assert command[:4] == ["docker", "exec", "--interactive", node.CONTAINER]
    assert "-T" in command and "-t" not in command
    assert "StrictHostKeyChecking=yes" in command
    assert "--mode offline-handoff" in command[-1]
    assert "--offline-handoff" in command[-1]
    assert "--live" not in command[-1]
    child = node.node_command(
        "live", worker=True, accepted="a" * 64, credential_fd=3, ready_fd=4
    )
    assert child[0] == str(node.noble.GUEST_APPDIR / "usr/bin/python3")
    assert child[-4:] == ["--credential-fd", "3", "--ready-fd", "4"]


def test_prepare_copies_only_fixed_sources_and_safe_plans_exclusively(
    node, plan, tmp_path, monkeypatch
):
    root, snapshot, output = (tmp_path / name for name in ("root", "input", "output"))
    for relative in node.SOURCES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic source")
    monkeypatch.setattr(node, "ROOT", root)
    monkeypatch.setattr(node, "HOST_SNAPSHOT", snapshot)
    monkeypatch.setattr(node, "HOST_OUTPUT", output)
    calls = []
    monkeypatch.setattr(
        node,
        "host_plan",
        lambda _args, mode: calls.append(mode) or {**plan, "mode": mode},
    )
    result = node.prepare(SimpleNamespace())
    assert calls == list(node.MODES)
    assert set(result) == set(node.MODES)
    assert sorted(
        str(p.relative_to(snapshot)) for p in snapshot.rglob("*") if p.is_file()
    ) == sorted(
        [*node.SOURCES, "plans/live.json", "plans/offline-handoff.json", "preview.json"]
    )
    with pytest.raises(FileExistsError):
        node.prepare(SimpleNamespace())


def test_node_plan_rechecks_package_sources_native_session_and_producers(
    node, plan, monkeypatch
):
    monkeypatch.setattr(node, "GUEST_ROOT", Path(node.__file__).resolve().parents[2])
    reviewed = node.fingerprint(
        node.spec(
            "offline-handoff", plan["configuration"], plan["package"], plan["sources"]
        )
    )
    monkeypatch.setattr(node, "load", lambda _: copy.deepcopy(reviewed))
    monkeypatch.setattr(node, "source_hashes", lambda _: plan["sources"])
    checked = []
    monkeypatch.setattr(
        node.core.previous,
        "verify_package",
        lambda *_: checked.append("package") or plan["package"],
    )
    monkeypatch.setattr(node.noble, "preflight", lambda: checked.append("session"))
    monkeypatch.setattr(
        node.noble, "verify_controls", lambda _: checked.append("native")
    )
    monkeypatch.setattr(
        node, "no_producers", lambda allowed: checked.append(("producers", allowed))
    )
    assert node.node_plan("offline-handoff", allowed=(123,)) == reviewed
    assert checked == ["package", "session", "native", ("producers", (123,))]
    monkeypatch.setattr(node, "source_hashes", lambda _: {})
    with pytest.raises(node.ControlError, match="^plan_changed$"):
        node.node_plan("offline-handoff")


@pytest.mark.parametrize("field", ["references", "hashes", "selected_models", "extra"])
def test_untrusted_plan_configuration_not_accepted(node, plan, field):
    value = copy.deepcopy(plan["configuration"])
    if field == "extra":
        value["private"] = "not echoed"
    else:
        value[field] = {}
    with pytest.raises(node.ControlError, match="^plan_changed$"):
        node.validate_configuration(value)


def handle_record(node, plan, path, pid=4321, start="12345"):
    handle = node.RunHandle.create(path)
    handle.record["producer"] = {
        "pid": pid,
        "start_ticks": start,
        "argv": node.node_command(
            plan["mode"],
            worker=True,
            accepted=plan["plan_sha256"],
            credential_fd=3,
            ready_fd=4,
        ),
        "exit_code": None,
        "owner_observed_terminal": False,
    }
    handle.save()
    return handle


def test_host_ready_expected_uses_independent_parent_record_not_ready(
    node, plan, tmp_path
):
    handle = handle_record(node, plan, tmp_path / "handle.json")
    origins = {name: "c" * 64 for name in node.handoff.ORIGINS}
    expected = node.host_expected(handle.path, plan, origins)
    ready = {
        "version": 1,
        "kind": "ready",
        "plan_sha256": plan["plan_sha256"],
        "origins": origins,
        "producer": {"pid": 9999, "start_ticks": "12345"},
        "budget": {arm: {"asr": 0, "polishing": 0} for arm in ("A", "B")},
    }
    assert expected.producer_pid == 4321
    with pytest.raises(node.handoff.HandoffError, match="^ready$"):
        node.handoff.validate_ready(ready, expected)
    handle.record["producer"]["argv"] += ["--source-root", "/untrusted"]
    handle.save()
    with pytest.raises(node.ControlError, match="^identity_mismatch$"):
        node.host_expected(handle.path, plan, origins)


def test_owner_reloads_worker_metadata_before_marking_natural_terminal(
    node, plan, tmp_path
):
    stale = handle_record(node, plan, tmp_path / "handle.json")
    fresh = node.RunHandle(stale.path)
    fresh.record.update(
        results=[{"configuration": "A"}],
        reserved_calls={"A": {"asr": 1}},
        runtime_origins={"actual": "hash"},
        cleanup_complete=True,
    )
    fresh.record["targets"] = [
        {"pid": 12, "owner_observed_terminal": True, "exit_code": 0}
    ]
    fresh.save()
    process = SimpleNamespace(pid=4321, poll=lambda: 1)
    assert node.terminal_worker(stale.path, process) == 1
    result = node.load(stale.path)
    assert result["results"] == fresh.record["results"]
    assert result["targets"] == fresh.record["targets"]
    assert result["runtime_origins"] == {"actual": "hash"}
    assert node.terminal_and_clean(stale.path)  # Failed experiment still cleans.


def test_session_close_or_previous_arm_does_not_prove_current_cleanup(
    node, plan, tmp_path
):
    handle = handle_record(node, plan, tmp_path / "handle.json")
    handle.record["session_cleanup_verified"] = True
    handle.record["live_arm_metadata"] = [{"mapping_restored_and_driver_closed": True}]
    assert not node.cleaned(handle)
    handle.record["current_arm_cleanup_verified"] = True
    assert node.cleaned(handle)
    handle.record["targets"] = [{"owner_observed_terminal": False, "exit_code": None}]
    assert not node.cleaned(handle)


@pytest.mark.parametrize("wrong_fake_key", [False, True])
def test_offline_worker_uses_real_anonymous_fds_and_no_sdk_gui(
    node, plan, tmp_path, monkeypatch, wrong_fake_key
):
    folder = tmp_path / "offline-handoff"
    folder.mkdir()
    handle = handle_record(
        node, plan, folder / "handle.json", os.getpid(), node.process_start(os.getpid())
    )
    monkeypatch.setattr(node, "GUEST_OUTPUT", tmp_path)
    monkeypatch.setattr(node, "node_plan", lambda *_a, **_k: plan)
    origins = {name: "d" * 64 for name in node.handoff.ORIGINS}
    monkeypatch.setattr(node.core, "audit_runtime", lambda _: origins)
    monkeypatch.setattr(node.core.previous, "verify_production_profiles", lambda: None)
    monkeypatch.setattr(node.resource, "setrlimit", lambda *_: None)
    monkeypatch.setattr(
        node.core,
        "run_arm",
        lambda *_a, **_k: pytest.fail("offline must not invoke Session/SDK"),
    )
    ready_read, ready_write = os.pipe()
    credential_read, credential_write = os.pipe()
    failures = []

    def host():
        try:
            expected = node.handoff.ReadyExpected(
                plan["plan_sha256"],
                origins,
                os.getpid(),
                node.process_start(os.getpid()),
            )
            ready = node.handoff.receive_ready(ready_read, expected)
            audio, constraints = node.synthetic_audio()
            node.handoff.Sender().send(
                credential_write,
                ready,
                expected,
                revalidate=lambda: None,
                read_key=lambda _: (
                    "wrong-synthetic" if wrong_fake_key else "synthetic-offline-only"
                ),
                read_audio=lambda: audio,
                constraints=constraints,
            )
        except Exception as error:
            failures.append(error)
        finally:
            os.close(ready_read)
            os.close(credential_write)

    thread = threading.Thread(target=host)
    thread.start()
    args = SimpleNamespace(
        mode="offline-handoff",
        accept_plan_sha=plan["plan_sha256"],
        ready_fd=ready_write,
        credential_fd=credential_read,
    )
    try:
        assert node.worker(args) == (1 if wrong_fake_key else 0)
    finally:
        thread.join(2)
    assert not thread.is_alive() and not failures
    result = node.load(handle.path)
    assert result["cleanup_complete"]
    if wrong_fake_key:
        assert result["failure_code"] == "offline_mismatch"
        assert not result.get("offline_handoff_verified")
    else:
        assert result["offline_handoff_verified"]
        assert result["runtime_origins"] == origins and result["results"] == []
    assert args.ready_fd is None and args.credential_fd is None
    assert "synthetic-offline-only" not in handle.path.read_text()


@pytest.mark.parametrize(
    "bad", ["id", "name", "started_at", "pid", "running", "paused", "qemu"]
)
def test_container_and_qemu_identity_pinned_before_network(node, monkeypatch, bad):
    container = {
        "id": node.CONTAINER_ID,
        "name": "/" + node.CONTAINER,
        "started_at": node.CONTAINER_STARTED,
        "running": True,
        "paused": False,
        "restarting": False,
        "pid": 517799,
        "networks": {},
    }
    qemu = {"exe": "/usr/bin/qemu-system-x86_64", "start": node.QEMU_START}
    if bad == "qemu":
        qemu["start"] = "1"
    else:
        container[bad] = (
            not container[bad] if type(container[bad]) is bool else "changed"
        )
    monkeypatch.setattr(
        node, "command_json", lambda argv: qemu if "exec" in argv else container
    )
    with pytest.raises(node.ControlError, match="^identity_mismatch$"):
        node.container_state()


def bridge_fixture(node, monkeypatch, *, networks=None):
    state = {"id": node.CONTAINER_ID, "networks": [] if networks is None else networks}
    calls, record = [], {}
    monkeypatch.setattr(node, "container_state", lambda: copy.deepcopy(state))
    monkeypatch.setattr(
        node,
        "command_json",
        lambda _: {
            "id": node.BRIDGE_ID,
            "name": "bridge",
            "driver": "bridge",
            "internal": False,
        },
    )

    def run(argv, **_options):
        calls.append(argv)
        state["networks"] = ["bridge"] if argv[2] == "connect" else []
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(node.subprocess, "run", run)
    return node.ScopedBridge(record, lambda: None), calls, record, state


@pytest.mark.parametrize("clean", [False, True])
def test_bridge_restore_uses_terminal_cleanup_not_experiment_success(
    node, monkeypatch, clean
):
    bridge, calls, record, _state = bridge_fixture(node, monkeypatch)
    bridge.connect()
    bridge.finish(clean)
    assert calls[0] == ["docker", "network", "connect", "bridge", node.CONTAINER_ID]
    assert len(calls) == (2 if clean else 1)
    assert record["network_phase"] == (
        "restored_none" if clean else "pending_producer_or_cleanup"
    )
    if clean:
        assert calls[1] == [
            "docker",
            "network",
            "disconnect",
            "bridge",
            node.CONTAINER_ID,
        ]


def test_bridge_never_touches_preexisting_network_or_other_bridge(node, monkeypatch):
    bridge, calls, _record, state = bridge_fixture(
        node, monkeypatch, networks=["bridge"]
    )
    with pytest.raises(node.ControlError, match="^network_state$"):
        bridge.connect()
    assert not calls
    state["networks"] = []
    monkeypatch.setattr(node, "command_json", lambda _: {"id": "different"})
    with pytest.raises(node.ControlError, match="^network_state$"):
        bridge.connect()
    assert not calls


def test_failed_connect_is_not_retried_and_unknown_state_not_disconnected(
    node, monkeypatch
):
    bridge, calls, record, state = bridge_fixture(node, monkeypatch)

    def failure(argv, **_options):
        calls.append(argv)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(node.subprocess, "run", failure)
    with pytest.raises(node.ControlError, match="^network_state$"):
        bridge.connect()
    assert bridge.requested and len(calls) == 1
    bridge.finish(False)
    assert len(calls) == 1 and record["network_phase"] == "pending_producer_or_cleanup"
    state["networks"] = ["unrelated"]
    with pytest.raises(node.ControlError, match="^network_state$"):
        bridge.finish(True)
    assert len(calls) == 1


def test_unknown_failure_does_not_echo_private_exception(node, capsys, monkeypatch):
    def fail(*_):
        raise RuntimeError("private-key-transcript")

    monkeypatch.setattr(node, "host_plan", fail)
    assert node.main([]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "failed",
        "code": "execution_failed",
    }


def test_invalid_cli_does_not_echo_unrecognized_private_arguments(node, capsys):
    assert node.main(["--unknown", "private-do-not-echo"]) == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {"status": "failed", "code": "mode_mismatch"}


@pytest.mark.parametrize("failed_arm", [None, "A"])
def test_live_pair_single_budget_order_and_failure_never_starts_b(
    node, plan, tmp_path, monkeypatch, failed_arm
):
    reviewed = {**plan, "mode": "live"}
    handle = handle_record(node, reviewed, tmp_path / "handle.json")
    monkeypatch.setattr(node, "node_plan", lambda *_a, **_k: reviewed)
    monkeypatch.setattr(node.core, "safe_result", lambda value: value)
    calls, budgets = [], []

    async def run_arm(arm, budget, _audio, _pcm, _credentials, *, desktop):
        calls.append(arm)
        budgets.append(budget)
        budget.reserve(arm, "asr")
        if arm != failed_arm:
            budget.reserve(arm, "polishing")
        return {
            "configuration": arm,
            "failed": arm == failed_arm,
            "mapping_restored_and_driver_closed": True,
            "matched_releases": True,
            "target_exit_zero": True,
        }

    def accept(row):
        if row["failed"]:
            raise node.core.ProbeError("arm_acceptance_failed")

    monkeypatch.setattr(node.core, "run_arm", run_arm)
    monkeypatch.setattr(node.core, "accept", accept)
    operation = node.live_pair(handle, reviewed, object(), node.synthetic_audio()[0])
    if failed_arm:
        with pytest.raises(node.core.ProbeError):
            asyncio.run(operation)
        assert calls == ["A"] and node.cleaned(handle)
        assert handle.record["reserved_calls"]["A"] == {"asr": 1, "polishing": 0}
    else:
        assert len(asyncio.run(operation)) == 2
        assert calls == ["A", "B"] and budgets[0] is budgets[1]
        assert sum(sum(row.values()) for row in budgets[0].calls.values()) == 4


@pytest.mark.parametrize(
    "mode,exit_code,bad_ready,changed_plan,cleanup_fails",
    [
        ("offline-handoff", 0, False, False, False),
        ("live", 0, False, False, False),
        ("live", 1, False, False, False),
        ("live", 1, True, False, False),
        ("live", 1, False, True, False),
        ("live", 0, False, False, True),
        ("live", 1, False, False, True),
    ],
)
def test_host_end_to_end_pipe_control_gates_keys_and_preserves_failure_cleanup(
    node,
    plan,
    tmp_path,
    monkeypatch,
    mode,
    exit_code,
    bad_ready,
    changed_plan,
    cleanup_fails,
):
    audio, constraints = node.synthetic_audio()
    reviewed = {**copy.deepcopy(plan), "mode": mode}
    snapshot, output = tmp_path / "snapshot", tmp_path / "output"
    (snapshot / "plans").mkdir(parents=True)
    output.mkdir()
    node.write_metadata(node.plan_path(snapshot, mode), reviewed)
    monkeypatch.setattr(node, "HOST_SNAPSHOT", snapshot)
    monkeypatch.setattr(node, "HOST_OUTPUT", output)
    monkeypatch.setattr(node, "source_hashes", lambda _: reviewed["sources"])
    events = []

    def host_plan(*_):
        events.append("revalidate")
        return {**reviewed, "plan_sha256": "f" * 64} if changed_plan else reviewed

    monkeypatch.setattr(node, "host_plan", host_plan)
    monkeypatch.setattr(node.handoff, "PUBLIC_AUDIO", constraints)
    monkeypatch.setattr(
        node.core.previous, "WAV", SimpleNamespace(read_bytes=lambda: audio)
    )
    package_root = tmp_path / "packages"
    security_path = package_root / "inkecho/security.py"
    security_path.parent.mkdir(parents=True)
    security_path.write_bytes(b"synthetic security module marker")
    origins = {name: "c" * 64 for name in node.handoff.ORIGINS}
    origins["inkecho.security"] = node.digest(security_path)
    monkeypatch.setattr(node, "expected_origins", lambda _: origins)

    class Store:
        def __init__(self):
            events.append("store")

        def get(self, reference):
            events.append(reference)
            return "real-looking-testkey"

    original_import = node.importlib.import_module
    monkeypatch.setattr(
        node.importlib,
        "import_module",
        lambda name: (
            SimpleNamespace(__file__=str(security_path), SecretStore=Store)
            if name == "inkecho.security"
            else original_import(name)
        ),
    )

    class Bridge:
        def __init__(self, record, _save):
            self.record = record

        def before(self):
            events.append("before")

        def connect(self):
            events.append("connect")

        def finish(self, clean):
            events.append(("finish", clean))
            assert self.record["passed"] is False
            assert node.load(output / mode / "controller.json")["passed"] is False
            if cleanup_fails:
                raise node.ControlError("network_state")

    monkeypatch.setattr(node, "ScopedBridge", Bridge)
    failures = []

    class Process:
        pid = 4321

        def __init__(self, argv, **options):
            assert options["start_new_session"] is True
            assert "-T" in argv
            read_credentials, write_credentials = os.pipe()
            read_ready, write_ready = os.pipe()
            self.stdin = os.fdopen(write_credentials, "wb", buffering=0)
            self.stdout = os.fdopen(read_ready, "rb", buffering=0)
            self.code = None
            handle = handle_record(
                node, reviewed, output / mode / "handle.json", 5678, "23456"
            )

            def guest():
                try:
                    message = {
                        "version": 1,
                        "kind": "ready",
                        "plan_sha256": reviewed["plan_sha256"],
                        "origins": origins,
                        "producer": {
                            "pid": 999 if bad_ready else 5678,
                            "start_ticks": "23456",
                        },
                        "budget": {
                            arm: {"asr": 0, "polishing": 0} for arm in ("A", "B")
                        },
                    }
                    node.send_ready(write_ready, message)
                    try:
                        credentials, received = node.handoff.Receiver().receive(
                            read_credentials,
                            reviewed["plan_sha256"],
                            constraints=constraints,
                        )
                        assert received == audio
                        expected_key = (
                            "synthetic-offline-only"
                            if mode == "offline-handoff"
                            else "real-looking-testkey"
                        )
                        assert all(
                            credentials.get(ref) == expected_key
                            for ref in node.handoff.REFS
                        )
                        credentials.close()
                    except node.handoff.HandoffError:
                        assert bad_ready or changed_plan
                    handle.record.update(
                        plan_sha256=reviewed["plan_sha256"],
                        cleanup_complete=True,
                        offline_handoff_verified=mode == "offline-handoff",
                        results=[]
                        if mode == "offline-handoff"
                        else [{"configuration": "A"}, {"configuration": "B"}],
                    )
                    if exit_code:
                        handle.record["failure_code"] = "execution_failed"
                    handle.record["producer"].update(
                        exit_code=exit_code, owner_observed_terminal=True
                    )
                    handle.save()
                except BaseException as error:
                    failures.append(error)
                finally:
                    os.close(read_credentials)
                    os.close(write_ready)
                    self.code = exit_code

            self.thread = threading.Thread(target=guest)
            self.thread.start()

        def wait(self):
            self.thread.join(2)
            assert not self.thread.is_alive()
            return self.code

        def poll(self):
            return self.code

    monkeypatch.setattr(node.subprocess, "Popen", Process)
    args = SimpleNamespace(
        mode=mode, accept_plan_sha=reviewed["plan_sha256"], package_root=package_root
    )
    if exit_code or bad_ready or changed_plan or cleanup_fails:
        with pytest.raises(node.ControlError) as caught:
            node.execute_host(args, reviewed)
        if cleanup_fails:
            assert caught.value.args == (
                "execution_failed" if exit_code else "network_state",
            )
    else:
        assert node.execute_host(args, reviewed)["passed"] is True
    assert not failures
    assert events[-1] == ("finish", True)
    if mode == "offline-handoff" or bad_ready or changed_plan:
        assert "store" not in events
    else:
        assert events.count("store") == 1
        assert events.index("connect") < events.index("store")
        assert [event for event in events if event in node.handoff.REFS] == list(
            node.handoff.REFS
        )
        assert events.count("revalidate") >= 5
    if bad_ready or changed_plan or mode == "offline-handoff":
        assert "connect" not in events
    result = node.load(output / mode / "controller.json")
    assert (
        result["ssh"]["owner_observed_terminal"]
        and result["producer_terminal_and_clean"]
    )
    assert result["passed"] is (
        exit_code == 0 and not bad_ready and not changed_plan and not cleanup_fails
    )
    if cleanup_fails:
        assert result["experiment_passed"] is (exit_code == 0)
        assert result["cleanup_failure_code"] == "network_state"
        assert result["cleanup_failed_phase"] == "network_cleanup"
        assert result["failure_code"] == (
            "execution_failed" if exit_code else "network_state"
        )
        assert result["host_failed_phase"] == (
            "experiment_terminal" if exit_code else "network_cleanup"
        )
    assert "real-looking-testkey" not in json.dumps(result)
    assert (output / mode / "ssh.log").stat().st_mode & 0o777 == 0o600


def test_launcher_real_local_child_fd_eof_and_fresh_terminal_record(
    node, plan, tmp_path, monkeypatch
):
    """A local helper stubs only node/package audit; no guest or SDK executes."""
    folder = tmp_path / "offline-handoff"
    folder.mkdir()
    data = tmp_path / "metadata.json"
    origins = {name: "e" * 64 for name in node.handoff.ORIGINS}
    data.write_text(json.dumps({"plan": plan, "origins": origins}))
    child = tmp_path / "local-worker.py"
    child.write_text(
        "import sys,json\nfrom pathlib import Path\nfrom types import SimpleNamespace\n"
        f"sys.path.insert(0,{str(Path(node.__file__).parent)!r})\n"
        "import performance_noble_live as n\n"
        "metadata=json.loads(Path(sys.argv[3]).read_text())\n"
        "n.GUEST_OUTPUT=Path(sys.argv[3]).parent\n"
        "n.node_plan=lambda *_a,**_k:metadata['plan']\n"
        "n.core.audit_runtime=lambda _:metadata['origins']\n"
        "n.core.previous.verify_production_profiles=lambda:None\n"
        "args=SimpleNamespace(mode='offline-handoff',accept_plan_sha=metadata['plan']['plan_sha256'],"
        "credential_fd=int(sys.argv[1]),ready_fd=int(sys.argv[2]))\n"
        "raise SystemExit(n.worker(args))\n"
    )
    monkeypatch.setattr(node, "GUEST_OUTPUT", tmp_path)
    monkeypatch.setattr(node, "node_plan", lambda *_: plan)
    monkeypatch.setattr(node, "expected_origins", lambda _: origins)
    monkeypatch.setattr(
        node.noble,
        "worker_environment",
        lambda *_: {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    # The entrypoint has the same anonymous pipe contract as no-PTY SSH stdio.
    host_input_read, host_input_write = os.pipe()
    host_ready_read, host_ready_write = os.pipe()
    original_read, original_check, original_ready = (
        node.os.read,
        node.handoff._pipe,
        node.send_ready,
    )
    monkeypatch.setattr(
        node.os,
        "read",
        lambda fd, count: original_read(host_input_read if fd == 0 else fd, count),
    )
    monkeypatch.setattr(
        node.handoff,
        "_pipe",
        lambda fd, *, writing: original_check(
            host_input_read if fd == 0 else host_ready_write if fd == 1 else fd,
            writing=writing,
        ),
    )
    monkeypatch.setattr(
        node,
        "send_ready",
        lambda fd, value: original_ready(host_ready_write if fd == 1 else fd, value),
    )
    processes = []
    terminal_calls = []
    original_terminal = node.terminal_worker

    def terminal(path, process):
        terminal_calls.append(process.pid)
        return original_terminal(path, process)

    monkeypatch.setattr(node, "terminal_worker", terminal)

    def popen(argv, **options):
        assert options["start_new_session"] is True
        cfd, rfd = options["pass_fds"]
        process = LOCAL_POPEN(
            [sys.executable, "-B", str(child), str(cfd), str(rfd), str(data)], **options
        )
        processes.append(process)
        return process

    monkeypatch.setattr(node.subprocess, "Popen", popen)
    failures = []

    def host():
        try:
            handle_path = folder / "handle.json"
            for _ in range(1000):
                if handle_path.exists() and node.load(handle_path)["producer"]:
                    break
                node.time.sleep(0.001)
            expected = node.host_expected(handle_path, plan, origins)
            ready = node.handoff.receive_ready(host_ready_read, expected)
            audio, constraints = node.synthetic_audio()
            node.handoff.Sender().send(
                host_input_write,
                ready,
                expected,
                revalidate=lambda: None,
                read_key=lambda _: "synthetic-offline-only",
                read_audio=lambda: audio,
                constraints=constraints,
            )
        except BaseException as error:
            failures.append(error)
        finally:
            os.close(host_input_write)
            os.close(host_ready_read)

    thread = threading.Thread(target=host)
    thread.start()
    try:
        assert (
            node.launcher(
                SimpleNamespace(
                    mode="offline-handoff", accept_plan_sha=plan["plan_sha256"]
                )
            )
            == 0
        )
    finally:
        thread.join(3)
        os.close(host_input_read)
        os.close(host_ready_write)
    assert not thread.is_alive() and not failures
    assert len(processes) == 1 and processes[0].returncode == 0
    assert terminal_calls == [processes[0].pid]
    record = node.load(folder / "handle.json")
    assert record["runtime_origins"] == origins and record["offline_handoff_verified"]
    assert (
        record["producer"]["owner_observed_terminal"]
        and record["producer"]["exit_code"] == 0
    )
    assert record["cleanup_complete"] and record["results"] == []
    assert "synthetic-offline-only" not in json.dumps(record)
    assert (folder / "worker.log").stat().st_mode & 0o777 == 0o600


def test_second_arm_exception_cannot_reuse_first_arm_cleanup_witness(
    node, plan, tmp_path, monkeypatch
):
    reviewed = {**plan, "mode": "live"}
    handle = handle_record(node, reviewed, tmp_path / "handle.json")
    monkeypatch.setattr(node, "node_plan", lambda *_a, **_k: reviewed)
    monkeypatch.setattr(node.core, "safe_result", lambda value: value)
    monkeypatch.setattr(node.core, "accept", lambda _: None)
    calls = []

    async def run_arm(arm, *_a, **_k):
        calls.append(arm)
        if arm == "B":
            raise RuntimeError("private-provider-details")
        return {
            "mapping_restored_and_driver_closed": True,
            "matched_releases": True,
            "target_exit_zero": True,
        }

    monkeypatch.setattr(node.core, "run_arm", run_arm)
    with pytest.raises(RuntimeError):
        asyncio.run(
            node.live_pair(handle, reviewed, object(), node.synthetic_audio()[0])
        )
    assert calls == ["A", "B"] and not node.cleaned(handle)
    assert len(handle.record["live_arm_metadata"]) == 1


@pytest.mark.parametrize(
    "field",
    ["mapping_restored_and_driver_closed", "matched_releases", "target_exit_zero"],
)
def test_any_false_resource_witness_prevents_verified_cleanup(
    node, plan, tmp_path, monkeypatch, field
):
    reviewed = {**plan, "mode": "live"}
    handle = handle_record(node, reviewed, tmp_path / "handle.json")
    monkeypatch.setattr(node, "node_plan", lambda *_a, **_k: reviewed)
    monkeypatch.setattr(node.core, "safe_result", lambda value: value)
    row = {
        name: True
        for name in (
            "mapping_restored_and_driver_closed",
            "matched_releases",
            "target_exit_zero",
        )
    }
    row[field] = False

    async def run_arm(*_a, **_k):
        return row

    def reject(_):
        raise node.core.ProbeError("arm_acceptance_failed")

    monkeypatch.setattr(node.core, "run_arm", run_arm)
    monkeypatch.setattr(node.core, "accept", reject)
    with pytest.raises(node.core.ProbeError):
        asyncio.run(
            node.live_pair(handle, reviewed, object(), node.synthetic_audio()[0])
        )
    assert not node.cleaned(handle)


@pytest.mark.parametrize("fault", ["cleanup", "producer", "target"])
def test_terminal_alone_or_unclosed_target_never_allows_network_teardown(
    node, plan, tmp_path, fault
):
    handle = handle_record(node, plan, tmp_path / "handle.json")
    handle.record["producer"].update(owner_observed_terminal=True, exit_code=1)
    handle.record.update(cleanup_complete=True)
    if fault == "cleanup":
        handle.record["cleanup_complete"] = False
    elif fault == "producer":
        handle.record["producer"]["owner_observed_terminal"] = False
    else:
        handle.record["targets"] = [
            {"owner_observed_terminal": False, "exit_code": None}
        ]
    handle.save()
    assert not node.terminal_and_clean(handle.path)


def test_fresh_import_and_default_stubbed_plan_use_only_stdlib(node):
    program = (
        "import sys;from pathlib import Path;"
        f"sys.path.insert(0,{str(Path(node.__file__).parent)!r});"
        "import performance_noble_live as n;"
        "n.core.read_metadata=lambda _:{};"
        "n.core.previous.verify_package=lambda *_:{};"
        "n.core.previous.verify_wave=lambda _:{'bytes':571456};"
        "n.source_hashes=lambda _:{};"
        "n.host_plan(n.arguments([]),'live');"
        "assert not any(k.split('.')[0] in {'PySide6','httpx','keyring','inkecho'} "
        "for k in sys.modules)"
    )
    process = LOCAL_POPEN(
        [sys.executable, "-B", "-c", program],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0 and stdout == stderr == b""


@pytest.mark.parametrize("core_already_failed", [False, True])
def test_worker_records_first_failure_before_phase_change_and_preserves_core_reason(
    node, plan, tmp_path, monkeypatch, core_already_failed
):
    handle = handle_record(node, plan, tmp_path / "handle.json")
    handle.record["phase"] = "preflight"
    if core_already_failed:
        handle.record.update(
            live_failure_code="authentication", failed_phase="request_reserved"
        )
    handle.save()
    monkeypatch.setattr(node, "attach_worker", lambda _: handle)

    def fail(*_a, **_k):
        raise RuntimeError("private-key-response")

    monkeypatch.setattr(node, "node_plan", fail)
    ready_read, ready_write = os.pipe()
    credential_read, credential_write = os.pipe()
    args = SimpleNamespace(
        mode="offline-handoff", ready_fd=ready_write, credential_fd=credential_read
    )
    try:
        assert node.worker(args) == 1
    finally:
        os.close(ready_read)
        os.close(credential_write)
    result = node.load(handle.path)
    assert result["phase"] == "worker_failed"
    assert result["failed_phase"] == (
        "request_reserved" if core_already_failed else "preflight"
    )
    if core_already_failed:
        assert result["live_failure_code"] == "authentication"
        assert "failure_code" not in result
    else:
        assert result["failure_code"] == "execution_failed"
    assert "private" not in json.dumps(result)
