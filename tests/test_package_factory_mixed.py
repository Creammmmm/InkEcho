"""Pure package-scope rejection checks; no desktop or subprocess starts."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = (
    Path(__file__).resolve().parents[1] / "scripts/validation/package_factory_mixed.py"
)
SPEC = importlib.util.spec_from_file_location("package_factory_mixed", PATH)
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


@pytest.mark.parametrize(
    "hybrid,count,sources", [(False, 18, 44), (True, 18, 44), (True, 19, 43)]
)
def test_reject_incomplete_final_package_scope(monkeypatch, hybrid, count, sources):
    origins = {f"module{i}": {} for i in range(count - int(hybrid))}
    if hybrid:
        origins["inkecho.platform.hybrid_keyboard"] = {}
    monkeypatch.setattr(PROBE, "selected_artifact", lambda *args: {"sha256": "fixed"})
    monkeypatch.setattr(
        PROBE,
        "audit_package",
        lambda *args: {
            "origins": origins,
            "inventory": {"application_files_match_source": sources},
        },
    )
    args = SimpleNamespace(
        artifact="candidate",
        expected_sha="fixed",
        package_root="package",
        frozen_source_root="frozen",
        expected_version="a15",
    )
    with pytest.raises(ValueError, match="final_hybrid_package_scope_required"):
        PROBE.audit_selected_package(args)


def test_artifact_rejection_precedes_package_import(monkeypatch):
    def reject(*args):
        raise ValueError("artifact_sha_mismatch")

    monkeypatch.setattr(PROBE, "selected_artifact", reject)
    monkeypatch.setattr(
        PROBE,
        "audit_package",
        lambda *args: pytest.fail("imported package before artifact check"),
    )
    with pytest.raises(ValueError, match="artifact_sha_mismatch"):
        PROBE.audit_selected_package(
            SimpleNamespace(artifact="wrong", expected_sha="fixed")
        )


def test_actual_factory_import_and_construct_without_desktop_io():
    # Match the import used inside one_run, without connecting or sending keys.
    import ast

    from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
    from inkecho.platform.wayland_keyboard import keyboard_for_desktop

    tree = ast.parse(PATH.read_text())
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert any(
        node.module == "inkecho.platform.wayland_keyboard"
        and any(alias.name == "keyboard_for_desktop" for alias in node.names)
        for node in imports
    )
    instance = keyboard_for_desktop(
        {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}
    )
    assert isinstance(instance, HybridKeyboardInput)
    assert instance.native._process is None
    assert instance.x11._driver is None
