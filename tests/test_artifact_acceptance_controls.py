"""Pure controls only: no browser/server/Qt/desktop/credential/API execution."""

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parents[1] / "scripts/validation"


@pytest.fixture(autouse=True)
def validation_imports(monkeypatch):
    monkeypatch.syspath_prepend(str(HERE))


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


artifact = load("artifact_scope")
browser = load("natural_owned_browser")


@pytest.fixture
def fake_package(tmp_path, monkeypatch):
    root = tmp_path / "appdir"
    packages = root / "packages"
    sources = tmp_path / "snapshot/src"
    sources.mkdir(parents=True)
    (root / "usr/bin").mkdir(parents=True)
    executable = root / "usr/bin/python3"
    executable.write_text("synthetic-interpreter-metadata-only")
    modules, files = {}, {}
    for name in artifact.MODULES:
        relative = name.replace(".", "/")
        relative += "/__init__.py" if name in {"inkecho", "websockets"} else ".py"
        path = packages / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic module for control test\n")
        modules[name] = SimpleNamespace(__file__=str(path), __version__="0.1.0a14")
        files[str(path.relative_to(root))] = artifact.checksum(path)
    doc = root / "usr/share/doc/inkecho"
    doc.mkdir(parents=True)
    (doc / "inventory.json").write_text(
        json.dumps({"application": "0.1.0a14", "files": files})
    )
    calls = []
    probe = SimpleNamespace(
        ROOT=sources.parent,
        audit_appdir=lambda path: calls.append(path) or {"verified": True},
    )
    monkeypatch.setitem(sys.modules, "performance_package_probe", probe)
    monkeypatch.setattr(artifact.sys, "executable", str(executable))
    monkeypatch.setattr(artifact.sys, "path", list(sys.path))
    monkeypatch.setattr(artifact.importlib, "import_module", lambda name: modules[name])
    return root, packages, sources, modules, calls


def test_complete_scope_uses_own_python_frozen_tree_inventory_and_native(fake_package):
    root, packages, sources, _modules, calls = fake_package
    result = artifact.audit_package(packages, sources, "0.1.0a14")
    assert result["runtime_kind"] == "package"
    assert not result["production_behavior_modified"]
    assert set(result["origins"]) == set(artifact.MODULES)
    assert "inkecho.platform.wayland_worker" in result["origins"]
    assert calls == [root]


def test_mutable_other_source_tree_rejected_before_inventory(fake_package, tmp_path):
    _root, packages, _source, _modules, calls = fake_package
    other = tmp_path / "other-src"
    other.mkdir()
    with pytest.raises(ValueError, match="frozen_source_snapshot_required"):
        artifact.audit_package(packages, other, "0.1.0a14")
    assert calls == []


def test_wrong_interpreter_rejected(fake_package, monkeypatch):
    _root, packages, source, _modules, calls = fake_package
    monkeypatch.setattr(artifact.sys, "executable", "/usr/bin/python3")
    with pytest.raises(ValueError, match="selected_package_interpreter_required"):
        artifact.audit_package(packages, source, "0.1.0a14")
    assert calls == []


def test_wrong_inventory_version_rejected(fake_package):
    _root, packages, source, _modules, calls = fake_package
    with pytest.raises(ValueError, match="selected_version_mismatch"):
        artifact.audit_package(packages, source, "0.1.0a13")
    assert calls == []


def test_native_origin_not_just_inkecho_app_is_checked(fake_package):
    _root, packages, source, modules, _calls = fake_package
    Path(modules["inkecho.platform.wayland_worker"].__file__).write_text("changed")
    with pytest.raises(ValueError, match="module_inventory_mismatch"):
        artifact.audit_package(packages, source, "0.1.0a14")


def test_import_escape_and_runtime_version_rejected(fake_package, tmp_path):
    _root, packages, source, modules, _calls = fake_package
    outside = tmp_path / "other.py"
    outside.write_text("outside")
    previous = modules["inkecho.platform.eis"].__file__
    modules["inkecho.platform.eis"].__file__ = str(outside)
    with pytest.raises(ValueError, match="module_origin_outside_package"):
        artifact.audit_package(packages, source, "0.1.0a14")
    modules["inkecho.platform.eis"].__file__ = previous
    modules["inkecho"].__version__ = "old"
    with pytest.raises(ValueError, match="runtime_version_mismatch"):
        artifact.audit_package(packages, source, "0.1.0a14")


