"""Rotating diagnostics accepting fixed event/error identifiers only."""

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from inkecho.core import Failure, State
from inkecho.performance import validate_snapshot
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
        "display_unavailable",
        "unsupported_target",
        "mapping_changed",
        "permission_required",
        "permission_denied",
        "portal_unavailable",
        "session_closed",
        "input_capability_unknown",
        "input_cancelled",
        "input_cleanup_failed",
        "partial_input_failed",
        "unsupported_compositor",
        "keys_held",
        "caps_lock",
        "cleanup_pending",
        "unsupported_layout",
        "fcitx_unavailable",
        "fcitx_authorization_failed",
        "fcitx_permission_denied",
        "fcitx_untrusted_owner",
        "fcitx_owner_changed",
        "fcitx_composition_guard_unavailable",
        "fcitx_composition_active",
        "fcitx_linefeed_protocol_unavailable",
        "fcitx_unsupported_text",
        "fcitx_no_target",
        "fcitx_ambiguous_target",
        "fcitx_delivery_unknown",
        "fcitx_cancelled",
        "fcitx_expired",
        "ibus_unavailable",
        "ibus_upgrade_required",
        "ibus_authorization_failed",
        "ibus_permission_denied",
        "ibus_untrusted_owner",
        "ibus_delivery_unknown",
        "ibus_cancelled",
        "ibus_unsupported_text",
        "unsupported_text",
        "busy",
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

    def record_performance(self, snapshot: dict) -> None:
        safe = validate_snapshot(snapshot)
        self.logger.info("performance %s", json.dumps(safe, allow_nan=False))
        self.path.chmod(0o600)

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
