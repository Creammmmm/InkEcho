"""Rotating diagnostics accepting fixed event/error identifiers only."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from inkecho.core import Failure, State
from inkecho.providers import ERRORS
from inkecho.statistics import state_directory

EVENTS = {
    "startup",
    "shutdown",
    "error",
    "shortcut",
    "integration",
    "settings_saved",
} | set(State)
CODES = (
    set(ERRORS)
    | set(Failure)
    | {
        "",
        "microphone_unavailable",
        "audio_format_unsupported",
        "microphone_start_failed",
        "microphone_interrupted",
        "empty_recording",
        "recording_timed_out",
        "desktop_unavailable",
        "shortcut_unavailable",
        "credentials_unavailable",
        "configuration_invalid",
        "statistics_invalid",
        "integration_failed",
    }
)


class DiagnosticLog:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root if root is not None else state_directory() / "logs"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / "inkecho.log"
        if any(path.is_symlink() for path in self._files()):
            raise ValueError("Diagnostic paths must not be symbolic links.")
        self.logger = logging.Logger("inkecho-diagnostics")
        self.handler = RotatingFileHandler(
            self.path, maxBytes=128_000, backupCount=2, encoding="utf-8"
        )
        self.handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        self.logger.addHandler(self.handler)
        self.path.chmod(0o600)

    def _files(self) -> list[Path]:
        return [self.path] + [self.root / f"inkecho.log.{i}" for i in (1, 2)]

    def record(self, event: str, code: str = "") -> None:
        if event not in EVENTS or code not in CODES:
            raise ValueError("Diagnostics only accept known event and error codes.")
        self.logger.log(logging.ERROR if code else logging.INFO, "%s %s", event, code)
        self.path.chmod(0o600)

    def recent(self) -> str:
        self.handler.flush()
        with self.path.open("rb") as stream:
            stream.seek(max(0, self.path.stat().st_size - 32_000))
            return stream.read().decode("utf-8", errors="replace")

    def clear(self) -> None:
        self.handler.acquire()
        try:
            self.handler.close()
            for path in self._files():
                path.unlink(missing_ok=True)
            self.path.touch(mode=0o600)
        finally:
            self.handler.release()

    def close(self) -> None:
        self.handler.close()
