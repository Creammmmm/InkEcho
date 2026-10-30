import hashlib
import json
import os
from pathlib import Path

import pytest

from inkecho.platform import fcitx5_staging
from inkecho.platform.fcitx5_staging import StagingError, _conf, deactivate, stage


@pytest.fixture(autouse=True)
def trusted_fixture_hash(monkeypatch):
    binary = b"\x7fELF\x02\x01" + bytes(10) + b"\x03\x00\x3e\x00" + bytes(44)
    monkeypatch.setattr(
        fcitx5_staging, "TESTED_CANDIDATE_SHA256", hashlib.sha256(binary).hexdigest()
    )


def candidate(tmp_path):
    root = tmp_path / "source"
    output = root / "candidate"
    output.mkdir(parents=True)
    root.chmod(0o700)
    output.chmod(0o700)
    binary = b"\x7fELF\x02\x01" + bytes(10) + b"\x03\x00\x3e\x00" + bytes(44)
    description = _conf("libinkecho", "5.1.7")
    (output / "libinkecho.so").write_bytes(binary)
    (output / "inkecho.conf").write_bytes(description)
    (output / "libinkecho.so").chmod(0o600)
    (output / "inkecho.conf").chmod(0o600)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "status": "uninstalled-candidate",
                "os_id": "ubuntu",
                "os_version": "24.04",
                "architecture": "x86_64",
                "fcitx5_core_version": "5.1.7",
                "files_sha256": {
                    "libinkecho.so": hashlib.sha256(binary).hexdigest(),
                    "inkecho.conf": hashlib.sha256(description).hexdigest(),
                },
            }
        )
    )
    (root / "manifest.json").chmod(0o600)
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    return root, data


def publish(source, data):
    return stage(
        source,
        data,
        os_id="ubuntu",
        os_version="24.04",
        architecture="x86_64",
        fcitx_version="5.1.7",
    )


def test_deactivate_keeps_library_and_never_restarts_anything(tmp_path):
    source, data = candidate(tmp_path)
    digest = publish(source, data)
    description = data / "fcitx5/addon/inkecho.conf"
    library = data / "inkecho/fcitx5" / digest / "libinkecho.so"
    assert description.is_file() and library.is_file()
    deactivate(data, digest=digest, fcitx_version="5.1.7")
    assert not description.exists()
    assert library.read_bytes().startswith(b"\x7fELF")


def test_existing_foreign_description_is_never_overwritten(tmp_path):
    source, data = candidate(tmp_path)
    addon = data / "fcitx5/addon"
    addon.mkdir(parents=True)
    addon.parent.chmod(0o700)
    addon.chmod(0o700)
    (addon / "inkecho.conf").write_text("not ours")
    with pytest.raises(StagingError, match="description_exists"):
        publish(source, data)
    assert (addon / "inkecho.conf").read_text() == "not ours"


def test_changed_description_is_not_removed(tmp_path):
    source, data = candidate(tmp_path)
    digest = publish(source, data)
    description = data / "fcitx5/addon/inkecho.conf"
    description.write_text("user modified")
    with pytest.raises(StagingError, match="description_changed"):
        deactivate(data, digest=digest, fcitx_version="5.1.7")
    assert description.read_text() == "user modified"


def test_symlinked_data_home_and_candidate_files_are_rejected(tmp_path):
    source, data = candidate(tmp_path)
    link = tmp_path / "link"
    link.symlink_to(data, target_is_directory=True)
    with pytest.raises(OSError):
        publish(source, link)
    binary = source / "candidate/libinkecho.so"
    binary.unlink()
    binary.symlink_to(Path("/etc/passwd"))
    with pytest.raises(OSError):
        publish(source, data)


def test_hash_mismatch_fails_before_description_publication(tmp_path):
    source, data = candidate(tmp_path)
    binary = source / "candidate/libinkecho.so"
    binary.write_bytes(binary.read_bytes() + b"tampered")
    with pytest.raises(StagingError, match="candidate_hash_mismatch"):
        publish(source, data)
    assert not (data / "fcitx5/addon/inkecho.conf").exists()


def test_wrong_elf_architecture_is_rejected_before_publication(tmp_path):
    source, data = candidate(tmp_path)
    binary = source / "candidate/libinkecho.so"
    contents = bytearray(binary.read_bytes())
    contents[18:20] = (183).to_bytes(2, "little")
    binary.write_bytes(contents)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files_sha256"]["libinkecho.so"] = hashlib.sha256(contents).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(StagingError, match="invalid_library_architecture"):
        publish(source, data)
    assert not (data / "fcitx5/addon/inkecho.conf").exists()


