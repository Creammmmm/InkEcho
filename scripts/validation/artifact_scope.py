"""New-package audit for frozen acceptance snapshots; imports no UI eagerly."""

import hashlib
import importlib
import json
import re
import sys
from pathlib import Path

MODULES = (
    "inkecho",
    "inkecho.app",
    "inkecho.audio",
    "inkecho.config",
    "inkecho.providers",
    "inkecho.provider_capability",
    "inkecho.realtime",
    "inkecho.polish_stream",
    "inkecho.streaming_output",
    "inkecho.ui.providers",
    "inkecho.runtime",
    "inkecho.security",
    "inkecho.platform.keyboard",
    "inkecho.platform.eis",
    "inkecho.platform.wayland_keyboard",
    "inkecho.platform.wayland_keymap",
    "inkecho.platform.wayland_worker",
    "websockets",
)


def checksum(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def selected_artifact(artifact: Path, expected_sha: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        raise ValueError("expected_artifact_sha_required")
    artifact = artifact.resolve(strict=True)
    if checksum(artifact) != expected_sha:
        raise ValueError("artifact_sha_mismatch")
    return {
        "path": str(artifact),
        "sha256": expected_sha,
        "bytes": artifact.stat().st_size,
    }


def audit_package(
    package_root: Path, frozen_source_root: Path, expected_version: str
) -> dict:
    """Use generic inventory audit only beside its actual frozen source tree."""
    import performance_package_probe as inventory_probe

    package_root = package_root.resolve(strict=True)
    source = frozen_source_root.resolve(strict=True)
    appdir = package_root.parent
    if source != (inventory_probe.ROOT / "src").resolve(strict=True):
        raise ValueError("frozen_source_snapshot_required")
    if not Path(sys.executable).resolve().is_relative_to(appdir / "usr"):
        raise ValueError("selected_package_interpreter_required")
    inventory = json.loads(
        (appdir / "usr/share/doc/inkecho/inventory.json").read_text()
    )
    if inventory["application"] != expected_version:
        raise ValueError("selected_version_mismatch")
    audit = inventory_probe.audit_appdir(appdir)
    sys.path.insert(0, str(package_root))
    origins = {}
    for name in MODULES:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve(strict=True)
        if not path.is_relative_to(package_root):
            raise ValueError("module_origin_outside_package")
        actual = checksum(path)
        if inventory["files"].get(str(path.relative_to(appdir))) != actual:
            raise ValueError("module_inventory_mismatch")
        origins[name] = {"path": str(path), "sha256": actual}
    if importlib.import_module("inkecho").__version__ != expected_version:
        raise ValueError("runtime_version_mismatch")
    return {
        "runtime_kind": "package",
        "version": expected_version,
        "inventory": audit,
        "origins": origins,
        "frozen_source_root": str(source),
        "production_behavior_modified": False,
    }
