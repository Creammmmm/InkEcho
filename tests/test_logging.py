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


def test_performance_logs_only_fixed_metadata_and_keeps_private_permissions(tmp_path):
    from inkecho.performance import TaskTiming

    timing = TaskTiming(clock=lambda: 100.0)
    timing.mark("recording_started")
    snapshot = timing.finish("cancelled")
    log = DiagnosticLog(tmp_path)
    try:
        log.record_performance(snapshot)
        assert 'INFO performance {"schema_version": 1' in log.recent()
        assert '"first_character_sent": null' in log.recent()
        assert log.path.stat().st_mode & 0o777 == 0o600
    finally:
        log.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("transcript", "private text"),
        ("outcome", "private text"),
        ("schema_version", True),
        ("events_ms", {"private text": 1}),
        ("durations_ms", {"private text": 1}),
    ],
)
def test_private_or_unknown_performance_metadata_is_rejected(tmp_path, field, value):
    from inkecho.performance import TaskTiming

    snapshot = TaskTiming().finish("cancelled")
    snapshot[field] = value
    log = DiagnosticLog(tmp_path)
    try:
        with pytest.raises(ValueError, match="Invalid performance metadata"):
            log.record_performance(snapshot)
        assert "private" not in log.recent()
    finally:
        log.close()


@pytest.mark.parametrize(
    "value", ["private text", True, -1, float("nan"), float("inf")]
)
def test_performance_rejects_non_numeric_or_unsafe_values(tmp_path, value):
    from inkecho.performance import TaskTiming

    snapshot = TaskTiming().finish("failed")
    snapshot["events_ms"]["asr_started"] = value
    log = DiagnosticLog(tmp_path)
    try:
        with pytest.raises(ValueError, match="Invalid performance metadata"):
            log.record_performance(snapshot)
        assert log.recent() == ""
    finally:
        log.close()
