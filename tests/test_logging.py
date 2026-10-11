import pytest

from inkecho.logging import DiagnosticLog


def test_only_safe_codes_and_levels_are_written(tmp_path):
    log = DiagnosticLog(tmp_path)
    try:
        log.record("startup")
        log.record("error", "authentication")
        assert "INFO startup" in log.recent()
        assert "ERROR error authentication" in log.recent()
        with pytest.raises(ValueError):
            log.record("error", "sk-test-secret")
        with pytest.raises(ValueError):
            log.record("private transcript")
        assert "secret" not in log.recent() and "transcript" not in log.recent()
    finally:
        log.close()


def test_rotation_bounded_and_clear_allows_new_events(tmp_path):
    log = DiagnosticLog(tmp_path)
    try:
        log.handler.maxBytes = 100
        for _ in range(20):
            log.record("startup")
        assert len(list(tmp_path.glob("inkecho.log*"))) <= 3
        (tmp_path / "keep.txt").write_text("user file")
        log.clear()
        assert log.recent() == "" and not (tmp_path / "inkecho.log.1").exists()
        log.record("shutdown")
        assert "shutdown" in log.recent()
        assert (tmp_path / "keep.txt").read_text() == "user file"
        assert log.path.stat().st_mode & 0o777 == 0o600
    finally:
        log.close()


def test_symlink_log_is_rejected(tmp_path):
    (tmp_path / "inkecho.log").symlink_to(tmp_path / "unrelated")
    with pytest.raises(ValueError):
        DiagnosticLog(tmp_path)
