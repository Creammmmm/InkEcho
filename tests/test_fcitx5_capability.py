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
    lock_fd, directory_fd = cap.lock_fd, cap.fd
    original = getattr(os, operation)

    def fail(*args, **kwargs):
        raise PermissionError("private fixture error")

    monkeypatch.setattr(os, operation, fail)
    with pytest.raises(PermissionError):
        cap.close()
    monkeypatch.setattr(os, operation, original)
    assert cap.lock_fd is None and cap.fd is None and cap.token == ""
    for fd in (lock_fd, directory_fd):
        with pytest.raises(OSError):
            os.fstat(fd)
    # The old owned file remains until the next owner verifies and replaces it.
    again = Capability(tmp_path)
    again.close()
