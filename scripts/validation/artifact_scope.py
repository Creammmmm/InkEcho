"""New-package audit for frozen acceptance snapshots; imports no UI eagerly."""

import hashlib
import importlib
import json
import re
import sys
from pathlib import Path

PROVIDER_MODULES = (
    "inkecho.provider_catalog",
    "inkecho.provider_credentials",
    "inkecho.http_asr",
    "inkecho.asr_streaming",
    "inkecho.asr_wire",
    "inkecho.step_realtime",
    "inkecho.dashscope_realtime",
    "inkecho.xfyun_realtime",
    "inkecho.tencent_realtime",
    "inkecho.volc_realtime",
    "inkecho.polish_protocols",
)


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
    *PROVIDER_MODULES,
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


def application_sources(
    package_root: Path, source_root: Path, inventory: dict, appdir: Path
) -> dict[str, str]:
    """Reject missing/extra application files and bind every byte to frozen source."""

    def files(root):
        result = {}
        for path in root.rglob("*"):
            if "__pycache__" in path.parts:
                continue
            if path.is_symlink():
                raise ValueError("application_source_symlink")
            if path.is_file():
                result[str(path.relative_to(root))] = path
        return result

    expected, actual = files(source_root / "inkecho"), files(package_root / "inkecho")
    if not expected or set(expected) != set(actual):
        raise ValueError("application_source_set_mismatch")
    result = {}
    for name, path in actual.items():
        digest = checksum(path)
        if inventory.get(str(path.relative_to(appdir))) != digest:
            raise ValueError("module_inventory_mismatch")
        if checksum(expected[name]) != digest:
            raise ValueError("application_source_hash_mismatch")
        result["inkecho/" + name] = digest
    return result


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
    sources = application_sources(package_root, source, inventory["files"], appdir)
    if audit.get("application_files_match_source") != len(sources):
        raise ValueError("application_source_count_mismatch")
    sys.path.insert(0, str(package_root))
    origins = {}
    modules = list(MODULES)
    hybrid = "inkecho.platform.hybrid_keyboard"
    if (package_root / "inkecho/platform/hybrid_keyboard.py").is_file():
        if hybrid not in modules:
            modules.append(hybrid)
    for name in modules:
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
        "application_source_files": sources,
        "frozen_source_root": str(source),
        "production_behavior_modified": False,
    }
