"""Copy only the approved public Chrome software directory to the new VM lab."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from ubuntu24_vm import LAB

SOURCE = Path("/opt/google/chrome")
DESTINATION = LAB / "input/software/chrome"
EXPECTED_VERSION = "Google Chrome 154.0.8037.97"
INSTALL = r"""
import hashlib, json, pathlib, platform, subprocess, sys

release = platform.freedesktop_os_release()
if release.get("ID") != "ubuntu" or release.get("VERSION_ID") != "24.04":
    raise RuntimeError("actual_ubuntu24_guest_required")
if subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() != "kvm":
    raise RuntimeError("actual_kvm_guest_required")
target = pathlib.Path("/opt/inkecho-test-chrome")
if target.exists() or pathlib.Path("/usr/local/bin/google-chrome").exists():
    raise RuntimeError("test_software_destination_exists")
subprocess.run(
    ["sudo", "cp", "-a", "/mnt/input/software/chrome", str(target)], check=True
)
subprocess.run(["sudo", "chown", "-R", "root:root", str(target)], check=True)
subprocess.run(["sudo", "chmod", "4755", str(target / "chrome-sandbox")], check=True)
wrapper = '#!/bin/sh\nexec /opt/inkecho-test-chrome/chrome "$@"\n'
subprocess.run(
    ["sudo", "tee", "/usr/local/bin/google-chrome"],
    input=wrapper,
    text=True,
    capture_output=True,
    check=True,
)
subprocess.run(["sudo", "chmod", "755", "/usr/local/bin/google-chrome"], check=True)
version = subprocess.check_output(
    ["/usr/local/bin/google-chrome", "--version"], text=True
).strip()
dependencies = subprocess.run(
    ["ldd", str(target / "chrome")], capture_output=True, text=True, check=True
).stdout
sandbox = (target / "chrome-sandbox").stat()
with (target / "chrome").open("rb") as stream:
    binary_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
if binary_sha256 != sys.argv[1]:
    raise RuntimeError("installed_binary_does_not_match_software_manifest")
report = {
    "version": version,
    "source": "offline copy of public software only; no browser profiles",
    "missing_dependencies": [
        line.strip() for line in dependencies.splitlines() if "not found" in line
    ],
    "sandbox_uid": sandbox.st_uid,
    "sandbox_mode": oct(sandbox.st_mode & 0o7777),
    "binary_sha256": binary_sha256,
    "binary_matches_source_manifest": True,
    "no_sandbox_flag": False,
}
pathlib.Path("/mnt/output/chrome-installed.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(json.dumps(report))
"""


def main():
    version = subprocess.check_output([str(SOURCE / "chrome"), "--version"], text=True)
    if version.strip() != EXPECTED_VERSION:
        raise RuntimeError("Unexpected approved public Chrome software version")
    if DESTINATION.exists():
        raise RuntimeError("Do not overwrite the recorded software copy")
    if any(path.is_symlink() for path in SOURCE.rglob("*")):
        raise RuntimeError("Unexpected software symlink requires review")
    temporary = DESTINATION.with_name("chrome-next")
    temporary.parent.mkdir(mode=0o700, exist_ok=True)
    shutil.copytree(SOURCE, temporary)
    files = {}
    for path in sorted(temporary.rglob("*")):
        if path.is_file():
            path.chmod(path.stat().st_mode & 0o777)
            with path.open("rb") as stream:
                files[str(path.relative_to(temporary))] = hashlib.file_digest(
                    stream, "sha256"
                ).hexdigest()
    temporary.replace(DESTINATION)
    (LAB / "chrome-software-manifest.json").write_text(
        json.dumps(
            {
                "source_directory": str(SOURCE),
                "version": version.strip(),
                "files": files,
                "user_profiles_copied": False,
            },
            indent=2,
        )
        + "\n"
    )
    subprocess.run(
        [
            str(Path(".venv/bin/python")),
            "scripts/validation/ubuntu24_vm.py",
            "ssh",
            "--",
            "python3",
            "-c",
            INSTALL,
            files["chrome"],
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
