"""Pure controls for isolated diagnostic dependencies; no package execution."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = (
    Path(__file__).resolve().parents[1] / "scripts/validation/provider_package_probe.py"
)
SPEC = importlib.util.spec_from_file_location("provider_package_probe", PATH)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


def test_diagnostic_manifest_bytes_are_independently_pinned(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"files": {"pytest/__init__.py": "fixed"}}))
    digest = PROBE.checksum(path)
    assert PROBE.verified_manifest(path, digest)["files"]
    path.write_text("{}")
    with pytest.raises(ValueError, match="diagnostic_manifest_sha_mismatch"):
        PROBE.verified_manifest(path, digest)


@pytest.mark.parametrize(
    "change", ["extra", "missing", "tampered", "symlink", "namespace"]
)
def test_framework_files_are_exact_and_cannot_overlay_product(tmp_path, change):
    root = tmp_path / "framework"
    path = root / "pytest/__init__.py"
    path.parent.mkdir(parents=True)
    path.write_text("# synthetic framework\n")
    files = {"pytest/__init__.py": PROBE.checksum(path)}
    PROBE.verify_framework(root, files)
    if change == "extra":
        (root / "pytest/extra.py").write_text("extra")
    elif change == "missing":
        path.unlink()
    elif change == "tampered":
        path.write_text("changed")
    elif change == "symlink":
        (root / "linked").symlink_to(path.parent, target_is_directory=True)
    else:
        bad = root / "inkecho/__init__.py"
        bad.parent.mkdir()
        bad.write_text("# forbidden product overlay\n")
        files["inkecho/__init__.py"] = PROBE.checksum(bad)
    with pytest.raises(ValueError):
        PROBE.verify_framework(root, files)


@pytest.mark.parametrize(
    "module", ["httpx", "inkecho.providers", "inkecho.extra_future_module"]
)
def test_every_loaded_product_and_runtime_module_must_be_package_owned(
    tmp_path, module
):
    package = tmp_path / "appdir/packages"
    framework = tmp_path / "framework"
    package.mkdir(parents=True)
    framework.mkdir()
    outside = tmp_path / "source.py"
    outside.write_text("outside")
    with pytest.raises(ValueError, match="runtime_dependency_outside_package"):
        PROBE.dependency_origins(
            package, framework, {}, {}, {module: SimpleNamespace(__file__=str(outside))}
        )


def test_runtime_and_framework_origins_verify_independent_inventories(tmp_path):
    appdir = tmp_path / "appdir"
    package, framework = appdir / "packages", tmp_path / "framework"
    product = package / "inkecho/extra.py"
    product.parent.mkdir(parents=True)
    product.write_text("synthetic product")
    runner = framework / "pytest/__init__.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("synthetic runner")
    inventory = {str(product.relative_to(appdir)): PROBE.checksum(product)}
    files = {str(runner.relative_to(framework)): PROBE.checksum(runner)}
    modules = {
        "inkecho.extra": SimpleNamespace(__file__=str(product)),
        "pytest": SimpleNamespace(__file__=str(runner)),
    }
    origins = PROBE.dependency_origins(package, framework, inventory, files, modules)
    assert set(origins) == set(modules)
    product.write_text("modified")
    with pytest.raises(ValueError, match="runtime_dependency_inventory_mismatch"):
        PROBE.dependency_origins(package, framework, inventory, files, modules)


@pytest.mark.parametrize(
    "prefix", ["pytest.namespace", "inkecho.namespace", "httpx.namespace"]
)
def test_namespace_import_paths_are_checked_without_file_attribute(tmp_path, prefix):
    package, framework = tmp_path / "packages", tmp_path / "framework"
    package.mkdir()
    framework.mkdir()
    with pytest.raises(ValueError, match="dependency_namespace_outside_scope"):
        PROBE.dependency_origins(
            package,
            framework,
            {},
            {},
            {prefix: SimpleNamespace(__path__=[str(tmp_path)])},
        )
