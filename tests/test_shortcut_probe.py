import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "shortcut_probe",
    Path(__file__).resolve().parents[1] / "scripts/feasibility/shortcut_probe.py",
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_matches_only_registered_key_and_modifiers():
    bindings = {"F13": (191, 0), "Ctrl+Alt+K": (96, 12)}
    assert probe.matching_shortcut(191, 0, bindings) == "F13"
    assert probe.matching_shortcut(96, 12, bindings) == "Ctrl+Alt+K"
    assert probe.matching_shortcut(191, 4, bindings) is None
    assert probe.matching_shortcut(96, 4, bindings) is None
    assert probe.matching_shortcut(192, 0, bindings) is None
