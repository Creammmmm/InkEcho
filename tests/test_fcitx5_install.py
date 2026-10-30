import hashlib
import json
from types import SimpleNamespace

import pytest

from inkecho.platform import fcitx5_staging as staging
from inkecho.platform.fcitx5_install import FcitxInstaller, FcitxInstallError


@pytest.mark.parametrize("value", [None, "", "relative/data"])
def test_default_data_home_ignores_unset_empty_or_relative_xdg_path(
    tmp_path, monkeypatch, value
):
    monkeypatch.setenv("HOME", str(tmp_path))
    if value is None:
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    else:
        monkeypatch.setenv("XDG_DATA_HOME", value)
    assert FcitxInstaller().data_home == tmp_path / ".local/share"


def test_data_home_accepts_absolute_xdg_path_and_explicit_override(
    tmp_path, monkeypatch
):
    configured = tmp_path / "configured"
    explicit = tmp_path / "explicit"
    monkeypatch.setenv("XDG_DATA_HOME", str(configured))
    assert FcitxInstaller().data_home == configured
    assert FcitxInstaller(data_home=explicit).data_home == explicit


@pytest.fixture
def candidate_source(tmp_path, monkeypatch):
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
    return source


def test_auto_version_discovers_installed_bridge_for_valid_xdg_paths(
    tmp_path, monkeypatch, candidate_source
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "platform.freedesktop_os_release",
        lambda: {"ID": "ubuntu", "VERSION_ID": "26.04"},
    )
    monkeypatch.setattr("platform.machine", lambda: "x86_64")

    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="5.1.19")

    default_data = tmp_path / ".local/share"
    default_data.mkdir(parents=True, mode=0o700)
    default_data.parent.chmod(0o700)
    FcitxInstaller(
        source=candidate_source, data_home=default_data, runner=runner
    ).install()
    for value in (None, "", "relative/data"):
        if value is None:
            monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        else:
            monkeypatch.setenv("XDG_DATA_HOME", value)
        assert FcitxInstaller(runner=runner).auto_version() == "5.1.19"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(mode=0o700)
    monkeypatch.setenv("XDG_DATA_HOME", str(elsewhere))
    assert FcitxInstaller(runner=runner).auto_version() is None
    monkeypatch.setenv("XDG_DATA_HOME", str(default_data))
    assert FcitxInstaller(runner=runner).auto_version() == "5.1.19"


def test_explicit_actions_check_pinned_files_and_preserve_loaded_library(
    tmp_path, monkeypatch, candidate_source
):
    source = candidate_source
    binary = (source / "candidate/libinkecho.so").read_bytes()
    digest = hashlib.sha256(binary).hexdigest()
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


def test_enable_restores_verified_bridge_after_disable(
    tmp_path, monkeypatch, candidate_source
):
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
    manager = FcitxInstaller(source=candidate_source, data_home=data, runner=runner)
    manager.install()
    digest = staging.TESTED_CANDIDATE_SHA256
    library = data / "inkecho/fcitx5" / digest / "libinkecho.so"
    original_inode = library.stat().st_ino
    manager.disable()
    assert not manager.available_for_auto()
    manager.enable()
    assert manager.available_for_auto()
    assert library.stat().st_ino == original_inode
    assert sum("Refresh" in " ".join(call) for call in calls) == 1


@pytest.mark.parametrize("failure", ["foreign", "symlink", "library", "source"])
def test_reenable_never_overwrites_or_refreshes_unverified_files(
    tmp_path, monkeypatch, candidate_source, failure
):
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
    manager = FcitxInstaller(source=candidate_source, data_home=data, runner=runner)
    manager.install()
    manager.disable()
    description = data / "fcitx5/addon/inkecho.conf"
    library = (
        data / "inkecho/fcitx5" / staging.TESTED_CANDIDATE_SHA256 / "libinkecho.so"
    )
    foreign = tmp_path / "foreign"
    foreign.write_text("foreign")
    if failure == "foreign":
        description.write_text("foreign")
    elif failure == "symlink":
        description.symlink_to(foreign)
    elif failure == "library":
        library.write_bytes(b"modified")
    else:
        (candidate_source / "candidate/libinkecho.so").write_bytes(b"modified")
    with pytest.raises(FcitxInstallError):
        manager.enable()
    assert not any("Refresh" in " ".join(call) for call in calls)
    assert foreign.read_text() == "foreign"
    if failure == "foreign":
        assert description.read_text() == "foreign"
    elif failure == "symlink":
        assert description.is_symlink()
    else:
        assert not description.exists()


