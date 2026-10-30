"""Read-only exact private QA Chrome resource and owned executable audit."""

import hashlib
import os
import stat
from pathlib import Path

ROOT = Path("/opt/inkecho-qa-chrome")
MANIFEST_SHA = "01c5c6683bdd5e143b456a5d44b54e56e2b5d5249d3789f80b085a08b626eec4"
WRAPPER_SHA = "51c3c7ae61c640f573e15a33de080bc481693c6d04375259654d2e92a0621d76"
BINARY_SHA = "6c792041b07547a662e1b17974d1dc34a3db630379b45d9d89ddd7e3e68cc587"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def audit_program():
    import json

    root_state = ROOT.lstat()
    assert (
        stat.S_ISDIR(root_state.st_mode) and root_state.st_uid == root_state.st_gid == 0
    )
    assert stat.S_IMODE(root_state.st_mode) == 0o755
    assert ROOT.resolve(strict=True) == ROOT
    manifest = ROOT / "qa-resource-manifest.json"
    assert not manifest.is_symlink() and sha(manifest) == MANIFEST_SHA
    pins = json.loads(manifest.read_text())["files"]
    assert len(pins) == 255
    actual = set()
    for path in ROOT.rglob("*"):
        state = path.lstat()
        assert state.st_uid == state.st_gid == 0 and not stat.S_ISLNK(state.st_mode)
        if stat.S_ISDIR(state.st_mode):
            assert stat.S_IMODE(state.st_mode) == 0o755
        else:
            assert stat.S_ISREG(state.st_mode)
            actual.add(str(path.relative_to(ROOT)))
    assert actual == set(pins) | {
        "qa-bin/google-chrome",
        "qa-resource-manifest.json",
        "qa-install-receipt.json",
    }
    for name, pin in pins.items():
        path = ROOT / name
        assert path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"]
        expected = (
            0o4755
            if name == "chrome-sandbox"
            else 0o755
            if int(pin["mode"], 8) & 0o111
            else 0o644
        )
        assert stat.S_IMODE(path.stat().st_mode) == expected
    assert sha(ROOT / "qa-bin/google-chrome") == WRAPPER_SHA
    assert stat.S_IMODE((ROOT / "qa-bin/google-chrome").stat().st_mode) == 0o755
    assert stat.S_IMODE((ROOT / "qa-install-receipt.json").stat().st_mode) == 0o600
    assert stat.S_IMODE(manifest.stat().st_mode) == 0o644
    return {
        "root": str(ROOT),
        "program_files": 255,
        "payload_bytes": sum(pin["bytes"] for pin in pins.values()),
        "manifest_sha256": MANIFEST_SHA,
        "wrapper_sha256": WRAPPER_SHA,
        "binary_sha256": BINARY_SHA,
        "sandbox_sha256": pins["chrome-sandbox"]["sha256"],
        "sandbox_uid": 0,
        "sandbox_gid": 0,
        "sandbox_mode": "0o4755",
        "sandbox_runtime_acceptance": "not inferred from resource audit",
    }


def assert_owned_executable(pid):
    assert Path(f"/proc/{pid}/exe").resolve(strict=True) == ROOT / "chrome"
    assert os.stat(ROOT).st_uid == 0 and not os.stat(ROOT).st_mode & 0o022
