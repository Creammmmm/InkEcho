import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "overlay_probe",
    Path(__file__).resolve().parents[1] / "scripts/feasibility/overlay_probe.py",
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_focus_evidence_requires_valid_stable_target():
    assert probe.focus_preserved([42, 42, 42, 42])
    assert not probe.focus_preserved([42, 43, 42])
    assert not probe.focus_preserved([0, 0, 0])
    assert not probe.focus_preserved([1, 1, 1])
    assert not probe.focus_preserved([42])