def test_explicit_artifact_sha_required(tmp_path):
    path = tmp_path / "synthetic.AppImage"
    path.write_bytes(b"synthetic-control-only")
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    assert artifact.selected_artifact(path, checksum)["sha256"] == checksum
    for invalid in ["", "latest", "x" * 64]:
        with pytest.raises(ValueError, match="expected_artifact_sha_required"):
            artifact.selected_artifact(path, invalid)
    with pytest.raises(ValueError, match="artifact_sha_mismatch"):
        artifact.selected_artifact(path, "0" * 64)


def test_desktop_review_is_mandatory_before_files_or_subprocess(tmp_path, monkeypatch):
    target = tmp_path / "not-created"
    fixture = browser.NaturalOwnedBrowser(target)
    monkeypatch.setattr(
        browser.subprocess, "Popen", lambda *_a, **_k: pytest.fail("spawn")
    )
    with pytest.raises(ValueError, match="explicit_desktop_review_required"):
        fixture.start()
    assert not target.exists()


@pytest.mark.parametrize(
    "contents",
    [
        "0\n/devtools/browser/id",
        "65536\n/devtools/browser/id",
        "123\nhttps://remote",
        "123\n/devtools/page/id",
        "123\n/devtools/browser/id\nextra",
        "x" * 257,
    ],
)
def test_debugger_metadata_cannot_select_arbitrary_destination(tmp_path, contents):
    path = tmp_path / "DevToolsActivePort"
    path.write_text(contents)
    with pytest.raises(ValueError, match="owned_debugger_metadata_invalid"):
        browser.debugger_endpoint(path, tmp_path)


def test_debugger_metadata_is_owned_bounded_loopback(tmp_path):
    path = tmp_path / "DevToolsActivePort"
    path.write_text("12345\n/devtools/browser/fixed-id\n")
    assert (
        browser.debugger_endpoint(path, tmp_path)
        == "ws://127.0.0.1:12345/devtools/browser/fixed-id"
    )
    alias = tmp_path / "alias"
    alias.symlink_to(path)
    with pytest.raises(ValueError, match="owned_debugger_metadata_invalid"):
        browser.debugger_endpoint(alias, tmp_path)


