"""Build an uninstalled, ABI-labelled Fcitx5 addon candidate on this machine.

No installation, Fcitx configuration, process restart, or network is performed.
"""

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "native/fcitx5"


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def run(args):
    subprocess.run(args, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="new candidate name (letters, digits, hyphen)")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,63}", args.name):
        parser.error("invalid candidate name")
    if shutil.which("cmake") is None:
        parser.error("CMake is required; no system packages were installed")
    build_root = ROOT / "build"
    if build_root.is_symlink():
        parser.error("build directory must not be a symlink")
    base = build_root / "fcitx5-candidates"
    base.mkdir(parents=True, exist_ok=True)
    if base.is_symlink() or not base.resolve().is_relative_to(build_root.resolve()):
        parser.error("candidate directory must remain in the project build directory")
    candidate = base / args.name
    candidate.mkdir(mode=0o700)
    build = candidate / "build"
    run(["cmake", "-S", str(SOURCE), "-B", str(build)])
    run(["cmake", "--build", str(build)])
    library = build / "libinkecho.so"
    metadata = build / "inkecho.conf"
    if (
        not library.is_file()
        or library.is_symlink()
        or not metadata.is_file()
        or metadata.is_symlink()
    ):
        raise RuntimeError("expected Fcitx candidate output missing")
    core = next(
        (
            line.partition(":")[2]
            for line in metadata.read_text().splitlines()
            if line.startswith("0=core:")
        ),
        "",
    )
    if not core or "@" in core:
        raise RuntimeError("missing Fcitx core ABI version")
    outputs = candidate / "candidate"
    outputs.mkdir(mode=0o700)
    for source in (library, metadata):
        shutil.copyfile(source, outputs / source.name)
        (outputs / source.name).chmod(0o600)
    release = platform.freedesktop_os_release()
    manifest = {
        "status": "uninstalled-candidate",
        "architecture": platform.machine(),
        "os_id": release.get("ID", "unknown"),
        "os_version": release.get("VERSION_ID", "unknown"),
        "fcitx5_core_version": core,
        "files_sha256": {item.name: digest(item) for item in sorted(outputs.iterdir())},
        "source_sha256": {
            item.name: digest(item)
            for item in sorted(SOURCE.iterdir())
            if item.is_file()
        },
    }
    (candidate / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (candidate / "manifest.json").chmod(0o600)
    print(f"Uninstalled candidate: {candidate}")


if __name__ == "__main__":
    main()
