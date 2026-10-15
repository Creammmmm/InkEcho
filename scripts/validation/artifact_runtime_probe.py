"""Audit actual package module origins before a frozen owned-target probe."""

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path

from performance_package_probe import audit_appdir


def audit_origins(package_root: Path) -> dict:
    appdir = package_root.parent
    if not Path(sys.executable).resolve().is_relative_to(appdir / "usr"):
        raise RuntimeError("selected_package_interpreter_required")
    audit = audit_appdir(appdir)
    inventory = json.loads(
        (appdir / "usr/share/doc/inkecho/inventory.json").read_text()
    )
    sys.path.insert(0, str(package_root))
    names = [
        "inkecho",
        "inkecho.app",
        "inkecho.audio",
        "inkecho.providers",
        "inkecho.realtime",
        "inkecho.polish_stream",
        "inkecho.streaming_output",
        "inkecho.ui.providers",
        "inkecho.runtime",
        "inkecho.platform.keyboard",
    ]
    origins = {}
    for name in names + ["websockets"]:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve(strict=True)
        if not path.is_relative_to(package_root):
            raise RuntimeError("runtime_module_escaped_selected_package")
        with path.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if inventory["files"][str(path.relative_to(appdir))] != checksum:
            raise RuntimeError("runtime_module_hash_mismatch")
        origins[name] = {"path": str(path), "sha256": checksum}
    version = importlib.import_module("inkecho").__version__
    if version != inventory["application"]:
        raise RuntimeError("runtime_version_mismatch")
    return {
        "runtime_kind": "package",
        "version": version,
        "application_modules_verified": len(names),
        "origins": origins,
        "package_inventory": audit,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--origins-output", type=Path, required=True)
    parser.add_argument(
        "--tool",
        choices=[
            "keyboard_latency_probe",
            "performance_package_probe",
            "artifact_streaming_cursor_probe",
        ],
        required=True,
    )
    args, remaining = parser.parse_known_args()
    package_root = args.package_root.resolve(strict=True)
    if remaining and remaining[0] == "--":
        remaining = remaining[1:]
    metadata = audit_origins(package_root)
    args.origins_output.write_text(json.dumps(metadata, indent=2) + "\n")
    tool = importlib.import_module(args.tool)
    if args.tool != "keyboard_latency_probe":
        remaining = ["--package-root", str(package_root), *remaining]
    sys.argv = [str(tool.__file__), *remaining]
    tool.main()


if __name__ == "__main__":
    main()
