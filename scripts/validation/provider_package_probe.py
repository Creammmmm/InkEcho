"""Run frozen local protocol tests with the selected package's own interpreter."""

import argparse
import hashlib
import importlib
import json
import os
import re
import sys
from pathlib import Path

SELECTED = (
    "tests/test_http_asr.py",
    "tests/test_step_realtime.py",
    "tests/test_dashscope_realtime.py",
    "tests/test_signed_asr.py",
    "tests/test_polish_protocols.py",
)
FRAMEWORK = {"pytest", "_pytest", "pluggy", "iniconfig", "packaging", "pygments"}
RUNTIME = {
    "httpx",
    "httpcore",
    "anyio",
    "sniffio",
    "certifi",
    "websockets",
    "PySide6",
    "shiboken6",
    "idna",
    "h11",
    "socksio",
}


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_manifest(path: Path, digest: str) -> dict:
    if checksum(path) != digest:
        raise ValueError("diagnostic_manifest_sha_mismatch")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("diagnostic_manifest_shape")
    return value


def verify_files(root: Path, expected: dict, *, exact: bool) -> None:
    if not isinstance(expected, dict) or not expected:
        raise ValueError("diagnostic_file_manifest_empty")
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("diagnostic_symlink_forbidden")
    if exact:
        actual = {
            str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()
        }
        if actual != set(expected):
            raise ValueError("diagnostic_file_set_mismatch")
    for name, digest in expected.items():
        path = root / name
        if (
            path.is_symlink()
            or not path.resolve().is_relative_to(root.resolve())
            or checksum(path) != digest
        ):
            raise ValueError("diagnostic_file_hash_mismatch")
        if path.suffix in {".pth", ".pyc", ".so"}:
            raise ValueError("diagnostic_framework_executable_extension")


def verify_framework(root: Path, expected: dict) -> None:
    for name in expected:
        top = Path(name).parts[0]
        if top not in FRAMEWORK and not re.fullmatch(
            r"(?:pytest|pluggy|iniconfig|packaging|pygments)-[A-Za-z0-9_.+-]+\.dist-info",
            top,
        ):
            raise ValueError("diagnostic_framework_namespace_forbidden")
    verify_files(root, expected, exact=True)


def dependency_origins(
    package_root: Path,
    framework_root: Path,
    inventory: dict,
    framework: dict,
    modules: dict | None = None,
) -> dict:
    result = {}
    appdir = package_root.parent
    for name, module in tuple((sys.modules if modules is None else modules).items()):
        prefix = name.partition(".")[0]
        if prefix not in FRAMEWORK | RUNTIME | {"inkecho"}:
            continue
        if not getattr(module, "__file__", None):
            paths = [
                Path(value).resolve(strict=True)
                for value in getattr(module, "__path__", ())
            ]
            allowed = framework_root if prefix in FRAMEWORK else package_root
            if not paths or any(not path.is_relative_to(allowed) for path in paths):
                raise ValueError("dependency_namespace_outside_scope")
            result[name] = {"namespace_paths": list(map(str, paths))}
            continue
        path = Path(module.__file__).resolve(strict=True)
        digest = checksum(path)
        if path.is_relative_to(package_root):
            if inventory.get(str(path.relative_to(appdir))) != digest:
                raise ValueError("runtime_dependency_inventory_mismatch")
        elif prefix in FRAMEWORK and path.is_relative_to(framework_root):
            if framework.get(str(path.relative_to(framework_root))) != digest:
                raise ValueError("framework_import_not_pinned")
        else:
            raise ValueError("runtime_dependency_outside_package")
        result[name] = {"path": str(path), "sha256": digest}
    return result