def test_only_selected_display_and_no_package_or_secret_environment(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setenv("WAYLAND_DISPLAY", "owned-wayland")
    monkeypatch.setenv("DISPLAY", ":99")
    for key in ["PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH", "API_KEY"]:
        monkeypatch.setenv(key, "private-not-forwarded")
    result = browser.browser_environment(tmp_path, "wayland")
    assert result["WAYLAND_DISPLAY"] == "owned-wayland"
    assert "DISPLAY" not in result
    assert (
        not {"PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH", "API_KEY"} & result.keys()
    )


class Process:
    pid = 123456
    returncode = None

    def __init__(self):
        self.wait_calls = 0

    def poll(self):
        return self.returncode

    def wait(self):
        self.wait_calls += 1
        self.returncode = 0
        return 0

    def terminate(self):
        pytest.fail("terminate forbidden")

    def kill(self):
        pytest.fail("kill forbidden")


@pytest.fixture
def owned(tmp_path, monkeypatch):
    fixture = browser.NaturalOwnedBrowser(tmp_path)
    fixture.profile = tmp_path / "profile"
    fixture.profile.mkdir()
    (fixture.profile / "DevToolsActivePort").write_text(
        "23456\n/devtools/browser/owned-id\n"
    )
    fixture.process = Process()
    fixture.started = "known-start"
    monkeypatch.setattr(browser, "process_start", lambda _pid: "known-start")
    monkeypatch.setattr(browser, "parent_pid", lambda _pid: os.getpid())
    fixture.server = SimpleNamespace(shutdown=lambda: None, server_close=lambda: None)
    fixture.thread = SimpleNamespace(join=lambda **_k: None, is_alive=lambda: False)
    fixture.stderr_thread = fixture.thread
    return fixture


def test_normal_close_is_single_fixed_cdp_then_natural_owner_wait(owned, monkeypatch):
    import websockets.sync.client

    messages = []

    class Channel:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def send(self, message):
            messages.append(json.loads(message))

    monkeypatch.setattr(websockets.sync.client, "connect", lambda *_a, **_k: Channel())
    assert owned.close() == 0
    assert messages == [{"id": 1, "method": "Browser.close"}]
    assert owned.process.wait_calls == 1 and owned.closed
    record = json.loads((owned.root / "owner.json").read_text())
    assert record["owner_observed_terminal"] and record["exit_code"] == 0
    assert owned.close() == 0 and owned.process.wait_calls == 1


def test_failed_close_preserves_same_pid_profile_and_does_not_retry(
    owned, monkeypatch, capsys
):
    import websockets.sync.client

    calls = []

    def refused(*_a, **_k):
        calls.append(True)
        raise RuntimeError("private-freeform-never-logged")

    monkeypatch.setattr(websockets.sync.client, "connect", refused)
    with pytest.raises(ValueError, match="^owned_normal_close_unconfirmed$"):
        owned.close()
    with pytest.raises(ValueError, match="^owned_close_already_attempted$"):
        owned.close()
    assert calls == [True] and owned.process.wait_calls == 0
    assert owned.profile.exists() and not owned.closed
    assert (
        json.loads((owned.root / "owner.json").read_text())["phase"]
        == "normal_close_unconfirmed"
    )
    assert capsys.readouterr() == ("", "")


def test_changed_process_identity_never_dispatches_close(owned, monkeypatch):
    import websockets.sync.client

    monkeypatch.setattr(browser, "process_start", lambda _pid: "different")
    monkeypatch.setattr(
        websockets.sync.client, "connect", lambda *_a, **_k: pytest.fail("CDP")
    )
    with pytest.raises(ValueError, match="owned_browser_identity_changed"):
        owned.close()
    assert owned.process.wait_calls == 0 and not owned.closed


def test_new_fixture_has_independent_nonce_and_no_reused_display(tmp_path):
    first = browser.NaturalOwnedBrowser(tmp_path / "first")
    second = browser.NaturalOwnedBrowser(tmp_path / "second")
    assert first.class_name.startswith("inkecho-owned-")
    assert first.class_name != second.class_name
    assert first.spawn_display is None


@pytest.mark.parametrize(
    "age,expected", [(0, True), (0.25, True), (0.251, False), (-0.01, False)]
)
def test_worker_guard_freshness_bounds(monkeypatch, age, expected):
    guard = load("native_guard")
    monkeypatch.setattr(guard, "parent_pid", lambda _pid: 77)
    monkeypatch.setattr(guard, "process_start", lambda _pid: "owned-start")
    state = {
        "allowed": True,
        "backend_confirmed": True,
        "owner_pid": 77,
        "pid": 88,
        "start_ticks": "owned-start",
        "sampled_at": 100.0 - age,
    }
    assert guard.guard_allowed(state, 77, 100.0) is expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("allowed", False),
        ("backend_confirmed", False),
        ("owner_pid", 99),
        ("start_ticks", "reused-pid"),
    ],
)
def test_worker_guard_rejects_unsafe_or_replaced_identity(monkeypatch, field, value):
    guard = load("native_guard")
    monkeypatch.setattr(guard, "parent_pid", lambda _pid: 77)
    monkeypatch.setattr(guard, "process_start", lambda _pid: "owned-start")
    state = {
        "allowed": True,
        "backend_confirmed": True,
        "owner_pid": 77,
        "pid": 88,
        "start_ticks": "owned-start",
        "sampled_at": 100.0,
    }
    state[field] = value
    assert not guard.guard_allowed(state, 77, 100.1)


def test_worker_guard_rechecks_real_parent_and_fails_closed_on_incomplete_data(
    monkeypatch,
):
    guard = load("native_guard")
    monkeypatch.setattr(guard, "parent_pid", lambda _pid: 99)
    monkeypatch.setattr(guard, "process_start", lambda _pid: "owned-start")
    state = {
        "allowed": True,
        "backend_confirmed": True,
        "owner_pid": 77,
        "pid": 88,
        "start_ticks": "owned-start",
        "sampled_at": 100.0,
    }
    assert not guard.guard_allowed(state, 77, 100.1)
    assert not guard.guard_allowed({}, 77, 100.1)


