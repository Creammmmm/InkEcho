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
        setBufferSize=lambda _: None,
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


def test_streaming_pcm_is_sample_aligned_and_stop_skips_wav_encoding(
    recorder, monkeypatch
):
    chunks, results = [], []
    recorder.pcm_ready.connect(chunks.append)
    recorder.finished.connect(lambda data, duration: results.append((data, duration)))
    recorder.streaming = True
    state = fake_source(recorder)
    pieces = iter((b"\x01", b"\x00\x02", b"\x00", b""))
    recorder.stream.readAll = lambda: next(pieces)

    def no_encoding(*_):
        pytest.fail("Realtime stop must not encode/upload a second WAV recording")

    monkeypatch.setattr(audio, "wav_bytes", no_encoding)
    for _ in range(3):
        recorder._read()
    assert chunks == [b"\x01\x00", b"\x02\x00"]
    assert not recorder.pcm and recorder._captured_bytes == 4
    assert not results
    assert recorder.stop() == b""
    assert results == [(b"", 4 / 32000)]
    assert state.stopped and not recorder.pcm and not recorder._stream_tail


def test_streaming_cancel_and_limit_emit_no_remaining_pcm(recorder):
    chunks, results = [], []
    recorder.pcm_ready.connect(chunks.append)
    recorder.finished.connect(lambda *_: results.append(True))
    recorder.streaming = True
    fake_source(recorder, b"\x01")
    recorder._read()
    recorder.cancel()
    assert not chunks and not results and not recorder._stream_tail
    fake_source(recorder, b"\0" * 6)
    recorder.max_bytes = 4
    recorder._read()
    assert not chunks and not results and not recorder.pcm


@pytest.mark.skipif(
    os.getenv("INKECHO_TEST_MICROPHONE") != "1",
    reason="Requires real microphone access",
)
def test_live_streaming_capture_emits_pcm_before_stop_without_whole_audio(recorder):
    sizes, durations, errors = [], [], []
    recorder.pcm_ready.connect(lambda data: sizes.append(len(data)))
    recorder.finished.connect(lambda _data, seconds: durations.append(seconds))
    recorder.failed.connect(errors.append)
    assert recorder.start(streaming=True, max_seconds=3)
    loop = QEventLoop()
    QTimer.singleShot(700, loop.quit)
    loop.exec()
    assert sizes and not durations
    assert all(size > 0 and size % 2 == 0 for size in sizes)
    assert not recorder.pcm and len(recorder._stream_tail) <= 1
    assert recorder.stop() == b""
    assert sum(sizes) == round(durations[0] * 32000)
    assert not errors and recorder._captured_bytes == 0
    assert not recorder.pcm and not recorder._stream_tail
    print({"pcm_chunks": len(sizes), "duration_seconds": durations[0], "saved": False})


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


def startup_source(monkeypatch, *, first=b"\x01\x00"):
    """Model PCM ready during start(), before a consumer can connect readyRead."""

    class Ready:
        callback = None

        def connect(self, callback):
            self.callback = callback

    pieces = [first]
    ready = Ready()
    stream = SimpleNamespace(
        readyRead=ready, readAll=lambda: pieces.pop(0) if pieces else b""
    )
    state = SimpleNamespace(buffer=None, stopped=False)
    source = SimpleNamespace(
        setBufferSize=lambda size: setattr(state, "buffer", size),
        start=lambda: stream,
        error=lambda: QtAudio.Error.NoError,
        stop=lambda: setattr(state, "stopped", True),
        deleteLater=lambda: None,
    )
    device = SimpleNamespace(isNull=lambda: False, isFormatSupported=lambda _: True)
    monkeypatch.setattr(
        audio, "QMediaDevices", SimpleNamespace(defaultAudioInput=lambda: device)
    )
    monkeypatch.setattr(audio, "QAudioSource", lambda *_: source)
    return state, pieces, ready


@pytest.mark.parametrize("streaming", [False, True])
def test_start_drains_first_buffer_without_waiting_for_next_notification(
    recorder, monkeypatch, streaming
):
    state, pieces, ready = startup_source(monkeypatch)
    chunks, started = [], []
    recorder.pcm_ready.connect(chunks.append)
    recorder.capturing.connect(lambda: started.append(True))
    assert recorder.start(streaming=streaming)
    assert state.buffer == 640  # Request 20 ms at 16 kHz, not a latency guarantee.
    assert started == [True]
    assert (chunks if streaming else [bytes(recorder.pcm)]) == [b"\x01\x00"]
    pieces.append(b"\x02\x00")
    ready.callback()
    assert started == [True]
    recorder.cancel()
    assert not recorder._capture_ready and state.stopped


def test_capture_ready_waits_for_complete_sample_and_resets_after_cancel(
    recorder, monkeypatch
):
    _, pieces, ready = startup_source(monkeypatch, first=b"\x01")
    started = []
    recorder.capturing.connect(lambda: started.append(True))
    assert recorder.start(streaming=True)
    assert not started
    pieces.append(b"\x00")
    ready.callback()
    assert started == [True]
    recorder.cancel()
    startup_source(monkeypatch, first=b"")
    assert recorder.start(streaming=True)
    assert started == [True] and not recorder._capture_ready


def test_cancel_from_first_frame_does_not_emit_pcm_or_restart_timers(
    recorder, monkeypatch
):
    state, _, _ = startup_source(monkeypatch)
    levels, chunks = [], []
    recorder.level.connect(levels.append)
    recorder.pcm_ready.connect(chunks.append)
    recorder.capturing.connect(recorder.cancel)
    assert not recorder.start(streaming=True)
    assert state.stopped and recorder.source is None
    assert not levels and not chunks
    assert not recorder.monitor.isActive() and not recorder.timer.isActive()


def test_replaced_source_from_first_frame_never_receives_old_pcm(recorder, monkeypatch):
    state, _, _ = startup_source(monkeypatch)
    chunks, replacements = [], []
    recorder.pcm_ready.connect(chunks.append)

    def replace():
        recorder.cancel()
        startup_source(monkeypatch, first=b"")
        assert recorder.start(streaming=True)
        replacements.append(recorder.source)

    recorder.capturing.connect(replace)
    assert not recorder.start(streaming=True)
    assert state.stopped and recorder.source is replacements[0]
    assert not chunks and recorder._captured_bytes == 0
    assert recorder.monitor.isActive() and recorder.timer.isActive()


def test_level_callback_cannot_feed_old_pcm_to_replaced_source(recorder, monkeypatch):
    state, _, _ = startup_source(monkeypatch)
    chunks = []
    recorder.pcm_ready.connect(chunks.append)

    def replace(_level):
        recorder.cancel()
        startup_source(monkeypatch, first=b"")
        assert recorder.start(streaming=True)

    recorder.level.connect(replace)
    assert not recorder.start(streaming=True)
    assert state.stopped and recorder.source is not None
    assert not chunks and recorder._captured_bytes == 0
