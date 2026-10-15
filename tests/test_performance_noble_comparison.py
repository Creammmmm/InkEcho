"""Noble controls and adapter tests; no GTK, guest execution or real keyring."""

import asyncio
import importlib.util
import json
import os
import socket
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

ENTRY = Path(__file__).resolve().parents[1] / (
    "scripts/validation/performance_noble_comparison.py"
)


@pytest.fixture
def adapter(monkeypatch):
    monkeypatch.syspath_prepend(str(ENTRY.parent))
    spec = importlib.util.spec_from_file_location("noble_comparison_test", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arguments(adapter, **updates):
    return SimpleNamespace(
        **{
            "package_root": adapter.GUEST_APPDIR / "packages",
            "appimage": adapter.GUEST_ARTIFACT,
            "preview": False,
            **updates,
        }
    )


def node(adapter, monkeypatch):
    original = Path.read_text

    def read(path, *args, **kwargs):
        if str(path) == "/etc/os-release":
            return 'ID=ubuntu\nVERSION_ID="24.04"\n'
        if str(path) == f"/proc/{adapter.GNOME_PID}/comm":
            return "gnome-shell\n"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(adapter.platform, "release", lambda: "6.8.0-142-generic")
    monkeypatch.setattr(adapter.os, "getuid", lambda: 1000)
    monkeypatch.setattr(adapter, "process_start", lambda _pid: adapter.GNOME_START)

    def command(argv):
        return {
            "/usr/bin/gnome-shell": "GNOME Shell 46.0",
            "/usr/bin/loginctl": "User=1000\nType=x11\nLockedHint=no",
            "/usr/bin/gdbus": "(false,)",
        }[argv[0]]

    monkeypatch.setattr(adapter, "command_output", command)
    return command


def test_noble_preflight_requires_actual_pinned_node(adapter, monkeypatch):
    node(adapter, monkeypatch)
    result = adapter.preflight()
    assert result["session_id"] == "20" and result["session_type"] == "x11"
    assert result["gnome_pid"] == 26971 and not result["locked"]
    assert result["gnome_start_ticks"] == "95097"


@pytest.mark.parametrize(
    "program,response",
    [
        ("/usr/bin/gnome-shell", "GNOME Shell 48.0"),
        ("/usr/bin/loginctl", "User=1000\nType=wayland\nLockedHint=no"),
        ("/usr/bin/loginctl", "User=1000\nType=x11\nLockedHint=yes"),
        ("/usr/bin/loginctl", "User=999\nType=x11\nLockedHint=no"),
        ("/usr/bin/gdbus", "(true,)"),
        ("/usr/bin/gdbus", "PRIVATE unknown output"),
    ],
)
def test_node_mismatch_or_unknown_lock_is_rejected(
    adapter, monkeypatch, program, response
):
    original = node(adapter, monkeypatch)
    monkeypatch.setattr(
        adapter,
        "command_output",
        lambda argv: response if argv[0] == program else original(argv),
    )
    with pytest.raises(ValueError, match="^noble_preflight_failed$"):
        adapter.preflight()


def test_replaced_gnome_process_is_rejected(adapter, monkeypatch):
    node(adapter, monkeypatch)
    monkeypatch.setattr(adapter, "process_start", lambda _pid: "new-start")
    with pytest.raises(ValueError, match="noble_preflight_failed"):
        adapter.preflight()


def test_native_queries_strip_package_and_secret_environment(adapter, monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "private-package")
    monkeypatch.setenv("API_KEY", "PRIVATE")
    calls = []

    def run(argv, **options):
        calls.append((argv, options))
        return SimpleNamespace(returncode=0, stdout="(false,)\n")

    monkeypatch.setattr(adapter.subprocess, "run", run)
    assert adapter.command_output(["/usr/bin/gdbus"]) == "(false,)"
    assert calls[0][1]["env"] == {"PATH": "/usr/bin:/bin", **adapter.DESKTOP}
    assert calls[0][1]["timeout"] == 3


def test_native_and_child_must_match_all_pins(adapter, monkeypatch):
    checksums = {
        **adapter.NATIVE_HASHES,
        str(adapter.ROOT / adapter.SOURCES[-1]): adapter.CHILD_SHA,
    }
    monkeypatch.setattr(adapter, "digest", lambda path: checksums[str(path)])
    assert adapter.verify_controls(adapter.XDOTOOL)["files"] == adapter.NATIVE_HASHES
    for name in checksums:
        previous = checksums[name]
        checksums[name] = "0" * 64
        with pytest.raises(ValueError, match="noble_native_mismatch"):
            adapter.verify_controls(adapter.XDOTOOL)
        checksums[name] = previous
    with pytest.raises(ValueError, match="noble_native_mismatch"):
        adapter.verify_controls(Path("/another/xdotool"))


def test_preview_declares_guest_pins_without_claiming_preflight(adapter, monkeypatch):
    monkeypatch.setattr(
        adapter.core.previous, "verify_package", lambda *_a: {"version": "0.1.0a13"}
    )
    monkeypatch.setattr(
        adapter, "preflight", lambda: pytest.fail("no guest query in preview")
    )
    monkeypatch.setattr(
        adapter, "verify_controls", lambda *_a: pytest.fail("no host native")
    )
    report = adapter.make_plan(arguments(adapter, preview=True))
    assert report["kind"] == "host_staging_preview_only"
    assert report["guest_preflight"] == "not_run"
    assert (
        not report["native_verified_on_guest"] and not report["live_cloud_route_ready"]
    )
    assert report["public_wave_reads"] == report["user_configuration_reads"] == 0
    assert len(report["source_snapshot"]) == 7


def test_actual_plan_requires_guest_paths_and_actual_native_preflight(
    adapter, monkeypatch
):
    events = []
    monkeypatch.setattr(adapter.core.previous, "verify_package", lambda *_a: {})
    monkeypatch.setattr(adapter, "verify_paths", lambda _args: events.append("paths"))
    monkeypatch.setattr(
        adapter, "preflight", lambda: events.append("preflight") or {"locked": False}
    )
    monkeypatch.setattr(adapter, "verify_controls", lambda _x: events.append("native"))
    report = adapter.make_plan(arguments(adapter))
    assert events == ["paths", "preflight", "native"]
    assert report["native_verified_on_guest"]
    with pytest.raises(ValueError, match="noble_execution_path_mismatch"):
        # Real verifier refuses a host source even with guest-looking flags.
        import performance_noble_comparison as other

        other.verify_paths(arguments(adapter))


def test_worker_environment_is_private_with_explicit_desktop_connections(
    adapter, tmp_path
):
    env = adapter.worker_environment(tmp_path / "app/packages", tmp_path)
    assert all(env[name] == value for name, value in adapter.DESKTOP.items())
    assert env["QT_QPA_PLATFORM"] == "xcb"
    for name in (
        "HOME",
        "TMPDIR",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_STATE_HOME",
        "XDG_RUNTIME_DIR",
    ):
        path = Path(env[name])
        assert path.is_relative_to(tmp_path) and path.stat().st_mode & 0o777 == 0o700
    assert env["PYTHONHOME"].endswith("app/usr")
    assert env["LD_LIBRARY_PATH"].endswith("app/usr/lib/inkecho")
    child_env = __import__("performance_memory_target").child_environment(env)
    assert "PYTHONHOME" not in child_env and "LD_LIBRARY_PATH" not in child_env
    assert child_env["GDK_BACKEND"] == "x11"


def test_memory_target_injected_verifier_and_child_preserve_default(
    adapter, monkeypatch, tmp_path
):
    import performance_memory_target as parent

    handle = parent.RunHandle.create(tmp_path / "handle.json")
    assert (
        parent.MemoryTarget(handle, Path("/unused")).verifier is parent.verify_controls
    )
    assert parent.MemoryTarget(handle, Path("/unused")).child_path == parent.CHILD
    checks, peers = [], []
    process = SimpleNamespace(pid=os.getpid(), returncode=None)
    process.poll = lambda: process.returncode
    child = tmp_path / "owned-child.py"

    def popen(argv, **options):
        assert argv[:2] == ["/usr/bin/python3", str(child)]
        assert options["start_new_session"] is True
        peer = socket.socket(fileno=os.dup(options["pass_fds"][0]))
        peers.append(peer)
        payload = json.dumps(
            {"ready": True, "pid": process.pid, "window_id": 21}
        ).encode()
        peer.sendall(struct.pack("!I", len(payload)) + payload)
        return process

    monkeypatch.setattr(parent.subprocess, "Popen", popen)
    monkeypatch.setattr(
        parent, "verify_controls", lambda *_a: pytest.fail("wrong native verifier")
    )
    monkeypatch.setattr(parent.subprocess, "run", lambda *_a, **_k: None)

    async def run():
        target = parent.MemoryTarget(
            handle,
            adapter.XDOTOOL,
            verifier=lambda path: checks.append(path),
            child_path=child,
        )
        await target.open({})
        await target.activate()
        assert checks == [adapter.XDOTOOL, adapter.XDOTOOL]
        assert handle.record["targets"][0]["argv"][1] == str(child)
        target.channel.channel.close()

    try:
        asyncio.run(run())
    finally:
        for peer in peers:
            peer.close()


def test_guest_commands_bind_only_offline_paths_and_exact_fingerprint(adapter):
    argv = adapter.guest_command(worker=True, fingerprint="approved")
    assert argv[0] == str(adapter.GUEST_APPDIR / "usr/bin/python3")
    assert argv[-1] == "--worker"
    assert argv[argv.index("--accept-plan-sha") + 1] == "approved"
    assert "--offline-owned" in argv and "--live" not in argv
    assert not any("config" in arg or "keyring" in arg for arg in argv)


def test_cli_bad_plan_and_preview_never_import_qt_or_launch(
    adapter, monkeypatch, capsys
):
    monkeypatch.setattr(adapter, "make_plan", lambda _a: {"plan_sha256": "exact"})
    monkeypatch.setattr(
        adapter, "worker_environment", lambda *_a: pytest.fail("no execution")
    )
    base = ["--package-root", "/unused", "--appimage", "/unused"]
    assert adapter.main([*base, "--preview"]) == 0
    assert (
        json.loads(capsys.readouterr().out)["guest_execution_argv"][-1]
        == "ACTUAL_GUEST_REVIEWED_FINGERPRINT_REQUIRED"
    )
    assert adapter.main([*base, "--offline-owned", "--accept-plan-sha", "wrong"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "noble_plan_required"


def test_unknown_native_failure_does_not_print_arbitrary_data(
    adapter, monkeypatch, capsys
):
    monkeypatch.setattr(
        adapter, "make_plan", lambda _a: (_ for _ in ()).throw(RuntimeError("PRIVATE"))
    )
    assert adapter.main(["--package-root", "/unused", "--appimage", "/unused"]) == 1
    output = capsys.readouterr()
    assert "PRIVATE" not in output.out and output.err == ""


@pytest.mark.parametrize("failure", ["acceptance", "timeout", "plan_changed"])
def test_first_arm_failure_never_starts_second_and_persists_metadata(
    adapter, monkeypatch, tmp_path, failure
):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    handle = adapter.RunHandle.create(tmp_path / "handle.json")
    monkeypatch.setattr(
        adapter,
        "make_plan",
        lambda _a: {
            "plan_sha256": "changed" if failure == "plan_changed" else "reviewed"
        },
    )
    arms = []

    class Fixture:
        def __init__(self, _directory):
            self.errors = []
            self.polish_input_exact = True
            self.audio = b"\x01\x00" * 3200
            self.calls = {"http_asr": 1, "wss_asr": 0, "polishing": 1}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

    import performance_comparison_fixture as fixture

    monkeypatch.setattr(fixture, "Fixture", Fixture)

    async def run(arm, budget, *_args, **_kwargs):
        arms.append(arm)
        budget.reserve(arm, "asr")
        if failure == "timeout":
            handle.timed_out = True
        return {"configuration": arm, "fixed_metadata": True}

    monkeypatch.setattr(adapter.core, "run_arm", run)
    monkeypatch.setattr(adapter.core, "safe_result", lambda row: row)
    monkeypatch.setattr(
        adapter.core,
        "accept",
        lambda _row: (
            adapter.fail("noble_preflight_failed") if failure == "acceptance" else None
        ),
    )
    with pytest.raises(ValueError):
        asyncio.run(
            adapter.run_pair(handle, {"plan_sha256": "reviewed"}, arguments(adapter))
        )
    assert arms == ([] if failure == "plan_changed" else ["A"])
    if arms:
        record = json.loads(handle.path.read_text())
        assert record["noble_arm_metadata"] == [
            {"configuration": "A", "fixed_metadata": True}
        ]
        assert record["reserved_calls"]["A"]["asr"] == 1
