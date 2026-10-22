"""Freeze the generic audio pipeline tools and source without starting a desktop.

The printed manifest digest must be reviewed before native_pipeline_runner is
started. Pulse tools are supplied explicitly; this script never installs them.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (
    "audio_pipeline_keyboard.py",
    "audio_pipeline_native_guard.py",
    "native_pipeline_runner.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--pulse-bin", type=Path, required=True)
    args = parser.parse_args()
    stage = args.stage.resolve()
    pulse = args.pulse_bin.resolve(strict=True)
    assert not stage.exists()
    binaries = {
        name: (pulse / name).resolve(strict=True) for name in ("pactl", "pacat")
    }
    assert all(path.is_file() for path in binaries.values())
    stage.mkdir(mode=0o700)
    for name in TOOLS:
        shutil.copyfile(Path(__file__).parent / name, stage / name)
    files = subprocess.check_output(
        ["git", "ls-files", "src", "scripts/validation", "assets/licenses"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    # Include these newly prepared tools even before their first commit.
    files = sorted(set(files) | {f"scripts/validation/{name}" for name in TOOLS})
    for name in files:
        path = ROOT / name
        assert path.is_file() and not path.is_symlink()
        target = stage / "frozen" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    (stage / "pulse-bin").mkdir()
    for name, path in binaries.items():
        shutil.copyfile(path, stage / "pulse-bin" / name)
        (stage / "pulse-bin" / name).chmod(0o700)
    shutil.copyfile(binaries["pacat"], stage / "pulse-bin/paplay")
    (stage / "pulse-bin/paplay").chmod(0o700)
    manifest = {
        "provenance": {
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_scope": "working source freeze, not an AppImage acceptance",
            "pulse_binary_sha256": {
                name: digest(path) for name, path in binaries.items()
            },
        },
        "files": {
            str(path.relative_to(stage)): digest(path)
            for path in sorted(stage.rglob("*"))
            if path.is_file()
        },
    }
    (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {"stage": str(stage), "manifest_sha256": digest(stage / "manifest.json")},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
