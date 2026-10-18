"""Run frozen local protocol tests with the selected package's own interpreter."""

import argparse
import base64
import binascii
import hashlib
import importlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

SELECTED = (
    "tests/test_http_asr.py",
    "tests/test_step_realtime.py",
    "tests/test_dashscope_realtime.py",
    "tests/test_signed_asr.py",
    "tests/test_polish_protocols.py",
)
FRAMEWORK = {"pytest", "_pytest", "pluggy", "iniconfig", "packaging", "pygments", "py"}
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
        if top not in (FRAMEWORK - {"py"}) | {"py.py"} and not re.fullmatch(
            r"(?:pytest|pluggy|iniconfig|packaging|pygments)-[A-Za-z0-9_.+-]+\.dist-info",
            top,
        ):
            raise ValueError("diagnostic_framework_namespace_forbidden")
    verify_files(root, expected, exact=True)


def _qt_embedded_origin(name, module, modules, package_root, inventory):
    """Authenticate only the observed Qt support aliases carried in libshiboken."""
    if name == "PySide6.support.feature":
        original = "shibokensupport.feature"
    elif name == "PySide6.support.signature" or name.startswith(
        "PySide6.support.signature."
    ):
        original = name.replace("PySide6.support", "shibokensupport", 1)
    else:
        raise ValueError("qt_embedded_alias_mismatch")
    try:
        loader = module.__loader__
        cls = type(loader)
        if (
            cls.__module__ != "signature_bootstrap"
            or cls.__name__ != "EmbeddableZipImporter"
            or modules.get(original) is not module
            or module.__name__ != original
        ):
            raise ValueError
        namespace = cls.__init__.__globals__
        if namespace.get("EmbeddableZipImporter") is not cls:
            raise ValueError
        logical = loader._mod2path[original]
        if (
            logical != module.__file__
            or not logical.startswith("shibokensupport/")
            or ".." in Path(logical).parts
        ):
            raise ValueError
        vector = namespace["zipstring_sequence"]
        if (
            not isinstance(vector, list)
            or not 0 < len(vector) <= 128
            or any(
                not isinstance(value, str) or not 0 < len(value) <= 8192
                for value in vector
            )
        ):
            raise ValueError
        encoded = "".join(vector).encode("ascii")
        archive = base64.b64decode(b"".join(encoded.split()), validate=True)
        if (
            len(archive) > 1048576
            or not isinstance(loader.zfile, zipfile.ZipFile)
            or loader.zfile.fp.getvalue() != archive
        ):
            raise ValueError
        info = loader.zfile.getinfo(logical)
        if info.file_size > 1048576:
            raise ValueError
        member = loader.zfile.read(logical)
        carriers = list((package_root / "shiboken6").glob("libshiboken6.abi3.so*"))
        if len(carriers) != 1:
            raise ValueError
        carrier = carriers[0].resolve(strict=True)
        if not carrier.is_relative_to(package_root):
            raise ValueError
        digest = checksum(carrier)
        if inventory.get(str(carrier.relative_to(package_root.parent))) != digest:
            raise ValueError
        data = carrier.read_bytes()
        if not all(value.encode("ascii") in data for value in vector):
            raise ValueError
        return {
            "logical_origin": logical,
            "embedded_member_sha256": hashlib.sha256(member).hexdigest(),
            "embedded_archive_sha256": hashlib.sha256(archive).hexdigest(),
            "carrier": str(carrier),
            "carrier_sha256": digest,
        }
    except (
        AttributeError,
        KeyError,
        ValueError,
        TypeError,
        OSError,
        binascii.Error,
        zipfile.BadZipFile,
    ):
        raise ValueError("qt_embedded_origin_unverified") from None


def dependency_origins(
    package_root: Path,
    framework_root: Path,
    inventory: dict,
    framework: dict,
    modules: dict | None = None,
) -> dict:
    result = {}
    appdir = package_root.parent
    loaded = sys.modules if modules is None else modules
    for name, module in tuple(loaded.items()):
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
        if prefix == "PySide6" and str(module.__file__).startswith("shibokensupport/"):
            result[name] = _qt_embedded_origin(
                name, module, loaded, package_root, inventory
            )
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
                *(["--collect-only"] if args.collect_only else []),
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
        and results.passed == (0 if args.collect_only else len(nodeids))
        and not results.skipped
        and not results.failed,
        "execution_kind": "collection_only" if args.collect_only else "protocol_tests",
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
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Validate isolated collection without executing protocol tests.",
    )
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
