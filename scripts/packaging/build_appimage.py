"""Build a real type-2 AppImage using a standalone Python and pinned runtime."""

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
from pathlib import Path

from bundle import collect_python, system_assets, trim_qt, write_inventory

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


def publish_appimage(runtime: Path, squashfs: Path, artifact: Path) -> str:
    """Publish a complete image without truncating an existing or mounted image."""
    temporary = None
    checksum_temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=artifact.parent, prefix=f".{artifact.name}.", delete=False
        ) as output:
            temporary = Path(output.name)
            for source in (runtime, squashfs):
                with source.open("rb") as stream:
                    shutil.copyfileobj(stream, output)
            output.flush()
            os.fsync(output.fileno())
        temporary.chmod(0o755)
        with temporary.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        with tempfile.NamedTemporaryFile(
            mode="w", dir=artifact.parent, prefix=".sha256.", delete=False
        ) as output:
            checksum_temporary = Path(output.name)
            output.write(f"{digest}  {artifact.name}\n")
            output.flush()
            os.fsync(output.fileno())
        # Atomic replacement keeps an old mounted inode intact, even on a rebuild.
        temporary.replace(artifact)
        checksum_temporary.replace(artifact.with_suffix(".AppImage.sha256"))
        return digest
    finally:
        for path in (temporary, checksum_temporary):
            if path is not None:
                path.unlink(missing_ok=True)


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
    # Runtime modules come from the locked environment, not standalone pip.
    for site_packages in (APPDIR / "usr/lib").glob("python*/site-packages"):
        shutil.rmtree(site_packages)
        site_packages.mkdir()
    for pip_entry in (APPDIR / "usr/bin").glob("pip*"):
        pip_entry.unlink()
    packages = APPDIR / "packages"
    packages.mkdir()
    versions = collect_python(packages)
    libraries = trim_qt(packages)
    assets = system_assets(ROOT, APPDIR)
    notices = APPDIR / "usr/share/doc/inkecho"
    shutil.copytree(ROOT / "assets/licenses", notices / "licenses")
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, notices / name)
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
        'export LD_LIBRARY_PATH="$APPDIR/usr/lib/inkecho'
        '${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
        'exec "$APPDIR/usr/bin/python3" -m inkecho "$@"\n'
    )
    launcher.chmod(0o755)
    (APPDIR / "inkecho.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=InkEcho\n"
        "Exec=AppRun\nIcon=inkecho\nCategories=AudioVideo;Audio;\nTerminal=false\n"
    )
    shutil.copy2(ROOT / "src/inkecho/assets/inkecho.svg", APPDIR / "inkecho.svg")
    (APPDIR / ".DirIcon").symlink_to("inkecho.svg")
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    write_inventory(
        APPDIR,
        {
            "application": version,
            "python": platform.python_version(),
            "python_distributions": versions,
            "qt_libraries": libraries,
            "system_assets": assets,
            "appimage_runtime_sha256": RUNTIME_SHA256,
        },
    )
    squashfs = BUILD / "inkecho.squashfs"
    subprocess.run(
        [
            "mksquashfs",
            str(APPDIR),
            str(squashfs),
            "-noappend",
            "-all-root",
            "-no-xattrs",
            "-comp",
            "zstd",
            "-no-progress",
            "-processors",
            "2",
            "-mkfs-time",
            os.getenv("SOURCE_DATE_EPOCH", "0"),
            "-all-time",
            os.getenv("SOURCE_DATE_EPOCH", "0"),
        ],
        check=True,
    )
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    artifact = dist / f"InkEcho-{version}-x86_64.AppImage"
    publish_appimage(RUNTIME, squashfs, artifact)
    print(f"Built {artifact} ({artifact.stat().st_size // 1048576} MiB)")


if __name__ == "__main__":
    main()