def test_deactivation_preserves_a_concurrently_replaced_description(
    tmp_path, monkeypatch
):
    source, data = candidate(tmp_path)
    digest = publish(source, data)
    description = data / "fcitx5/addon/inkecho.conf"
    original_rename = os.rename

    def raced_rename(src, dst, **kwargs):
        description.write_text("another application's file")
        return original_rename(src, dst, **kwargs)

    monkeypatch.setattr(os, "rename", raced_rename)
    with pytest.raises(StagingError, match="description_changed"):
        deactivate(data, digest=digest, fcitx_version="5.1.7")
    assert description.read_text() == "another application's file"


def test_only_pinned_hash_authorizes_ubuntu_26(tmp_path):
    source, data = candidate(tmp_path)
    digest = stage(
        source,
        data,
        os_id="ubuntu",
        os_version="26.04",
        architecture="x86_64",
        fcitx_version="5.1.19",
    )
    assert digest == fcitx5_staging.TESTED_CANDIDATE_SHA256
    assert b"0=core:5.1.19" in (data / "fcitx5/addon/inkecho.conf").read_bytes()


def test_editable_manifest_cannot_authorize_another_binary(tmp_path):
    source, data = candidate(tmp_path)
    binary = source / "candidate/libinkecho.so"
    binary.write_bytes(binary.read_bytes() + b"tamper")
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files_sha256"]["libinkecho.so"] = hashlib.sha256(
        binary.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(StagingError, match="unverified_candidate"):
        publish(source, data)
    assert not (data / "fcitx5/addon/inkecho.conf").exists()


def test_untested_version_rejected_despite_manifest(tmp_path):
    source, data = candidate(tmp_path)
    with pytest.raises(StagingError, match="incompatible_candidate"):
        stage(
            source,
            data,
            os_id="ubuntu",
            os_version="26.04",
            architecture="x86_64",
            fcitx_version="5.1.20",
        )


def test_interrupted_library_write_does_not_poison_retry(tmp_path, monkeypatch):
    source, data = candidate(tmp_path)
    real_new = fcitx5_staging._new_file

    def fail_partway(parent, name, content):
        if name == "libinkecho.so" or name.startswith(".inkecho-lib-"):
            fd = os.open(
                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent
            )
            try:
                os.write(fd, content[:8])
            finally:
                os.close(fd)
            raise OSError("simulated interrupted write")
        return real_new(parent, name, content)

    monkeypatch.setattr(fcitx5_staging, "_new_file", fail_partway)
    with pytest.raises(OSError, match="interrupted"):
        publish(source, data)
    digest = fcitx5_staging.TESTED_CANDIDATE_SHA256
    assert not (data / "inkecho/fcitx5" / digest / "libinkecho.so").exists()
    monkeypatch.setattr(fcitx5_staging, "_new_file", real_new)
    assert publish(source, data) == digest
    assert (data / "fcitx5/addon/inkecho.conf").is_file()


def test_concurrent_first_installs_preserve_published_content(tmp_path, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from inkecho.platform.fcitx5_install import FcitxInstaller

    source, data = candidate(tmp_path)
    managers = [FcitxInstaller(source=source, data_home=data) for _ in range(2)]
    for manager in managers:
        monkeypatch.setattr(
            manager, "_system", lambda: ("ubuntu", "24.04", "x86_64", "5.1.7")
        )
    barrier = threading.Barrier(2, timeout=5)
    real_link = os.link

    def concurrent_link(src, dst, **kwargs):
        if dst == "inkecho.conf":
            barrier.wait()
        return real_link(src, dst, **kwargs)

    monkeypatch.setattr(os, "link", concurrent_link)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(manager.install) for manager in managers]
        for future in futures:
            future.result(timeout=10)
    assert all(manager._check_staged("5.1.7") for manager in managers)


def test_existing_corrupt_library_is_never_overwritten(tmp_path):
    source, data = candidate(tmp_path)
    digest = fcitx5_staging.TESTED_CANDIDATE_SHA256
    directory = data / "inkecho/fcitx5" / digest
    directory.mkdir(parents=True, mode=0o700)
    for path in (directory, directory.parent, directory.parent.parent):
        path.chmod(0o700)
    library = directory / "libinkecho.so"
    library.write_bytes(b"user-modified-or-incomplete")
    library.chmod(0o600)
    with pytest.raises(StagingError, match="library_conflict"):
        publish(source, data)
    assert library.read_bytes() == b"user-modified-or-incomplete"
    assert not (data / "fcitx5/addon/inkecho.conf").exists()


