"""Exercise the standalone synthetic comparison without real input or network."""

import json
import os
import subprocess
import sys
from pathlib import Path


def test_comparison_labels_synthetic_evidence_and_uses_same_delays():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/validation/performance_baseline.py"),
            "--compare-streaming",
            "--samples",
            "1",
            "--characters",
            "2",
            "--asr-ms",
            "0",
            "--polish-ms",
            "50",
            "--char-ms",
            "0",
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    payload = json.loads(result.stdout)
    assert payload["evidence_kind"] == "synthetic_headless"
    assert payload["desktop_validated"] is False
    assert payload["cloud_validated"] is False
    assert payload["same_generation_and_per_character_delays"] is True
    synchronous = payload["synchronous"]["samples"][0]["events_ms"]
    streaming = payload["streaming"]["samples"][0]["events_ms"]
    assert synchronous["first_character_sent"] >= synchronous["polishing_completed"]
    assert streaming["first_character_sent"] < streaming["polishing_completed"]
