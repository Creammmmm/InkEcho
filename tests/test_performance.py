"""Timing schema tests use a controlled clock, not desktop/cloud measurements."""

import json

import pytest

from inkecho.performance import EVENTS, TaskTiming


def test_relative_milestones_and_derived_durations():
    now = [100.0]
    timing = TaskTiming(clock=lambda: now[0])
    for event, seconds in (
        ("recording_started", 0),
        ("recording_stop_requested", 2),
        ("recording_stopped", 2.01),
        ("asr_started", 2.02),
        ("asr_completed", 2.22),
        ("polishing_started", 2.23),
        ("polishing_first_segment", 2.25),
        ("polishing_completed", 2.3),
        ("first_character_sent", 2.35),
        ("output_completed", 3.0),
    ):
        now[0] = 100 + seconds
        timing.mark(event)
    result = timing.finish("succeeded")
    assert result["durations_ms"] == {
        "stop_to_audio_ready_ms": 10.0,
        "asr_ms": 200.0,
        "polishing_to_first_segment_ms": 20.0,
        "polishing_ms": 70.0,
        "stop_to_first_character_ms": 350.0,
        "audio_ready_to_first_character_ms": 340.0,
        "output_ms": 650.0,
        "stop_to_output_completed_ms": 1000.0,
        "stop_to_task_finished_ms": 1000.0,
    }
    assert set(result["events_ms"]) == set(EVENTS)
    assert result["events_ms"]["recording_started"] == 0


@pytest.mark.parametrize("outcome", ["succeeded", "failed", "cancelled"])
def test_missing_milestones_are_not_estimated_and_closed_results_are_immutable(outcome):
    now = [1.0]
    timing = TaskTiming(clock=lambda: now[0])
    timing.mark("recording_started")
    now[0] = 2.0
    timing.mark("asr_started")
    now[0] = 3.0
    timing.mark("asr_started")
    snapshot = timing.finish(outcome)
    assert snapshot["events_ms"]["asr_started"] == 1000
    assert snapshot["events_ms"]["first_character_sent"] is None
    assert all(value is None for value in snapshot["durations_ms"].values())
    now[0] = 5.0
    timing.mark("first_character_sent")
    assert timing.finish("failed") == snapshot
    snapshot["events_ms"]["asr_started"] = -1
    assert timing.snapshot()["events_ms"]["asr_started"] == 1000


def test_only_fixed_metadata_is_accepted():
    timing = TaskTiming()
    with pytest.raises(ValueError, match="milestone"):
        timing.mark("private transcript or api key")
    with pytest.raises(ValueError, match="outcome"):
        timing.finish("private exception")
    serialized = json.dumps(timing.finish("cancelled"))
    assert "private" not in serialized
    assert "api key" not in serialized


def test_realtime_asr_can_begin_before_stop_and_overlap_recording():
    now = [1.0]
    timing = TaskTiming(clock=lambda: now[0])
    timing.mark("recording_started")
    timing.mark("asr_started")
    now[0] = 4.0
    timing.mark("recording_stop_requested")
    now[0] = 4.1
    timing.mark("asr_completed")
    now[0] = 4.2
    timing.mark("first_character_sent")
    timing.mark("output_completed")
    result = timing.finish("succeeded")
    assert result["durations_ms"]["asr_ms"] == 3100
    assert result["durations_ms"]["stop_to_first_character_ms"] == 200


def test_transport_timestamp_excludes_acknowledgement_delay():
    now = [100.0]
    timing = TaskTiming(clock=lambda: now[0])
    timing.mark("recording_stop_requested")
    now[0] = 101.1
    timing.mark("first_character_sent", at=101.0)
    result = timing.finish("succeeded")
    assert result["durations_ms"]["stop_to_first_character_ms"] == 1000


@pytest.mark.parametrize("at", [99, 102, True, float("nan"), float("inf"), "private"])
def test_invalid_transport_timestamp_is_rejected(at):
    timing = TaskTiming(clock=lambda: 100.0)
    with pytest.raises(ValueError, match="observation time"):
        timing.mark("first_character_sent", at=at)
    assert timing.snapshot()["events_ms"]["first_character_sent"] is None


def test_unconfirmed_performance_snapshot_is_valid():
    from inkecho.performance import TaskTiming, validate_snapshot

    snapshot = TaskTiming().finish("unconfirmed")
    assert validate_snapshot(snapshot)["outcome"] == "unconfirmed"
