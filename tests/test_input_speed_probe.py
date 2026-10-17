"""Pure benchmark audit/metrics checks; no desktop, cloud or process is started."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def probe(monkeypatch):
    directory = Path(__file__).resolve().parents[1] / "scripts/validation"
    names = (
        "artifact_scope",
        "native_acceptance",
        "native_guard",
        "natural_owned_browser",
        "x11_acceptance",
    )
    before = {name: sys.modules.get(name) for name in names}
    monkeypatch.syspath_prepend(str(directory))
    for name in names:
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(
        "input_speed_probe_test", directory / "input_speed_probe.py"
    )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        yield module
    finally:
        for name, value in before.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def test_fixed_public_sample_and_single_insert_metrics(probe):
    assert len(probe.SAMPLE) == 100
    assert all(32 <= ord(char) <= 0xFFFF for char in probe.SAMPLE)
    result = probe.measurement(1, 1.1, 3, 2.9, 100)
    assert result["characters_per_second"] == 50
    assert result["post_return_dom_exact_observed_ms"] < result["output_scope_ms"]


@pytest.mark.parametrize(
    "values",
    [
        (1, 1, 1, 1, 100),
        (1, 0, 2, 3, 100),
        (1, 2, 3, 1, 100),
        (1, 2, float("nan"), 4, 100),
        (1, 2, 3, 4, True),
    ],
)
def test_invalid_timings_never_become_throughput(probe, values):
    with pytest.raises(ValueError):
        probe.measurement(*values)


def audit_fixture(probe, tmp_path, monkeypatch):
    package = tmp_path / "app/packages"
    package.mkdir(parents=True)
    inventory_path = tmp_path / "app/usr/share/doc/inkecho/inventory.json"
    inventory_path.parent.mkdir(parents=True)
    inventory_path.write_text(
        json.dumps({"application": "test-version", "files": {}, "symlinks": {}})
    )
    artifact = tmp_path / "candidate.AppImage"
    artifact.write_bytes(b"synthetic non-executable artifact")
    source = tmp_path / "source"
    source.mkdir()
    (source / "fixed.py").write_text("PUBLIC = True\n")
    manifest = tmp_path / "manifest.json"
    pins = {}
    for name in ("keyboard", "hybrid_keyboard", "wayland_keyboard", "wayland_worker"):
        file = source / f"inkecho/platform/{name}.py"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("PUBLIC = True\n")
        pins[f"inkecho/platform/{name}.py"] = probe.checksum(file)
    monkeypatch.setitem(
        sys.modules,
        "inkecho.platform.hybrid_keyboard",
        SimpleNamespace(__file__=str(source / "inkecho/platform/hybrid_keyboard.py")),
    )
    manifest.write_text(
        json.dumps(
            {
                "source_files": probe.source_files(source),
                "approved_production_pins": pins,
            }
        )
    )
    monkeypatch.setattr(probe.sys, "executable", str(tmp_path / "app/usr/bin/python"))
    monkeypatch.setattr(probe.sys, "path", list(sys.path))
    monkeypatch.setattr(probe, "MODULES", ())
    return SimpleNamespace(
        runtime="source",
        artifact=artifact,
        artifact_sha=probe.checksum(artifact),
        package_root=package,
        source_root=source,
        manifest=manifest,
        manifest_sha=probe.checksum(manifest),
    )


def test_source_audit_is_distinct_from_package_and_rejects_changed_bytes(
    probe, tmp_path, monkeypatch
):
    args = audit_fixture(probe, tmp_path, monkeypatch)
    result = probe.audit(args)
    assert result["runtime_kind"] == "source" and result["not_a_new_package"]
    assert result["source_files_checked"] == 5
    (args.source_root / "fixed.py").write_text("PUBLIC = False\n")
    with pytest.raises(ValueError, match="source_manifest_mismatch"):
        probe.audit(args)


def test_package_mode_never_accepts_source_overlay(probe, tmp_path, monkeypatch):
    args = audit_fixture(probe, tmp_path, monkeypatch)
    args.runtime = "package"
    with pytest.raises(ValueError, match="cannot_overlay_source"):
        probe.audit(args)
    args.source_root = args.manifest = args.manifest_sha = None
    assert probe.audit(args)["runtime_kind"] == "package"


def test_source_manifest_requires_approved_hash(probe, tmp_path, monkeypatch):
    args = audit_fixture(probe, tmp_path, monkeypatch)
    args.manifest_sha = "0" * 64
    with pytest.raises(ValueError, match="source_manifest_sha_mismatch"):
        probe.audit(args)


def test_symlink_and_inventory_escape_rejected_before_import(
    probe, tmp_path, monkeypatch
):
    args = audit_fixture(probe, tmp_path, monkeypatch)
    (args.source_root / "escape").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="source_symlink"):
        probe.audit(args)
    (args.source_root / "escape").unlink()
    inventory = tmp_path / "app/usr/share/doc/inkecho/inventory.json"
    outside = tmp_path / "outside"
    outside.write_bytes(b"fixed")
    inventory.write_text(
        json.dumps(
            {
                "application": "test-version",
                "files": {"../outside": probe.checksum(outside)},
                "symlinks": {},
            }
        )
    )
    with pytest.raises(ValueError, match="dependency_inventory_mismatch"):
        probe.audit(args)


def test_worker_argv_preserves_runtime_and_explicit_review(probe, tmp_path):
    args = probe.parser().parse_args(
        [
            "--runtime",
            "source",
            "--artifact",
            "candidate.AppImage",
            "--artifact-sha",
            "a" * 64,
            "--package-root",
            "/package",
            "--source-root",
            "/source",
            "--manifest",
            "/manifest",
            "--manifest-sha",
            "b" * 64,
            "--backend",
            "native",
            "--field",
            "contenteditable",
            "--work-root",
            str(tmp_path),
            "--output",
            str(tmp_path / "result.json"),
        ]
    )
    argv = probe.worker_argv(args, tmp_path)
    assert "--run-reviewed" in argv and "--worker" in argv
    assert argv[argv.index("--manifest-sha") + 1] == "b" * 64
    assert argv[argv.index("--source-root") + 1] == "/source"
    assert argv[argv.index("--guard-state") + 1] == str(tmp_path / "guard.json")


@pytest.mark.parametrize(
    "cancel, fault",
    [
        (False, None),
        (True, None),
        (False, "scope_leak"),
        (False, "close_failure"),
        (False, "close_cancel"),
        (False, "delayed_x"),
        (False, "x_never_ready"),
    ],
)
def test_single_case_uses_factory_and_verifies_partial_cancel_cleanup(
    probe, tmp_path, monkeypatch, cancel, fault
):
    import asyncio

    from inkecho.platform.keyboard import KeyboardError

    state = {
        "text": "",
        "document_focused": True,
        "field_focused": True,
        "sampled_at": 0,
    }
    calls = []

    class Driver:
        def _mapping(self):
            return b"leaked" if state.get("leaked") else b"original"

        def _write(self, _values):
            pass

        def restore(self):
            calls.append("restore")

        def close(self):
            calls.append("observer_close")

    class Inputs:
        connected = True
        _driver = Driver()

        async def connect(self):
            calls.append("connect")

        async def authorize(self):
            calls.append("authorize")

        def _send(self, _window, _code, pressed):
            if pressed:
                state["text"] += self.character

        async def insert(self, text, active, *, deadline, on_first_sent):
            assert deadline > probe.time.monotonic()
            try:
                for index, char in enumerate(text):
                    if not active():
                        raise KeyboardError("input_cancelled")
                    self.character = char
                    self._send(1, 124, True)
                    if index == 0:
                        on_first_sent(probe.time.monotonic())
                    self._send(1, 124, False)
                return len(text)
            finally:
                self._driver.restore()
                state["leaked"] = fault == "scope_leak"

        async def aclose(self):
            calls.append("close")
            state["leaked"] = False
            if fault == "close_failure":
                raise ValueError("synthetic_cleanup_failure")
            if fault == "close_cancel":
                raise asyncio.CancelledError

    class Fixture:
        errors = []
        process = None
        started = "synthetic"

        def __init__(self, *_args, **_kwargs):
            self.profile = tmp_path / "profile"

        def snapshot(self):
            return {**state, "sampled_at": probe.time.monotonic()}

        def assert_owned(self):
            pass

        def start(self, *, reviewed):
            assert reviewed
            self.process = SimpleNamespace(pid=999999, poll=lambda: None)
            calls.append("owned_target_start")

        def close(self):
            calls.append("owned_target_close")
            return 0

    def factory():
        calls.append("factory")
        return Inputs()

    async def until(predicate, *_args, **_kwargs):
        for _ in range(4):
            if predicate():
                return
        raise ValueError("synthetic_not_ready")

    async def sleep(_seconds):
        pass

    monkeypatch.setattr(
        "inkecho.platform.wayland_keyboard.keyboard_for_desktop", factory
    )
    monkeypatch.setattr("inkecho.platform.keyboard._XDriver", Driver)
    evidence_calls = []

    def evidence(_fixture):
        evidence_calls.append(True)
        return {
            "confirmed": fault != "x_never_ready"
            and (fault != "delayed_x" or len(evidence_calls) >= 3),
            "ozone_platform": "x11",
        }

    monkeypatch.setitem(
        sys.modules, "host_mixed_wayland_probe", SimpleNamespace(x11_evidence=evidence)
    )
    monkeypatch.setattr(probe, "debugger_endpoint", lambda *_args: "owned-endpoint")
    monkeypatch.setattr(probe, "NaturalOwnedBrowser", Fixture)
    monkeypatch.setattr(probe, "owned_focus", lambda *_args: True)
    monkeypatch.setattr(probe, "until", until)
    monkeypatch.setattr(probe.asyncio, "sleep", sleep)
    args = SimpleNamespace(
        backend="xwayland",
        field="textarea",
        cancel=cancel,
        work_root=tmp_path,
        output=tmp_path / "result.json",
    )
    report = {"worker_owners": []}
    asyncio.run(probe.direct_case(args, report))
    if fault == "x_never_ready":
        assert not report["passed"] and state["text"] == ""
        assert report["failed_phase"] == "target_protocol_ready"
        assert report["safe_setup_code"] == "owned_protocol_not_ready"
        assert calls.index("close") < calls.index("owned_target_close")
        return
    expected = 8 if cancel else 100
    assert report["passed"] is (fault in {None, "delayed_x"})
    assert report["received_count"] == expected
    assert report["successful_presses"] == report["successful_releases"] == expected
    assert calls[0] == "factory" and calls.count("factory") == 1
    assert calls.index("close") < calls.index("owned_target_close")
    assert report["x_mapping_restored"] and report["correct_route"]
    assert report["scope_open_x_restored"] is (fault != "scope_leak")
    if fault in {"close_failure", "close_cancel"}:
        assert report["cleanup_errors"] == [
            {
                "component": "inputs",
                "safe_error_type": (
                    "ValueError" if fault == "close_failure" else "CancelledError"
                ),
            }
        ]
    if fault == "delayed_x":
        assert len(evidence_calls) == 3
    if cancel:
        assert report["expected_error"] == "input_cancelled"
    # The report persists counts/timings only, never the synthetic body itself.
    assert probe.SAMPLE not in args.output.read_text()


def test_source_manifest_cannot_self_report_wrong_production_pins(
    probe, tmp_path, monkeypatch
):
    args = audit_fixture(probe, tmp_path, monkeypatch)
    manifest = json.loads(args.manifest.read_text())
    pins = manifest["approved_production_pins"]
    name = next(iter(pins))
    pins[name] = "0" * 64
    args.manifest.write_text(json.dumps(manifest))
    args.manifest_sha = probe.checksum(args.manifest)
    with pytest.raises(ValueError, match="production_pin_mismatch"):
        probe.audit(args)
    del manifest["approved_production_pins"]
    args.manifest.write_text(json.dumps(manifest))
    args.manifest_sha = probe.checksum(args.manifest)
    with pytest.raises(ValueError, match="four_production_pins_required"):
        probe.audit(args)


def test_missing_close_endpoint_stops_http_and_waits_original_terminal(
    probe, tmp_path, monkeypatch
):
    import asyncio
    import threading

    stopped = threading.Event()
    thread = threading.Thread(target=stopped.wait)
    thread.start()
    calls = []
    process = SimpleNamespace(pid=999999, returncode=None)
    process.poll = lambda: process.returncode

    def wait():
        calls.append("original_wait")
        assert process.returncode == 0
        return 0

    process.wait = wait

    class Server:
        def shutdown(self):
            calls.append("http_shutdown")
            stopped.set()
            process.returncode = 0  # Simulate natural exit after startup failure.

        def server_close(self):
            calls.append("http_close")

    fixture = SimpleNamespace(
        process=process,
        profile=tmp_path,
        started="synthetic",
        server=Server(),
        thread=thread,
        assert_owned=lambda: None,
        save_owner=lambda phase, code: calls.append((phase, code)),
    )

    def missing(*_args):
        raise FileNotFoundError

    async def initial_timeout(predicate, *_args):
        assert not predicate()
        raise ValueError("owned_close_endpoint_not_ready")

    monkeypatch.setattr(probe, "debugger_endpoint", missing)
    monkeypatch.setattr(probe, "until", initial_timeout)
    report = {}
    try:
        result = asyncio.run(
            probe.close_owned_fixture(fixture, report, tmp_path / "result.json")
        )
        assert result == 0 and not thread.is_alive()
        assert calls == [
            "http_shutdown",
            "http_close",
            "original_wait",
            ("terminal", 0),
        ]
        assert report["target_cleanup_pending"]["pid"] == process.pid
        assert report["cleanup_errors"] == []
    finally:
        stopped.set()
        thread.join(timeout=1)


def test_actual_xorg_factory_reaches_controlled_connect_without_backend_attribute(
    probe, monkeypatch, tmp_path
):
    import asyncio

    from inkecho.platform.keyboard import KeyboardError, KeyboardInput
    from inkecho.platform.wayland_keyboard import keyboard_for_desktop

    # Use the real factory and actual class, stopping at its first desktop I/O.
    actual = keyboard_for_desktop({"XDG_SESSION_TYPE": "x11"})
    assert isinstance(actual, KeyboardInput)
    assert not hasattr(actual, "backend")
    connected = []

    async def unavailable(self):
        connected.append(type(self))
        raise KeyboardError("input_unavailable")

    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setattr(KeyboardInput, "connect", unavailable)
    args = SimpleNamespace(
        work_root=tmp_path,
        output=tmp_path / "result.json",
        field="textarea",
        backend="xwayland",
        cancel=False,
    )
    report = {"worker_owners": []}
    asyncio.run(probe.direct_case(args, report))
    assert connected == [KeyboardInput]
    assert report["failed_phase"] == "input_connect"
    assert report["safe_error_type"] == "KeyboardError"
    assert report["native_observer_applicable"] is False
    assert report["native_mapping_evidence"] == "not_applicable_xorg_factory"
    assert report["worker_owners"] == []
    assert not (tmp_path / "browser/owner.json").exists()
