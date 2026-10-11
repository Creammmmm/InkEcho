"""Build a real type-2 AppImage using a standalone Python and pinned runtime."""

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "build"
APPDIR = BUILD / "InkEcho.AppDir"
RUNTIME = BUILD / "tools/runtime-x86_64"
RUNTIME_URL = (
    "https://github.com/AppImage/type2-runtime/releases/download/"
    "continuous/runtime-x86_64"
)
# Official release asset digest, inspected 2026-10-12. Fail closed on upstream change.
RUNTIME_SHA256 = "156f4bdbde9c52d01814600013e0a273f0118dc2de98975f3c8c63427ec79074"


def main() -> None:
    if platform.machine() != "x86_64" or sys.platform != "linux":
        raise SystemExit("This build recipe currently supports Linux x86_64 only.")
    if not shutil.which("mksquashfs"):
        raise SystemExit("Install squashfs-tools before building.")
    python_home = Path(sys.base_prefix).resolve()
    if not (python_home / "BUILD").exists():
        raise SystemExit("Use an uv-managed standalone Python to build the AppImage.")
    RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    if not RUNTIME.exists():
        urllib.request.urlretrieve(RUNTIME_URL, RUNTIME)
    if hashlib.sha256(RUNTIME.read_bytes()).hexdigest() != RUNTIME_SHA256:
        raise SystemExit("AppImage runtime checksum mismatch; review upstream release.")
    if APPDIR.exists():
        shutil.rmtree(APPDIR)
    shutil.copytree(python_home, APPDIR / "usr", symlinks=True)
    packages = APPDIR / "packages"
    packages.mkdir()
    installed = Path(sysconfig.get_paths()["purelib"])
    for pattern in (
        "PySide6",
        "shiboken6",
        "pyside6*.dist-info",
        "shiboken6*.dist-info",
    ):
        for path in installed.glob(pattern):
            shutil.copytree(path, packages / path.name)
    shutil.copytree(ROOT / "src/inkecho", packages / "inkecho")
    for path in APPDIR.rglob("__pycache__"):
        shutil.rmtree(path)
    launcher = APPDIR / "AppRun"
    launcher.write_text(
        "#!/bin/sh\nset -eu\n"
        'APPDIR="${APPDIR:-$(dirname "$(readlink -f "$0")")}"\n'
        "export APPDIR\n"
        'export PYTHONHOME="$APPDIR/usr"\n'
        'export PYTHONPATH="$APPDIR/packages"\n'
        "export PYTHONNOUSERSITE=1\n"
        'export QT_PLUGIN_PATH="$APPDIR/packages/PySide6/Qt/plugins"\n'
        'exec "$APPDIR/usr/bin/python3" -m inkecho.probe "$@"\n'
    )
    launcher.chmod(0o755)
    (APPDIR / "inkecho.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=InkEcho Feasibility Probe\n"
        "Exec=AppRun\nIcon=inkecho\nCategories=Utility;Audio;\nTerminal=false\n"
    )
    (APPDIR / "inkecho.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">'
        '<rect width="128" height="128" rx="28" fill="#245B52"/>'
        '<path d="M36 54v20m14-34v48m14-60v72m14-60v48m14-34v20" '
        'stroke="#fff" stroke-width="7" stroke-linecap="round"/></svg>\n'
    )
    (APPDIR / ".DirIcon").symlink_to("inkecho.svg")
    squashfs = BUILD / "inkecho.squashfs"
    subprocess.run(
        [
            "mksquashfs",
            str(APPDIR),
            str(squashfs),
            "-noappend",
            "-all-root",
            "-comp",
            "zstd",
            "-no-progress",
            "-processors",
            "2",
            "-mkfs-time",
            os.getenv("SOURCE_DATE_EPOCH", "0"),
        ],
        check=True,
    )
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    artifact = dist / "InkEcho-0.1.0-stage0-x86_64.AppImage"
    with artifact.open("wb") as output:
        output.write(RUNTIME.read_bytes())
        with squashfs.open("rb") as filesystem:
            shutil.copyfileobj(filesystem, output)
    artifact.chmod(0o755)
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    artifact.with_suffix(".AppImage.sha256").write_text(f"{digest}  {artifact.name}\n")
    print(f"Built {artifact} ({artifact.stat().st_size // 1048576} MiB)")


if __name__ == "__main__":
    main()
