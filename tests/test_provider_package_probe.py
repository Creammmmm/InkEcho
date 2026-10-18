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


def test_pytest_owned_py_shim_and_alias_files_have_individual_pins(tmp_path):
    framework = tmp_path / "framework"
    shim = framework / "py.py"
    alias = framework / "_pytest/_py/path.py"
    alias.parent.mkdir(parents=True)
    shim.write_text("# pytest-owned compatibility shim\n")
    alias.write_text("# pytest-owned alias target\n")
    files = {
        str(path.relative_to(framework)): PROBE.checksum(path) for path in (shim, alias)
    }
    PROBE.verify_framework(framework, files)
    modules = {
        "py": SimpleNamespace(__file__=str(shim)),
        "py.path": SimpleNamespace(__file__=str(alias)),
    }
    origins = PROBE.dependency_origins(
        tmp_path / "packages", framework, {}, files, modules
    )
    assert set(origins) == {"py", "py.path"}
    alias.write_text("changed")
    with pytest.raises(ValueError, match="framework_import_not_pinned"):
        PROBE.dependency_origins(tmp_path / "packages", framework, {}, files, modules)


def test_allowing_py_shim_does_not_allow_a_separate_py_package(tmp_path):
    framework = tmp_path / "framework"
    path = framework / "py/__init__.py"
    path.parent.mkdir(parents=True)
    path.write_text("# not the distribution-owned shim\n")
    with pytest.raises(ValueError, match="diagnostic_framework_namespace_forbidden"):
        PROBE.verify_framework(framework, {"py/__init__.py": PROBE.checksum(path)})


@pytest.fixture
def embedded_qt(tmp_path):
    import base64
    import io
    import zipfile

    package = tmp_path / "appdir/packages"
    carrier = package / "shiboken6/libshiboken6.abi3.so.6.12"
    carrier.parent.mkdir(parents=True)
    logical = "shibokensupport/signature/errorhandler.py"
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w") as archive:
        archive.writestr(logical, "# synthetic embedded Qt support\n")
    data = memory.getvalue()
    encoded = base64.b64encode(data).decode()
    vector = [encoded[n : n + 64] + "\n" for n in range(0, len(encoded), 64)]
    namespace = {"__name__": "signature_bootstrap", "zipstring_sequence": vector}
    exec(
        "class EmbeddableZipImporter:\n"
        "    def __init__(self, archive, mapping):\n"
        "        self.zfile = archive\n"
        "        self._mod2path = mapping\n",
        namespace,
    )
    loader = namespace["EmbeddableZipImporter"](
        zipfile.ZipFile(io.BytesIO(data)),
        {"shibokensupport.signature.errorhandler": logical},
    )
    module = SimpleNamespace(
        __name__="shibokensupport.signature.errorhandler",
        __file__=logical,
        __loader__=loader,
    )
    modules = {
        "shibokensupport.signature.errorhandler": module,
        "PySide6.support.signature.errorhandler": module,
    }
    carrier.write_bytes(
        b"synthetic carrier\0" + b"\0".join(value.encode() for value in vector)
    )
    inventory = {str(carrier.relative_to(package.parent)): PROBE.checksum(carrier)}
    yield package, carrier, loader, module, modules, inventory
    loader.zfile.close()


def test_exact_qt_embedded_source_and_carrier_are_reported(embedded_qt, tmp_path):
    package, _carrier, _loader, _module, modules, inventory = embedded_qt
    result = PROBE.dependency_origins(
        package, tmp_path / "framework", inventory, {}, modules
    )
    item = result["PySide6.support.signature.errorhandler"]
    assert item["logical_origin"] == "shibokensupport/signature/errorhandler.py"
    assert (
        len(item["embedded_member_sha256"])
        == len(item["embedded_archive_sha256"])
        == 64
    )
    assert item["carrier_sha256"] in inventory.values()


@pytest.mark.parametrize(
    "change",
    [
        "alias",
        "loader",
        "logical",
        "vector",
        "carrier_hash",
        "carrier_payload",
        "namespace",
    ],
)
def test_unverified_qt_virtual_modules_are_not_skipped(embedded_qt, tmp_path, change):
    package, carrier, loader, module, modules, inventory = embedded_qt
    if change == "alias":
        modules["shibokensupport.signature.errorhandler"] = SimpleNamespace()
    elif change == "loader":
        module.__loader__ = SimpleNamespace()
    elif change == "logical":
        module.__file__ = "shibokensupport/other.py"
    elif change == "vector":
        type(loader).__init__.__globals__["zipstring_sequence"] = ["not base64"]
    elif change == "carrier_hash":
        carrier.write_bytes(b"changed carrier")
    elif change == "carrier_payload":
        carrier.write_bytes(b"different but inventory updated")
        inventory[str(carrier.relative_to(package.parent))] = PROBE.checksum(carrier)
    else:
        modules["PySide6.other"] = modules.pop("PySide6.support.signature.errorhandler")
    with pytest.raises(
        ValueError, match="qt_embedded_(origin_unverified|alias_mismatch)"
    ):
        PROBE.dependency_origins(
            package, tmp_path / "framework", inventory, {}, modules
        )