@pytest.mark.parametrize(
    "module,extra",
    [
        ("native_acceptance", []),
        ("ui_protocol_acceptance", ["--expected-platform", "wayland"]),
        ("cloud_realtime_capability", ["--expected-provider-sha", "0" * 64]),
        ("artifact_entry", ["--tool", "performance_package_probe"]),
    ],
)
def test_execution_flags_required_before_artifact_runtime_gui_or_keys(
    monkeypatch, module, extra
):
    entry = load(module)
    argv = [
        str(HERE / (module + ".py")),
        "--artifact",
        "/nonexistent.AppImage",
        "--expected-sha",
        "0" * 64,
        "--package-root",
        "/nonexistent/packages",
        "--frozen-source-root",
        "/nonexistent/src",
        "--expected-version",
        "0.1.0a14",
    ]
    if module == "artifact_entry":
        argv += ["--origins-output", "/nonexistent/report.json"]
    else:
        argv += ["--output", "/nonexistent/report.json"]
    if module in {"native_acceptance", "ui_protocol_acceptance"}:
        argv += ["--work-root", "/nonexistent/work"]
    if module == "native_acceptance":
        argv += ["--mode", "textarea"]
    argv += extra
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(
        entry,
        "selected_artifact",
        lambda *_a: pytest.fail("artifact/SDK path executed"),
    )
    with pytest.raises(SystemExit) as error:
        entry.main()
    assert error.value.code == 2


@pytest.mark.parametrize(
    "session,platform,display,valid",
    [
        ("x11", "x11", "DISPLAY", True),
        ("wayland", "x11", "DISPLAY", True),
        ("wayland", "wayland", "WAYLAND_DISPLAY", True),
        ("x11", "wayland", "WAYLAND_DISPLAY", False),
        ("tty", "x11", "DISPLAY", False),
    ],
)
def test_browser_environment_accepts_actual_backend_without_relabeling(
    tmp_path, monkeypatch, session, platform, display, valid
):
    monkeypatch.setenv("XDG_SESSION_TYPE", session)
    monkeypatch.setenv(display, ":owned" if display == "DISPLAY" else "owned-wayland")
    if valid:
        env = browser.browser_environment(tmp_path, platform)
        assert env["XDG_SESSION_TYPE"] == session
        assert (
            ("WAYLAND_DISPLAY" not in env)
            if platform == "x11"
            else ("DISPLAY" not in env)
        )
    else:
        with pytest.raises(ValueError, match="actual_graphical_session_required"):
            browser.browser_environment(tmp_path, platform)


def add_hybrid_to_package(fake_package):
    root, packages, _source, modules, _calls = fake_package
    path = packages / "inkecho/platform/hybrid_keyboard.py"
    path.write_text("# synthetic current package hybrid module\n")
    modules["inkecho.platform.hybrid_keyboard"] = SimpleNamespace(__file__=str(path))
    inventory = root / "usr/share/doc/inkecho/inventory.json"
    value = json.loads(inventory.read_text())
    value["files"][str(path.relative_to(root))] = artifact.checksum(path)
    inventory.write_text(json.dumps(value))
    return path


def test_current_package_checks_optional_hybrid_origin(
    fake_package,
):
    add_hybrid_to_package(fake_package)
    _root, packages, source, _modules, _calls = fake_package
    result = artifact.audit_package(packages, source, "0.1.0a14")
    assert len(result["origins"]) == len(artifact.MODULES) + 1
    assert "inkecho.platform.hybrid_keyboard" in result["origins"]


def test_current_hybrid_tamper_rejected(fake_package):
    path = add_hybrid_to_package(fake_package)
    _root, packages, source, _modules, _calls = fake_package
    path.write_text("changed")
    with pytest.raises(ValueError, match="module_inventory_mismatch"):
        artifact.audit_package(packages, source, "0.1.0a14")
