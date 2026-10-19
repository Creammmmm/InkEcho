"""Local daily numeric aggregates; never store audio or transcript text."""

import json
import math
import os
from datetime import date, timedelta
from pathlib import Path

from inkecho.config import atomic_write
from inkecho.providers import Usage

COUNTS = (
    "recordings",
    "succeeded",
    "failed",
    "cancelled",
    "characters",
    "transcription_calls",
    "polishing_calls",
)
DURATIONS = ("audio_seconds", "transcription_seconds", "polishing_seconds")
TOKENS = ("input_tokens", "output_tokens", "total_tokens")


class StatisticsError(ValueError):
    """Statistics are invalid; explicit clearing can reset only usage data."""


def state_directory() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", ""))
    return (root if root.is_absolute() else Path.home() / ".local/state") / "inkecho"


def empty_day() -> dict:
    return dict.fromkeys(COUNTS + DURATIONS + TOKENS, 0)


class Statistics:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path if path is not None else state_directory() / "statistics.json"

    def _load(self) -> dict:
        if not self.path.exists():
            return {"schema_version": 1, "days": {}}
        try:
            raw = self.path.read_bytes()
            if len(raw) > 2_000_000:
                raise ValueError
            data = json.loads(raw)
            if data["schema_version"] != 1 or set(data) != {"schema_version", "days"}:
                raise ValueError
            if not isinstance(data["days"], dict):
                raise ValueError
            for day, values in data["days"].items():
                date.fromisoformat(day)
                if set(values) != set(empty_day()):
                    raise ValueError
                for name, value in values.items():
                    if name in TOKENS and value is None:
                        continue
                    if (
                        type(value) not in (int, float)
                        or not math.isfinite(value)
                        or value < 0
                    ):
                        raise ValueError
                    if name in COUNTS + TOKENS and type(value) is not int:
                        raise ValueError
            return data
        except (OSError, ValueError, TypeError, KeyError):
            raise StatisticsError(
                "Usage data is invalid; clear statistics to reset it."
            ) from None

    def recent(self, days: int = 7) -> list[tuple[str, dict]]:
        """Return zero-filled daily aggregates, oldest first, in local time."""
        if type(days) is not int or not 1 <= days <= 366:
            raise ValueError("Invalid statistics period.")
        values = self._load()["days"]
        today = date.today()
        return [
            (day.isoformat(), values.get(day.isoformat(), empty_day()).copy())
            for day in (
                today - timedelta(days=offset) for offset in reversed(range(days))
            )
        ]

    def today(self) -> dict:
        return self._load()["days"].get(date.today().isoformat(), empty_day()).copy()

    def record(
        self,
        outcome: str,
        *,
        audio_seconds: float = 0,
        characters: int = 0,
        transcription_calls: int = 0,
        transcription_seconds: float = 0,
        polishing_calls: int = 0,
        polishing_seconds: float = 0,
        usage: Usage | None = None,
    ) -> None:
        if outcome not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("Unknown task outcome.")
        additions = {
            "characters": characters,
            "transcription_calls": transcription_calls,
            "polishing_calls": polishing_calls,
            "audio_seconds": audio_seconds,
            "transcription_seconds": transcription_seconds,
            "polishing_seconds": polishing_seconds,
        }
        for name, value in additions.items():
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("Statistics require nonnegative finite numbers.")
            if name in COUNTS and type(value) is not int:
                raise ValueError("Statistics counts must be integers.")
        data = self._load()
        today = data["days"].setdefault(date.today().isoformat(), empty_day())
        today["recordings"] += 1
        today[outcome] += 1
        for name, value in additions.items():
            today[name] += value
        if polishing_calls:
            for name in TOKENS:
                count = getattr(usage, name) if usage else None
                if count is not None and (type(count) is not int or count < 0):
                    raise ValueError("Token counts must be nonnegative integers.")
                today[name] = (
                    None
                    if count is None or today[name] is None
                    else today[name] + count
                )
        atomic_write(self.path, json.dumps(data, allow_nan=False).encode())

    def clear(self) -> None:
        atomic_write(self.path, b'{"schema_version": 1, "days": {}}')
