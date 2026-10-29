"""Build-time pin and inventory tests; these never load a native plugin."""

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bundle():
    spec = importlib.util.spec_from_file_location(
        "fcitx_bundle_test", ROOT / "scripts/packaging/bundle.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def candidate_root(tmp_path):
    shutil.copytree(ROOT / "native/fcitx5", tmp_path / "native/fcitx5")
    shutil.copytree(
        ROOT / "assets/native/fcitx5/x86_64", tmp_path / "assets/native/fcitx5/x86_64"
    )
    return tmp_path


def test_verified_candidate_is_included_in_inventory(bundle, candidate_root, tmp_path):
    candidate = bundle.verified_fcitx5_candidate(candidate_root)
    appdir = tmp_path / "appdir"
    (appdir / "usr/share/doc/inkecho").mkdir(parents=True)
    metadata = bundle.install_fcitx5_candidate(appdir, candidate)
    bundle.write_inventory(appdir, {"fcitx5_candidate": metadata})
    inventory = json.loads(
        (appdir / "usr/share/doc/inkecho/inventory.json").read_text()
    )
    key = "usr/share/inkecho/fcitx5/x86_64/candidate/libinkecho.so"
    assert inventory["files"][key] == bundle.FCITX5_PLUGIN_SHA256
    assert inventory["fcitx5_candidate"]["status"] == "uninstalled-candidate"
    assert inventory["fcitx5_candidate"]["fcitx5_core_version"] == "5.1.7"
    assert inventory["fcitx5_candidate"]["focus_protocol_version"] == 3
    assert inventory["fcitx5_candidate"]["composition_guard_protocol_version"] == 3
    assert inventory["fcitx5_candidate"]["legacy_begin_supported"] is True
    assert inventory["fcitx5_candidate"]["neighbor_batch_protocol_version"] == 4


@pytest.mark.parametrize(
    "file",
    [
        "native/fcitx5/inkecho.cpp",
        "native/fcitx5/utf8_scalar.h",
        "native/fcitx5/focused_context.h",
        "assets/native/fcitx5/x86_64/libinkecho.so",
        "assets/native/fcitx5/x86_64/inkecho.conf",
    ],
)
def test_changed_source_or_candidate_fails_closed(bundle, candidate_root, file):
    path = candidate_root / file
    path.write_bytes(path.read_bytes() + b"modified")
    with pytest.raises(SystemExit, match="candidate or pinned source mismatch"):
        bundle.verified_fcitx5_candidate(candidate_root)


def test_missing_or_symlinked_candidate_fails_closed(bundle, candidate_root, tmp_path):
    plugin = candidate_root / "assets/native/fcitx5/x86_64/libinkecho.so"
    original = tmp_path / "original.so"
    plugin.rename(original)
    with pytest.raises(SystemExit, match="candidate or pinned source mismatch"):
        bundle.verified_fcitx5_candidate(candidate_root)
    plugin.symlink_to(original)
    with pytest.raises(SystemExit, match="candidate or pinned source mismatch"):
        bundle.verified_fcitx5_candidate(candidate_root)


def test_changed_candidate_after_preflight_is_not_packaged(bundle, tmp_path):
    with pytest.raises(ValueError, match="candidate changed after verification"):
        bundle.install_fcitx5_candidate(tmp_path / "appdir", (b"fake", b"fake"))
    assert not (tmp_path / "appdir").exists()


@pytest.mark.parametrize(
    ("os_version", "fcitx_version"), [("24.04", "5.1.7"), ("26.04", "5.1.19")]
)
def test_squashfs_extracted_candidate_is_safe_to_stage(
    bundle, candidate_root, tmp_path, os_version, fcitx_version
):
    from inkecho.platform.fcitx5_staging import stage

    if not shutil.which("mksquashfs") or not shutil.which("unsquashfs"):
        pytest.skip("squashfs-tools required")
    appdir = tmp_path / "appdir"
    previous = os.umask(0o002)
    try:
        bundle.install_fcitx5_candidate(
            appdir, bundle.verified_fcitx5_candidate(candidate_root)
        )
    finally:
        os.umask(previous)
    image = tmp_path / "payload.squashfs"
    extracted = tmp_path / "extracted"
    subprocess.run(
        [
            "mksquashfs",
            str(appdir),
            str(image),
            "-noappend",
            "-all-root",
            "-no-progress",
            "-processors",
            "1",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    subprocess.run(
        ["unsquashfs", "-d", str(extracted), str(image)],
        check=True,
        capture_output=True,
        timeout=30,
    )
    root = extracted / "usr/share/inkecho/fcitx5/x86_64"
    for path in (
        root,
        root / "candidate",
        root / "manifest.json",
        root / "candidate/inkecho.conf",
        root / "candidate/libinkecho.so",
    ):
        assert path.stat().st_mode & 0o022 == 0
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    assert (
        stage(
            root,
            data,
            os_id="ubuntu",
            os_version=os_version,
            architecture="x86_64",
            fcitx_version=fcitx_version,
        )
        == bundle.FCITX5_PLUGIN_SHA256
    )
