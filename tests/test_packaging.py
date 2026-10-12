"""AppImage publication never truncates a running or previously valid package."""

import hashlib
import runpy
from pathlib import Path

import pytest


@pytest.fixture
def publisher(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts/packaging"
    monkeypatch.syspath_prepend(str(scripts))
    return runpy.run_path(str(scripts / "build_appimage.py"))["publish_appimage"]


def test_publish_replaces_path_but_preserves_open_image(publisher, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.write_bytes(b"runtime")
    squashfs = tmp_path / "squashfs"
    squashfs.write_bytes(b"filesystem")
    artifact = tmp_path / "InkEcho.AppImage"
    artifact.write_bytes(b"running image")
    with artifact.open("rb") as mounted:
        digest = publisher(runtime, squashfs, artifact)
        assert mounted.read() == b"running image"
    assert artifact.read_bytes() == b"runtimefilesystem"
    assert digest == hashlib.sha256(b"runtimefilesystem").hexdigest()
    assert artifact.stat().st_mode & 0o777 == 0o755
    assert artifact.with_suffix(".AppImage.sha256").read_text() == (
        f"{digest}  InkEcho.AppImage\n"
    )
    assert not list(tmp_path.glob(".*"))


def test_failed_payload_preserves_existing_image(publisher, tmp_path):
    runtime = tmp_path / "runtime"
    runtime.write_bytes(b"runtime")
    artifact = tmp_path / "InkEcho.AppImage"
    artifact.write_bytes(b"known good")
    checksum = artifact.with_suffix(".AppImage.sha256")
    checksum.write_text("known checksum")
    with pytest.raises(FileNotFoundError):
        publisher(runtime, tmp_path / "missing-squashfs", artifact)
    assert artifact.read_bytes() == b"known good"
    assert checksum.read_text() == "known checksum"
    assert not list(tmp_path.glob(".*"))


def test_failed_checksum_preparation_preserves_image(publisher, tmp_path, monkeypatch):
    import tempfile

    runtime = tmp_path / "runtime"
    runtime.write_bytes(b"runtime")
    squashfs = tmp_path / "squashfs"
    squashfs.write_bytes(b"filesystem")
    artifact = tmp_path / "InkEcho.AppImage"
    artifact.write_bytes(b"known good")
    create = tempfile.NamedTemporaryFile

    def fail_checksum(**kwargs):
        if kwargs.get("mode") == "w":
            raise OSError("disk full")
        return create(**kwargs)

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", fail_checksum)
    with pytest.raises(OSError, match="disk full"):
        publisher(runtime, squashfs, artifact)
    assert artifact.read_bytes() == b"known good"
    assert not list(tmp_path.glob(".*"))
