import os
import subprocess
import sys

import pytest

from inkecho.platform.fcitx5_capability import Capability


def test_exclusive_lock_and_owned_cleanup(tmp_path):
    cap = Capability(tmp_path)
    assert (tmp_path / "inkecho-fcitx-candidate.cap").read_text() == cap.token
    with pytest.raises(BlockingIOError):
        Capability(tmp_path)
    cap.close()
    assert not (tmp_path / "inkecho-fcitx-candidate.cap").exists()
    again = Capability(tmp_path)
    again.close()


def test_process_crash_releases_lock_and_allows_safe_stale_recovery(tmp_path):
    code = (
        "import os,sys; from inkecho.platform.fcitx5_capability import Capability; "
        "c=Capability(sys.argv[1]); os._exit(0)"
    )
    subprocess.run([sys.executable, "-c", code, str(tmp_path)], check=True)
    stale = tmp_path / "inkecho-fcitx-candidate.cap"
    assert stale.exists()
    old = stale.read_bytes()
    cap = Capability(tmp_path)
    assert stale.read_bytes() != old
    cap.close()
    assert not stale.exists()


def test_foreign_stale_or_symlink_never_removed(tmp_path):
    foreign = tmp_path / "inkecho-fcitx-candidate.cap"
    foreign.write_text("foreign")
    foreign.chmod(0o600)
    with pytest.raises(ValueError, match="foreign capability"):
        Capability(tmp_path)
    assert foreign.read_text() == "foreign"
    foreign.unlink()
    foreign.symlink_to("other")
    with pytest.raises(OSError):
        Capability(tmp_path)
    assert foreign.is_symlink()


def test_unsafe_runtime_rejected(tmp_path):
    os.chmod(tmp_path, 0o755)
    with pytest.raises(ValueError, match="unsafe runtime"):
        Capability(tmp_path)


def test_failed_publication_never_leaves_partially_written_capability(
    tmp_path, monkeypatch
):
    original_write = os.write
    writes = 0

    def interrupted(fd, data):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("simulated interrupted write")
        return original_write(fd, data)

    monkeypatch.setattr(os, "write", interrupted)
    with pytest.raises(OSError, match="simulated interrupted write"):
        Capability(tmp_path)
    assert not (tmp_path / "inkecho-fcitx-candidate.cap").exists()
    monkeypatch.setattr(os, "write", original_write)
    cap = Capability(tmp_path)
    cap.close()


@pytest.mark.parametrize("operation", ["stat", "unlink"])
def test_cleanup_error_releases_lock_and_redacts_token(
    tmp_path, monkeypatch, operation
):
    cap = Capability(tmp_path)
    lock_fd, directory_fd, cap_fd = cap.lock_fd, cap.fd, cap.cap_fd
    original = getattr(os, operation)

    def fail(*args, **kwargs):
        raise PermissionError("private fixture error")

    monkeypatch.setattr(os, operation, fail)
    with pytest.raises(PermissionError):
        cap.close()
    monkeypatch.setattr(os, operation, original)
    assert cap.lock_fd is None and cap.fd is None and cap.token == ""
    assert cap.cap_fd is None
    for fd in (lock_fd, directory_fd, cap_fd):
        with pytest.raises(OSError):
            os.fstat(fd)
    # The old owned file remains until the next owner verifies and replaces it.
    again = Capability(tmp_path)
    again.close()


@pytest.mark.parametrize("replacement", ["regular", "symlink"])
def test_live_unlinked_inode_remains_reserved_and_replacement_survives(
    tmp_path, replacement
):
    cap = Capability(tmp_path)
    fd = cap.cap_fd
    path = tmp_path / "inkecho-fcitx-candidate.cap"
    path.unlink()
    assert os.fstat(fd).st_nlink == 0
    if replacement == "regular":
        path.write_text("foreign")
    else:
        path.symlink_to("foreign")
    info = path.lstat()
    assert (info.st_dev, info.st_ino) != cap.identity
    cap.close()
    assert (
        path.is_symlink() if replacement == "symlink" else path.read_text() == "foreign"
    )
    with pytest.raises(OSError):
        os.fstat(fd)
    cap.close()


def test_symlink_never_removed_even_if_identity_matches(tmp_path):
    cap = Capability(tmp_path)
    path = tmp_path / "inkecho-fcitx-candidate.cap"
    path.unlink()
    path.symlink_to("foreign")
    info = path.lstat()
    cap.identity = (info.st_dev, info.st_ino)
    cap.close()
    assert path.is_symlink()


def test_failed_token_write_closes_unnamed_capability_fd(tmp_path, monkeypatch):
    original_open, original_write = os.open, os.write
    opened = []

    def track(*args, **kwargs):
        fd = original_open(*args, **kwargs)
        opened.append(fd)
        return fd

    writes = 0

    def fail(fd, data):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("synthetic token write failure")
        return original_write(fd, data)

    monkeypatch.setattr(os, "open", track)
    monkeypatch.setattr(os, "write", fail)
    with pytest.raises(OSError, match="synthetic token write failure"):
        Capability(tmp_path)
    assert len(opened) == 3
    for fd in opened:
        with pytest.raises(OSError):
            os.fstat(fd)
    assert not (tmp_path / "inkecho-fcitx-candidate.cap").exists()