def run(args) -> dict:
    """No source overlays, user plugins, downloads, microphone or real credentials."""
    package = args.package_root.resolve(strict=True)
    frozen = args.frozen_source_root.resolve(strict=True).parent
    framework = args.framework_root.resolve(strict=True)
    if not sys.flags.isolated:
        raise ValueError("isolated_package_python_required")
    framework_manifest = verified_manifest(args.framework_manifest, args.framework_sha)
    tests_manifest = verified_manifest(args.tests_manifest, args.tests_sha)
    verify_framework(framework, framework_manifest["files"])
    verify_files(frozen, tests_manifest["files"], exact=False)
    nodeids = tests_manifest["nodeids"]
    if (
        not isinstance(nodeids, list)
        or not nodeids
        or any(not isinstance(node, str) or "::" not in node for node in nodeids)
    ):
        raise ValueError("selected_test_manifest_invalid")
    if len(nodeids) != len(set(nodeids)) or any(
        node.partition("::")[0] not in SELECTED for node in nodeids
    ):
        raise ValueError("selected_test_manifest_invalid")
    if tests_manifest["selected_files"] != list(SELECTED):
        raise ValueError("selected_test_files_mismatch")
    args.work_dir.mkdir(mode=0o700, exist_ok=False)
    configuration = args.work_dir / "pytest.ini"
    configuration.write_text("[pytest]\naddopts = -q -x -p no:cacheprovider\n")
    sys.dont_write_bytecode = True
    for name in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "PYTEST_DEBUG"):
        os.environ.pop(name, None)
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    appdir = package.parent
    sys.path[:] = [
        str(package),
        str(framework),
        str(frozen / "tests"),
        str(frozen / "scripts/validation"),
    ] + [
        path for path in sys.path if Path(path).resolve().is_relative_to(appdir / "usr")
    ]
    if any(
        Path(path).resolve().is_relative_to(args.frozen_source_root.resolve())
        for path in sys.path
    ):
        raise ValueError("application_source_overlay_forbidden")
    scope = importlib.import_module("artifact_scope")
    artifact = scope.selected_artifact(args.artifact, args.expected_sha)
    before = scope.audit_package(
        package, args.frozen_source_root, args.expected_version
    )
    inventory = json.loads(
        (appdir / "usr/share/doc/inkecho/inventory.json").read_text()
    )["files"]
    import pytest

    class ProtocolResults:
        collected = None
        passed = 0
        skipped = 0
        failed = 0

        def pytest_collection_modifyitems(self, items):
            self.collected = [item.nodeid for item in items]
            if self.collected != nodeids:
                raise pytest.UsageError("selected_test_collection_mismatch")

        def pytest_runtest_logreport(self, report):
            if report.failed:
                self.failed += 1
            elif report.skipped:
                self.skipped += 1
            elif report.when == "call" and report.passed:
                self.passed += 1

    results = ProtocolResults()
    code = int(
        pytest.main(
            [
                "-c",
                str(configuration),
                "--rootdir",
                str(frozen),
                "--confcutdir",
                str(frozen / "tests"),
                "--basetemp",
                str(args.work_dir / "temporary"),
                *[
                    str(frozen / node.partition("::")[0])
                    + "::"
                    + node.partition("::")[2]
                    for node in nodeids
                ],
            ],
            plugins=[results],
        )
    )
    after = scope.audit_package(package, args.frozen_source_root, args.expected_version)
    origins = dependency_origins(
        package, framework, inventory, framework_manifest["files"]
    )
    verify_framework(framework, framework_manifest["files"])
    verify_files(frozen, tests_manifest["files"], exact=False)
    return {
        "passed": code == 0
        and results.collected == nodeids
        and results.passed == len(nodeids)
        and not results.skipped
        and not results.failed,
        "artifact": artifact,
        "interpreter": str(Path(sys.executable).resolve()),
        "pytest_exit_code": code,
        "selected_nodeids": results.collected,
        "counts": {
            "passed": results.passed,
            "skipped": results.skipped,
            "failed": results.failed,
        },
        "before_audit": before,
        "after_audit": after,
        "dependency_origins": origins,
        "framework_manifest_sha256": args.framework_sha,
        "tests_manifest_sha256": args.tests_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "artifact",
        "package-root",
        "frozen-source-root",
        "framework-root",
        "framework-manifest",
        "tests-manifest",
        "work-dir",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("expected-sha", "expected-version", "framework-sha", "tests-sha"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("fresh_output_required")
    result = run(args)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
