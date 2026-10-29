import hashlib
import json
from types import SimpleNamespace

import pytest

from inkecho.platform import fcitx5_staging as staging
from inkecho.platform.fcitx5_install import FcitxInstaller, FcitxInstallError


def test_explicit_actions_check_pinned_files_and_preserve_loaded_library(
    tmp_path, monkeypatch
):
    source = tmp_path / "source"
    candidate = source / "candidate"
    candidate.mkdir(parents=True, mode=0o700)
    source.chmod(0o700)
    binary = b"\x7fELF\x02\x01" + bytes(10) + b"\x03\x00\x3e\x00" + bytes(44)
    conf = staging._conf("libinkecho", "5.1.7")
    digest = hashlib.sha256(binary).hexdigest()
    monkeypatch.setattr(staging, "TESTED_CANDIDATE_SHA256", digest)
    for name, content in (("libinkecho.so", binary), ("inkecho.conf", conf)):
        path = candidate / name
        path.write_bytes(content)
        path.chmod(0o600)
    manifest = {
        "status": "uninstalled-candidate",
        "os_id": "ubuntu",
        "os_version": "24.04",
        "architecture": "x86_64",
        "fcitx5_core_version": "5.1.7",
        "files_sha256": {
            "libinkecho.so": digest,
            "inkecho.conf": hashlib.sha256(conf).hexdigest(),
        },
    }
    path = source / "manifest.json"
    path.write_text(json.dumps(manifest))
    path.chmod(0o600)
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    calls = []

    def runner(args, **_kwargs):
        calls.append(args)
        return SimpleNamespace(
            returncode=0, stdout="5.1.19" if args[-1] == "--version" else "()"
        )

    monkeypatch.setattr(
        "platform.freedesktop_os_release",
        lambda: {"ID": "ubuntu", "VERSION_ID": "26.04"},
    )
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    manager = FcitxInstaller(source=source, data_home=data, runner=runner)
    assert "未发现" in manager.status()
    assert all("Refresh" not in " ".join(call) for call in calls)
    with pytest.raises(FcitxInstallError, match="先安装"):
        manager.enable()
    manager.install()
    description = data / "fcitx5/addon/inkecho.conf"
    original = description.read_bytes()
    before = description.stat()
    manager.install()
    after = description.stat()
    assert description.read_bytes() == original
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)
    modified = original + b"# user modification\n"
    description.write_bytes(modified)
    with pytest.raises(FcitxInstallError, match="已有输入桥配置"):
        manager.install()
    assert description.read_bytes() == modified
    description.write_bytes(original)
    assert "已安装" in manager.status()
    assert manager.available_for_auto()
    manager.runner = lambda *_args, **_kwargs: SimpleNamespace(
        returncode=0, stdout="5.1.20"
    )
    assert not manager.available_for_auto()
    manager.runner = runner
    manager.enable()
    assert sum("Refresh" in " ".join(call) for call in calls) == 1
    library = data / "inkecho/fcitx5" / digest / "libinkecho.so"
    # Removal must remain possible after an upgrade, or even removal, of Fcitx.
    manager.runner = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        OSError("fcitx executable unavailable")
    )
    manager.disable()
    assert not manager.available_for_auto()
    assert not (data / "fcitx5/addon/inkecho.conf").exists()
    assert library.read_bytes() == binary


def test_disable_preserves_foreign_description_without_fcitx(tmp_path, monkeypatch):
    digest = "a" * 64
    monkeypatch.setattr(staging, "TESTED_CANDIDATE_SHA256", digest)
    addon = tmp_path / "fcitx5" / "addon"
    addon.mkdir(parents=True, mode=0o700)
    addon.parent.chmod(0o700)
    description = addon / "inkecho.conf"
    description.write_text("foreign configuration")
    description.chmod(0o600)
    manager = FcitxInstaller(data_home=tmp_path)
    with pytest.raises(FcitxInstallError, match="停用未完成"):
        manager.disable()
    assert description.read_text() == "foreign configuration"


@pytest.mark.parametrize("old_digest", staging.RETIRED_CANDIDATE_SHA256)
def test_disable_recognizes_retired_candidate_after_upgrade(tmp_path, old_digest):
    addon = tmp_path / "fcitx5" / "addon"
    addon.mkdir(parents=True, mode=0o700)
    addon.parent.chmod(0o700)
    description = addon / "inkecho.conf"
    old_library = tmp_path / "inkecho" / "fcitx5" / old_digest / "libinkecho"
    description.write_bytes(staging._conf(str(old_library), "5.1.7"))
    description.chmod(0o600)
    manager = FcitxInstaller(data_home=tmp_path)
    manager.disable()
    assert not description.exists()


@pytest.mark.parametrize("old_digest", staging.RETIRED_CANDIDATE_SHA256)
def test_disable_preserves_retired_candidate_description_if_modified(
    tmp_path, old_digest
):
    addon = tmp_path / "fcitx5" / "addon"
    addon.mkdir(parents=True, mode=0o700)
    addon.parent.chmod(0o700)
    description = addon / "inkecho.conf"
    old_library = tmp_path / "inkecho" / "fcitx5" / old_digest / "libinkecho"
    contents = staging._conf(str(old_library), "5.1.7") + b"# modified\n"
    description.write_bytes(contents)
    description.chmod(0o600)
    with pytest.raises(FcitxInstallError, match="停用未完成"):
        FcitxInstaller(data_home=tmp_path).disable()
    assert description.read_bytes() == contents


def test_install_is_disabled_without_verified_candidate(monkeypatch, tmp_path):
    monkeypatch.setattr(staging, "TESTED_CANDIDATE_SHA256", "")
    monkeypatch.setattr(
        "platform.freedesktop_os_release",
        lambda: {"ID": "ubuntu", "VERSION_ID": "26.04"},
    )
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    manager = FcitxInstaller(
        source=tmp_path,
        data_home=tmp_path,
        runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout="5.1.19"),
    )
    with pytest.raises(FcitxInstallError, match="没有通过"):
        manager.install()


def test_missing_fcitx_binary_gives_install_guidance(tmp_path):
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        raise FileNotFoundError("private test path")

    manager = FcitxInstaller(source=tmp_path, data_home=tmp_path, runner=runner)
    with pytest.raises(FcitxInstallError, match="安装 Fcitx5") as error:
        manager.install()
    assert "private test path" not in str(error.value)
    assert calls == [["/usr/bin/fcitx5", "--version"]]
    assert not manager.available_for_auto()


def test_missing_dbus_tool_does_not_claim_fcitx_is_missing(tmp_path):
    manager = FcitxInstaller(
        data_home=tmp_path,
        runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )
    with pytest.raises(FcitxInstallError, match="服务不可用") as error:
        manager._run(["/usr/bin/gdbus", "call"])
    assert "安装 Fcitx5" not in str(error.value)
