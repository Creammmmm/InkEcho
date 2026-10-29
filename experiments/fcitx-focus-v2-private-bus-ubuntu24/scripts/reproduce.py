"""Reproduce only inside a disposable Ubuntu24 VM with existing SDK; no install."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

source = Path(__file__).resolve().parents[1]
repo, deps = (Path(x).resolve(strict=True) for x in sys.argv[1:])
assert os.getuid() == 1000
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() in {"qemu", "kvm"}
assert "VERSION_ID=\"24.04\"" in Path("/etc/os-release").read_text()
root = Path("/tmp/inkecho-fcitx-v2")
assert not root.exists(), "fresh directory required; old data is never removed"
pins = json.loads((source / "raw/source-pins.json").read_text())
for name, digest in pins.items():
    if name.startswith("src/"):
        actual = repo / name
    elif name.startswith("deps/"):
        actual = deps / name.removeprefix("deps/")
    else:
        continue
    assert actual.is_file() and hashlib.sha256(actual.read_bytes()).hexdigest() == digest, name
root.mkdir(mode=0o700)
shutil.copytree(repo / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
(root / "deps").mkdir()
shutil.copytree(deps / "dbus_next", root / "deps/dbus_next", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
for name in ["product-native", "legacy-native", "test-control"]:
    shutil.copytree(source / "frozen" / name, root / name)
    subprocess.run(["cmake", "-S", str(root / name), "-B", str(root / (name + "-build"))], check=True)
    subprocess.run(["cmake", "--build", str(root / (name + "-build")), "-j2"], check=True)
shutil.copyfile(source / "scripts/run_protocol_measured.py.txt", root / "run_protocol-r3.py")
for variant in ["product-native", "legacy-native"]:
    subprocess.run(["dbus-run-session", "--", "/usr/bin/python3", str(root / "run_protocol-r3.py"), variant], check=True)