def test_killed_library_writer_leaves_no_published_partial(tmp_path):
    import subprocess
    import sys
    import time

    source, data = candidate(tmp_path)
    digest = fcitx5_staging.TESTED_CANDIDATE_SHA256
    marker = tmp_path / "writer-ready"
    script = r"""
import os, sys, time
from pathlib import Path
from inkecho.platform import fcitx5_staging as staging
source, data, marker, digest = sys.argv[1:]
staging.TESTED_CANDIDATE_SHA256 = digest
original = staging._new_file
def interrupted(parent, name, content):
    if name.startswith('.inkecho-lib-'):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=parent)
        os.write(fd, content[:8])
        os.fsync(fd)
        Path(marker).write_text('ready')
        time.sleep(30)
        os.close(fd)
        raise RuntimeError('unexpected resume')
    return original(parent, name, content)
staging._new_file = interrupted
staging.stage(Path(source), Path(data), os_id='ubuntu', os_version='24.04',
              architecture='x86_64', fcitx_version='5.1.7')
"""
    child = subprocess.Popen(
        [sys.executable, "-c", script, str(source), str(data), str(marker), digest],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 5
        while (
            not marker.exists() and child.poll() is None and time.monotonic() < deadline
        ):
            time.sleep(0.01)
        assert marker.exists(), "child did not begin library write"
    finally:
        child.kill()
        child.communicate(timeout=5)
    directory = data / "inkecho/fcitx5" / digest
    assert not (directory / "libinkecho.so").exists()
    assert not (data / "fcitx5/addon/inkecho.conf").exists()
    # A crashed writer's private temp file is not trusted or overwritten.
    assert any(path.name.startswith(".inkecho-lib-") for path in directory.iterdir())
    assert publish(source, data) == digest


def test_create_missing_directory_rejects_concurrent_symlink(tmp_path, monkeypatch):
    import os

    from inkecho.platform import fcitx5_staging

    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    target = tmp_path / "new" / "share"
    original_mkdir = os.mkdir

    def race(name, mode=0o777, *, dir_fd=None):
        if name == "new" and dir_fd is not None:
            os.symlink(str(outside), name, dir_fd=dir_fd)
            raise FileExistsError
        return original_mkdir(name, mode, dir_fd=dir_fd)

    monkeypatch.setattr(fcitx5_staging.os, "mkdir", race)
    with pytest.raises(OSError):
        fcitx5_staging._directory(target, create_missing=True)
    assert not (outside / "share").exists()


def test_untrusted_writable_ancestor_rejected_for_creation(tmp_path):
    ancestor = tmp_path / "writable"
    target = ancestor / "private" / "share"
    target.parent.mkdir(parents=True, mode=0o700)
    ancestor.chmod(0o777)
    with pytest.raises(StagingError, match="unsafe_directory"):
        fcitx5_staging._directory(target, create_missing=True)
    assert not target.exists()


def test_trusted_sticky_ancestor_allows_owned_child(tmp_path):
    sticky = tmp_path / "sticky"
    owned = sticky / "owned"
    owned.mkdir(parents=True, mode=0o700)
    sticky.chmod(0o1777)
    target = owned / "share"
    fd = fcitx5_staging._directory(target, create_missing=True)
    os.close(fd)
    assert target.stat().st_mode & 0o777 == 0o700


def test_sticky_ancestor_does_not_authorize_creation_directly(tmp_path):
    sticky = tmp_path / "sticky"
    sticky.mkdir(mode=0o700)
    sticky.chmod(0o1777)
    with pytest.raises(StagingError, match="unsafe_directory"):
        fcitx5_staging._directory(sticky / "share", create_missing=True)
    assert not (sticky / "share").exists()


@pytest.mark.parametrize("sticky", [False, True])
def test_foreign_owned_ancestor_rejected(tmp_path, monkeypatch, sticky):
    from types import SimpleNamespace

    parent = tmp_path / "parent"
    foreign = parent / "foreign"
    target = foreign / "share"
    foreign.mkdir(parents=True, mode=0o700)
    if sticky:
        parent.chmod(0o1777)
    foreign_identity = foreign.stat().st_dev, foreign.stat().st_ino
    original_fstat = os.fstat

    def foreign_owner(fd):
        info = original_fstat(fd)
        if (info.st_dev, info.st_ino) == foreign_identity:
            return SimpleNamespace(st_uid=os.getuid() + 1, st_mode=info.st_mode)
        return info

    monkeypatch.setattr(fcitx5_staging.os, "fstat", foreign_owner)
    with pytest.raises(StagingError, match="unsafe_directory"):
        fcitx5_staging._directory(target, create_missing=True)


def test_candidate_source_allows_writable_ancestor_when_bytes_are_verified(tmp_path):
    ancestor = tmp_path / "source_parent"
    ancestor.mkdir(mode=0o700)
    source, _ = candidate(ancestor)
    ancestor.chmod(0o775)
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    assert publish(source, data)


def test_existing_data_path_with_writable_ancestor_retains_baseline(tmp_path):
    source, _ = candidate(tmp_path)
    ancestor = tmp_path / "group_writable"
    data = ancestor / "data"
    data.mkdir(parents=True, mode=0o700)
    ancestor.chmod(0o775)
    digest = publish(source, data)
    assert deactivate(data, digest=digest) is None
