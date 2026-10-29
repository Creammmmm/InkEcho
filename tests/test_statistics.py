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


def test_unrepresentable_statistics_value_is_rejected_without_overwriting(tmp_path):
    path = tmp_path / "stats.json"
    values = statistics.empty_day()
    values["characters"] = 10**400
    body = json.dumps({"schema_version": 1, "days": {"2026-10-28": values}})
    path.write_text(body)
    with pytest.raises(StatisticsError):
        Statistics(path).today()
    assert path.read_text() == body


def test_unrepresentable_new_statistics_value_is_rejected(tmp_path):
    path = tmp_path / "stats.json"
    with pytest.raises(ValueError):
        Statistics(path).record("succeeded", characters=10**400)
    assert not path.exists()


@pytest.mark.parametrize(
    "values",
    [{"audio_seconds": float("nan")}, {"characters": -1}, {"transcription_calls": 0.5}],
)
def test_invalid_numbers_do_not_write(tmp_path, values):
    stats = Statistics(tmp_path / "stats.json")
    with pytest.raises(ValueError):
        stats.record("succeeded", **values)
    assert not stats.path.exists()


def test_unconfirmed_preserves_legacy_statistics_schema(tmp_path):
    import json

    from inkecho.statistics import Statistics, empty_day

    path = tmp_path / "statistics.json"
    stats = Statistics(path)
    stats.record("unconfirmed", characters=3)
    day = stats.today()
    assert set(day) == set(empty_day())
    assert day["succeeded"] == 1  # fully attempted, not confirmed delivery
    assert day["failed"] == 0
    assert day["characters"] == 3
    raw = json.loads(path.read_text())
    assert raw["schema_version"] == 1
    assert set(next(iter(raw["days"].values()))) == set(empty_day())
