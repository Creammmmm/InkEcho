import importlib.util
import json
import time
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "native_wayland_probe",
    Path(__file__).resolve().parents[1]
    / "scripts/validation/native_wayland_keyboard_probe.py",
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.mark.parametrize(
    "changed",
    [
        {"allowed": False},
        {"native_confirmed": False},
        {"browser_pid": 999},
        {"browser_parent_pid": 999},
        {"sampled_at": 0},
    ],
)
def test_press_guard_rejects_foreign_stale_or_unfocused_state(
    tmp_path, monkeypatch, changed
):
    path = tmp_path / "guard.json"
    state = {
        "browser_pid": 12,
        "browser_parent_pid": 10,
        "allowed": True,
        "native_confirmed": True,
        "sampled_at": time.monotonic(),
    }
    monkeypatch.setattr(probe, "parent_pid", lambda _pid: 10)
    path.write_text(json.dumps(state))
    assert probe.guard_allowed(path, 12, 10)
    path.write_text(json.dumps({**state, **changed}))
    assert not probe.guard_allowed(path, 12, 10)


def test_source_validation_rejects_imported_package_from_another_root(
    tmp_path, monkeypatch
):
    import inkecho

    assert (
        Path(inkecho.__file__)
        .resolve()
        .is_relative_to(Path(__file__).resolve().parents[1] / "src")
    )
    monkeypatch.setattr(probe.sys, "path", list(probe.sys.path))
    (tmp_path / "inkecho").mkdir()
    (tmp_path / "inkecho" / "__init__.py").write_text("")
    with pytest.raises(RuntimeError, match="source mismatch"):
        probe.load_package(tmp_path)


@pytest.mark.parametrize("counts", [(26, 25), (25, 25), (27, 27), (0, 0)])
def test_exact_text_without_exact_balanced_events_does_not_pass(counts):
    report = {
        "fixed_sample_exact": True,
        "map_and_modifiers_restored": True,
        "press_attempts": len(probe.SAMPLE),
        "release_attempts": len(probe.SAMPLE),
    }
    assert probe.successful_report(report)
    report.update(press_attempts=counts[0], release_attempts=counts[1])
    assert not probe.successful_report(report)
