import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from inkecho.platform import ibus_extension as module


def test_install_is_explicit_verified_and_does_not_enable(tmp_path):
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        assert kwargs["env"].get("PYTHONHOME") is None
        with zipfile.ZipFile(command[2]) as archive:
            assert set(archive.namelist()) == set(module.FILES)
            for name in module.FILES:
                assert archive.read(name) == (manager.source / name).read_bytes()
        return SimpleNamespace(returncode=0, stdout="")

    manager = module.ExtensionManager(runner=run)
    manager.install()
    assert len(commands) == 1
    assert commands[0][:2] == ["/usr/bin/gnome-extensions", "install"]
    assert not Path(commands[0][2]).exists()


def test_tampering_and_symlink_fail_before_any_desktop_operation(tmp_path):
    for name in module.FILES:
        (tmp_path / name).write_bytes(b"changed")
    commands = []
    manager = module.ExtensionManager(
        source=tmp_path, runner=lambda *a, **k: commands.append(a)
    )
    with pytest.raises(module.ExtensionError, match="校验失败"):
        manager.install()
    (tmp_path / "capability.js").unlink()
    (tmp_path / "capability.js").symlink_to("delivery_gate.js")
    with pytest.raises(module.ExtensionError, match="不安全"):
        manager.install()
    assert not commands


def test_enable_disable_and_state_are_explicit():
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(
            returncode=0,
            stdout=f"  State: ACTIVE\n  Path: {manager.source}\n",
        )

    manager = module.ExtensionManager(runner=run)
    assert "正在运行" in manager.status()
    manager.enable()
    manager.disable()
    assert [command[1:] for command in commands] == [
        ["info", module.UUID],
        ["info", module.UUID],
        ["enable", module.UUID],
        ["disable", module.UUID],
    ]


def test_enable_rejects_unverified_existing_extension(tmp_path):
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout=f"  Path: {tmp_path}\n")

    with pytest.raises(module.ExtensionError):
        module.ExtensionManager(runner=run).enable()
    assert len(commands) == 1 and commands[0][1] == "info"


def test_timeout_and_unavailable_never_report_running():
    def run(*args, **kwargs):
        raise subprocess.TimeoutExpired("gnome-extensions", 10)

    manager = module.ExtensionManager(runner=run)
    assert "不可用" in manager.status()
    with pytest.raises(module.ExtensionError):
        manager.enable()


def test_install_failure_does_not_enable_or_remove_existing_extension():
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=1, stdout="", stderr="already installed")

    with pytest.raises(module.ExtensionError):
        module.ExtensionManager(runner=run).install()
    assert [command[1] for command in commands] == ["install"]
    assert "--force" not in commands[0]


def test_bundled_files_match_verified_hashes():
    manager = module.ExtensionManager()
    assert manager._verified(manager.source)


def test_status_does_not_claim_foreign_or_tampered_extension_is_active(tmp_path):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(
            returncode=0, stdout=f"  State: ACTIVE\n  Path: {tmp_path}\n"
        )

    for name in module.FILES:
        (tmp_path / name).write_bytes(b"unrelated extension")
    manager = module.ExtensionManager(runner=run)
    assert "未通过校验" in manager.status()
    assert [command[1] for command in calls] == ["info"]


def test_status_does_not_claim_active_when_path_missing():
    manager = module.ExtensionManager(
        runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout="State: ACTIVE\n")
    )
    assert "无法确认" in manager.status()
