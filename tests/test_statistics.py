import json
from datetime import date as real_date

import pytest

from inkecho import statistics
from inkecho.providers import Usage
from inkecho.statistics import Statistics, StatisticsError


def test_numeric_daily_totals_persist_without_content(tmp_path):
    path = tmp_path / "stats.json"
    stats = Statistics(path)
    stats.record(
        "succeeded",
        audio_seconds=2.5,
        characters=len("中🙂e\u0301"),
        transcription_calls=1,
        transcription_seconds=0.4,
        polishing_calls=1,
        polishing_seconds=0.5,
        usage=Usage(2, 3, 5),
    )
    stats.record("failed", audio_seconds=1, transcription_calls=1)
    stats.record("cancelled")
    today = Statistics(path).today()
    assert today["recordings"] == 3
    assert today["succeeded"] == today["failed"] == today["cancelled"] == 1
    assert today["characters"] == 4 and today["audio_seconds"] == 3.5
    assert today["transcription_calls"] == 2 and today["total_tokens"] == 5
    assert "中" not in path.read_text() and "text" not in path.read_text()


def test_unknown_token_usage_never_becomes_fake_zero(tmp_path):
    stats = Statistics(tmp_path / "stats.json")
    stats.record("succeeded", polishing_calls=1)
    stats.record("succeeded", polishing_calls=1, usage=Usage(1, 2, 3))
    assert stats.today()["input_tokens"] is None
    assert (
        stats.today()["output_tokens"] is None and stats.today()["total_tokens"] is None
    )


def test_local_calendar_day_rollover(tmp_path, monkeypatch):
    class LocalDate(real_date):
        current = real_date(2026, 10, 12)

        @classmethod
        def today(cls):
            return cls.current

    monkeypatch.setattr(statistics, "date", LocalDate)
    stats = Statistics(tmp_path / "stats.json")
    stats.record("succeeded", characters=3)
    LocalDate.current = real_date(2026, 10, 13)
    assert stats.today()["recordings"] == 0
    stats.record("failed")
    assert len(json.loads(stats.path.read_text())["days"]) == 2


@pytest.mark.parametrize("body", [b"broken", b"[]", b'{"schema_version":2,"days":{}}'])
def test_corrupt_data_preserved_until_explicit_clear(tmp_path, body):
    path = tmp_path / "stats.json"
    path.write_bytes(body)
    stats = Statistics(path)
    with pytest.raises(StatisticsError):
        stats.record("failed")
    assert path.read_bytes() == body
    stats.clear()
    assert stats.today()["recordings"] == 0


@pytest.mark.parametrize(
    "values",
    [{"audio_seconds": float("nan")}, {"characters": -1}, {"transcription_calls": 0.5}],
)
def test_invalid_numbers_do_not_write(tmp_path, values):
    stats = Statistics(tmp_path / "stats.json")
    with pytest.raises(ValueError):
        stats.record("succeeded", **values)
    assert not stats.path.exists()
