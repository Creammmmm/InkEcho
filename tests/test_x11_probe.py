"""Focus and cancellation unit checks; these do not establish desktop support."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "x11_probe",
    Path(__file__).resolve().parents[1] / "scripts/feasibility/x11_probe.py",
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_injects_mixed_unicode_without_a_clipboard():
    received = []
    assert probe.inject("中文🌍\n", 7, lambda: 7, received.append, lambda: False) == 4
    assert "".join(received) == "中文🌍\n"


def test_cancelled_task_sends_nothing():
    received = []
    with pytest.raises(RuntimeError, match="Cancelled"):
        probe.inject("中文", 7, lambda: 7, received.append, lambda: True)
    assert received == []


def test_focus_change_stops_remaining_input():
    received = []
    with pytest.raises(RuntimeError, match="Focus changed"):
        probe.inject(
            "中文", 7, lambda: 8 if received else 7, received.append, lambda: False
        )
    assert received == ["中"]


def test_cancellation_stops_remaining_input():
    received = []
    with pytest.raises(RuntimeError, match="Cancelled"):
        probe.inject("中文", 7, lambda: 7, received.append, lambda: bool(received))
    assert received == ["中"]
