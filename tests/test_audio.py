"""Recorder unit checks; the explicit opt-in test uses a real microphone."""

import io
import os
import wave
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtMultimedia import QtAudio

from inkecho import audio


@pytest.fixture(scope="module")
def app():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def recorder(app):
    recorder = audio.Recorder()
    yield recorder
    recorder.cancel()


def test_wav_is_mono_16bit_and_preserves_samples():
    pcm = b"\x00\x00\xff\x7f\x00\x80"
    with wave.open(io.BytesIO(audio.wav_bytes(pcm, 16000)), "rb") as result:
        assert (
            result.getnchannels(),
            result.getsampwidth(),
            result.getframerate(),
        ) == (
            1,
            2,
            16000,
        )
        assert result.readframes(3) == pcm


@pytest.mark.parametrize("pcm", [b"", b"\x01"])
def test_wav_rejects_empty_or_partial_samples(pcm):
    with pytest.raises(ValueError):
        audio.wav_bytes(pcm, 16000)


def fake_source(recorder, data=b"\x01\x00", error=QtAudio.Error.NoError):
    state = SimpleNamespace(stopped=False, deleted=False)
    recorder.source = SimpleNamespace(
        stop=lambda: setattr(state, "stopped", True),
        deleteLater=lambda: setattr(state, "deleted", True),
        error=lambda: error,
    )
    recorder.stream = SimpleNamespace(readAll=lambda: data)
    recorder.max_bytes = 64000
    return state


def test_stop_returns_wav_and_cleans_memory(recorder):
    state = fake_source(recorder)
    output = recorder.stop()
    assert output.startswith(b"RIFF")
    assert state.stopped and state.deleted
    assert recorder.source is None and not recorder.pcm
    assert recorder.stop() is None


def test_empty_recording_and_device_error_fail(recorder):
    errors = []
    recorder.failed.connect(errors.append)
    fake_source(recorder, b"")
    assert recorder.stop() is None
    fake_source(recorder, error=QtAudio.Error.IOError)
    assert recorder.stop() is None
    assert errors == ["empty_recording", "microphone_interrupted"]


def test_cancel_discards_samples_without_result(recorder):
    results = []
    recorder.finished.connect(lambda *result: results.append(result))
    state = fake_source(recorder)
    recorder.pcm.extend(b"\0\0")
    recorder.cancel()
    assert state.stopped and state.deleted and not recorder.pcm
    assert results == []


def test_memory_limit_and_late_timeout_fail_once(recorder):
    errors = []
    recorder.failed.connect(errors.append)
    state = fake_source(recorder, b"\0" * 6)
    recorder.max_bytes = 4
    recorder._read()
    recorder._fail("recording_timed_out")
    assert errors == ["recording_timed_out"]
    assert state.stopped and not recorder.pcm


def test_duplicate_start_is_rejected(recorder):
    fake_source(recorder)
    assert not recorder.start()


def test_missing_device_is_explicit(recorder, monkeypatch):
    errors = []
    recorder.failed.connect(errors.append)
    monkeypatch.setattr(
        audio, "QMediaDevices", SimpleNamespace(defaultAudioInput=lambda: None)
    )
    assert not recorder.start()
    assert errors == ["microphone_unavailable"]


def test_synchronous_start_failure_is_reported_once(recorder, monkeypatch):
    errors = []
    recorder.failed.connect(errors.append)
    device = SimpleNamespace(isNull=lambda: False, isFormatSupported=lambda _: True)
    monkeypatch.setattr(
        audio, "QMediaDevices", SimpleNamespace(defaultAudioInput=lambda: device)
    )
    state = SimpleNamespace(stopped=False)
    source = SimpleNamespace(
        start=lambda: None,
        error=lambda: QtAudio.Error.OpenError,
        stop=lambda: setattr(state, "stopped", True),
        deleteLater=lambda: None,
    )
    monkeypatch.setattr(audio, "QAudioSource", lambda *_: source)
    assert not recorder.start()
    assert recorder.source is None and state.stopped
    assert errors == ["microphone_start_failed"]


def test_unsupported_format_never_starts_source(recorder, monkeypatch):
    errors = []
    recorder.failed.connect(errors.append)
    device = SimpleNamespace(isNull=lambda: False, isFormatSupported=lambda _: False)
    monkeypatch.setattr(
        audio, "QMediaDevices", SimpleNamespace(defaultAudioInput=lambda: device)
    )
    assert not recorder.start()
    assert errors == ["audio_format_unsupported"] and recorder.source is None


@pytest.mark.skipif(
    os.getenv("INKECHO_TEST_MICROPHONE") != "1",
    reason="Requires real microphone access",
)
def test_live_repeated_same_process_capture(recorder):
    errors, durations = [], []
    recorder.failed.connect(errors.append)
    recorder.finished.connect(lambda _, duration: durations.append(duration))
    for _ in range(3):
        assert recorder.start(max_seconds=3)
        loop = QEventLoop()
        QTimer.singleShot(700, loop.quit)
        loop.exec()
        result = recorder.stop()
        assert result is not None
        with wave.open(io.BytesIO(result), "rb") as recorded:
            assert recorded.getframerate() == 16000
            assert recorded.getnchannels() == 1 and recorded.getnframes() > 0
        assert recorder.source is None and not recorder.pcm
    assert not errors and len(durations) == 3
    assert recorder.start(max_seconds=3)
    recorder.cancel()
    assert recorder.source is None and not recorder.pcm
    assert recorder.start(max_seconds=0.1)
    loop = QEventLoop()
    QTimer.singleShot(250, loop.quit)
    loop.exec()
    assert errors == ["recording_timed_out"]
    assert recorder.source is None and not recorder.pcm
    assert recorder.start(max_seconds=3)
    recorder.cancel()
    print(
        {
            "captures": 3,
            "sample_rate": 16000,
            "durations": durations,
            "saved": False,
            "cancel_restart": True,
            "timeout_restart": True,
        }
    )
