"""Audit a source snapshot before invoking the frozen local pipeline probe."""

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path


def audit_origins(source: Path, dependencies: Path, manifest: dict) -> dict:
    if not Path(sys.executable).resolve().is_relative_to(dependencies.parent / "usr"):
        raise RuntimeError("selected_dependency_interpreter_required")
    inventory = json.loads(
        (dependencies.parent / "usr/share/doc/inkecho/inventory.json").read_text()
    )
    sys.path.insert(0, str(source))
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
        with path.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if name == "websockets":
            if not path.is_relative_to(dependencies):
                raise RuntimeError("websocket_dependency_escaped_selected_package")
            relative = str(path.relative_to(dependencies.parent))
            if inventory["files"][relative] != checksum:
                raise RuntimeError("websocket_dependency_hash_mismatch")
        else:
            if not path.is_relative_to(source):
                raise RuntimeError("application_module_escaped_source_snapshot")
            relative = "src/" + str(path.relative_to(source))
            if manifest["source_files"][relative] != checksum:
                raise RuntimeError("application_module_hash_mismatch")
        origins[name] = {"path": str(path), "sha256": checksum}
    return {
        "runtime_kind": "source",
        "application_modules_verified": len(names),
        "source_root": str(source),
        "dependency_root": str(dependencies),
        "origins": origins,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--dependency-root", type=Path, required=True)
    parser.add_argument("--snapshot-manifest", type=Path, required=True)
    parser.add_argument("--origins-output", type=Path, required=True)
    args, remaining = parser.parse_known_args()
    source = args.source_root.resolve(strict=True)
    dependencies = args.dependency_root.resolve(strict=True)
    metadata = audit_origins(
        source, dependencies, json.loads(args.snapshot_manifest.read_text())
    )
    args.origins_output.write_text(json.dumps(metadata, indent=2) + "\n")
    import performance_package_probe

    sys.argv = [str(performance_package_probe.__file__), *remaining]
    performance_package_probe.main()


if __name__ == "__main__":
    main()