@pytest.mark.parametrize(
    "mode", ["failure", "timeout", "replaced", "unlink_recreate", "preexisting"]
)
def test_failed_refresh_preserves_description_and_reports_unknown_state(
    tmp_path, monkeypatch, candidate_source, mode
):
    import os
    import subprocess

    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    calls = []
    description = data / "fcitx5/addon/inkecho.conf"
    replacement_inode = []

    def runner(args, **_kwargs):
        calls.append(args)
        if args[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout="5.1.19")
        if mode == "timeout":
            raise subprocess.TimeoutExpired(args, 10)
        if mode == "replaced":
            replacement = description.with_name("replacement.conf")
            replacement.write_bytes(description.read_bytes())
            replacement_inode.append(replacement.stat().st_ino)
            os.replace(replacement, description)
        elif mode == "unlink_recreate":
            content = description.read_bytes()
            description.unlink()
            description.write_bytes(content)
            replacement_inode.append(description.stat().st_ino)
        return SimpleNamespace(returncode=1, stdout="")

    monkeypatch.setattr(
        "platform.freedesktop_os_release",
        lambda: {"ID": "ubuntu", "VERSION_ID": "26.04"},
    )
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    manager = FcitxInstaller(source=candidate_source, data_home=data, runner=runner)
    manager.install()
    if mode != "preexisting":
        manager.disable()
    with pytest.raises(FcitxInstallError) as caught:
        manager.enable()
    assert sum("Refresh" in " ".join(call) for call in calls) == 1
    assert "刷新未确认" in str(caught.value)
    assert "配置可能已保留或改变" in str(caught.value)
    assert "插件状态未知" in str(caught.value)
    assert description.exists()
    if mode in {"replaced", "unlink_recreate"}:
        assert description.stat().st_ino == replacement_inode[0]


@pytest.mark.parametrize("fault", ["directory_fsync", "temporary_unlink"])
def test_reenable_reports_uncertain_post_publication_failure(
    tmp_path, monkeypatch, candidate_source, fault
):
    import os

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
    manager = FcitxInstaller(source=candidate_source, data_home=data, runner=runner)
    manager.install()
    manager.disable()
    addon = data / "fcitx5/addon"
    description = addon / "inkecho.conf"
    real_fsync, real_unlink = os.fsync, os.unlink
    triggered = []

    def at_addon(fd):
        return os.path.realpath(f"/proc/self/fd/{fd}") == str(addon)

    def fsync(fd):
        if fault == "directory_fsync" and at_addon(fd) and description.exists():
            triggered.append(True)
            raise OSError("injected directory fsync failure")
        return real_fsync(fd)

    def unlink(path, *, dir_fd=None):
        if (
            fault == "temporary_unlink"
            and dir_fd is not None
            and at_addon(dir_fd)
            and str(path).startswith(".inkecho-")
            and description.exists()
        ):
            triggered.append(True)
            raise OSError("injected temporary unlink failure")
        return real_unlink(path, dir_fd=dir_fd)

    monkeypatch.setattr(os, "fsync", fsync)
    monkeypatch.setattr(os, "unlink", unlink)
    with pytest.raises(FcitxInstallError, match="恢复未确认.*可能已发布或改变"):
        manager.enable()
    assert triggered and description.exists()
    assert manager.available_for_auto()
    assert not any("Refresh" in " ".join(call) for call in calls)


def test_install_creates_missing_default_xdg_directory(
    tmp_path, monkeypatch, candidate_source
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(
        "platform.freedesktop_os_release",
        lambda: {"ID": "ubuntu", "VERSION_ID": "26.04"},
    )
    monkeypatch.setattr("platform.machine", lambda: "x86_64")

    def runner(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="5.1.19")

    manager = FcitxInstaller(source=candidate_source, runner=runner)
    assert not manager.data_home.exists()
    manager.install()
    assert manager.available_for_auto()
    assert (manager.data_home / "fcitx5/addon/inkecho.conf").is_file()


def test_install_creates_missing_absolute_xdg_directory(
    tmp_path, monkeypatch, candidate_source
):
    target = tmp_path / "custom" / "nested" / "share"
    monkeypatch.setenv("XDG_DATA_HOME", str(target))
    monkeypatch.setattr(
        "platform.freedesktop_os_release",
        lambda: {"ID": "ubuntu", "VERSION_ID": "26.04"},
    )
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    manager = FcitxInstaller(
        source=candidate_source,
        runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="5.1.19"),
    )
    manager.install()
    assert manager.available_for_auto()
    for directory in (target, target.parent, target.parent.parent):
        assert directory.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("failure", ["unsafe_parent", "symlink", "candidate"])
def test_install_missing_xdg_does_not_create_under_unsafe_inputs(
    tmp_path, monkeypatch, candidate_source, failure
):
    parent = tmp_path / "custom"
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    if failure == "symlink":
        parent.symlink_to(outside, target_is_directory=True)
    elif failure == "unsafe_parent":
        parent.mkdir(mode=0o700)
        parent.chmod(0o777)
    else:
        (candidate_source / "candidate/libinkecho.so").write_bytes(b"modified")
    target = parent / "share"
    monkeypatch.setenv("XDG_DATA_HOME", str(target))
    monkeypatch.setattr(
        "platform.freedesktop_os_release",
        lambda: {"ID": "ubuntu", "VERSION_ID": "26.04"},
    )
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    manager = FcitxInstaller(
        source=candidate_source,
        runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="5.1.19"),
    )
    with pytest.raises(FcitxInstallError):
        manager.install()
    assert not target.exists()
    assert not (outside / "share").exists()
    if failure == "candidate":
        assert not parent.exists()


def test_existing_install_with_writable_ancestor_can_be_detected_and_disabled(
    tmp_path, monkeypatch, candidate_source
):
    ancestor = tmp_path / "writable"
    data = ancestor / "data"
    data.mkdir(parents=True, mode=0o700)
    ancestor.chmod(0o775)
    monkeypatch.setattr(
        FcitxInstaller, "_system", lambda self: ("ubuntu", "26.04", "x86_64", "5.1.19")
    )
    manager = FcitxInstaller(source=candidate_source, data_home=data)
    manager.install()
    assert manager.auto_version() == "5.1.19"
    manager.disable()
    assert manager.auto_version() is None
