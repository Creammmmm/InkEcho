"""Actual production gates/handlers with controlled asynchronous boundaries."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_actual_owned_gate_deadline_owner_cancel_and_legacy_refusal():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is needed to execute the actual production JS gates")
    fixture = Path(__file__).with_name("fixtures") / "owned_bounded_gate.mjs"
    result = subprocess.run(
        [node, "--experimental-default-type=module", str(fixture)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
