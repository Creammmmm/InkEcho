"""Pure metrics tests with fixture-scoped imports and no desktop/service calls."""

import importlib.util
import math
import sys
from pathlib import Path

import pytest


@pytest.fixture
def benchmark(monkeypatch):
    names = [
        "artifact_scope",
        "native_acceptance",
        "native_guard",
        "natural_owned_browser",
        "x11_acceptance",
    ]
    previous = {name: sys.modules.get(name) for name in names}
    with monkeypatch.context() as scoped:
        scoped.setattr(sys, "path", list(sys.path))
        scoped.setattr(sys, "dont_write_bytecode", True)
        for name in names:
            sys.modules.pop(name, None)
        path = (
            Path(__file__).resolve().parents[1]
            / "scripts/validation/a14_input_speed.py"
        )
        # Pure metrics controls also run in checkouts without ignored lab data.
        scoped.syspath_prepend(str(path.parent))
        spec = importlib.util.spec_from_file_location("a14_input_speed_test", path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            yield module
        finally:
            for name, value in previous.items():
                if value is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = value


def test_sample_is_100_mixed_bmp_codepoints(benchmark):
    sample = benchmark.SAMPLE
    assert len(sample) == 100
    assert all(32 <= ord(character) <= 0xFFFF for character in sample)
    assert 35 <= sum("\u4e00" <= character <= "\u9fff" for character in sample) <= 60
    assert len(set(sample)) >= 35


def test_steady_rate_uses_n_minus_one_intervals(benchmark):
    result = benchmark.metrics(0, [1, 2, 3], 1, 3.1, 3.2, 3.05)
    assert result["steady_press_events_per_second"] == 1
    assert result["dispatch_throughput_chars_per_second"] == 3 / 3.2
    assert result["start_to_dom_exact_observed_ms"] == 3050
    assert (
        result["start_to_dom_exact_observed_ms"]
        < result["start_to_output_scope_return_ms"]
    )


@pytest.mark.parametrize(
    "presses,callback,dom",
    [
        ([1, math.nan, 3], 1, 4),
        ([1, 3, 2], 1, 4),
        ([1, 2, 3], 1.1, 4),
        ([1, 2, 3], 1, 2.5),
    ],
)
def test_invalid_timing_never_becomes_a_success_metric(
    benchmark, presses, callback, dom
):
    with pytest.raises(ValueError):
        benchmark.metrics(0, presses, callback, 3.1, 3.2, dom)
