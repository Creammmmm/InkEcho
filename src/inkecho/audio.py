"""Bounded microphone capture; audio and WAV encoding stay in memory."""

import io
import math
import struct
import wave

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices, QtAudio


def wav_bytes(pcm: bytes, sample_rate: int) -> bytes:
    if not pcm or len(pcm) % 2:
        raise ValueError("Audio must contain complete 16-bit samples.")
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(pcm)
    return output.getvalue()


class Recorder(QObject):
    level = Signal(float)
    pcm_ready = Signal(bytes)
    finished = Signal(bytes, float)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.source: QAudioSource | None = None
        self.stream = None
        self.pcm = bytearray()
        self.sample_rate = 16000
        self.max_bytes = 0
        self.streaming = False
        self._stream_tail = b""
        self._captured_bytes = 0
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self._fail("recording_timed_out"))
        self.monitor = QTimer(self)
        self.monitor.setInterval(50)
        self.monitor.timeout.connect(self._check_source)

    @staticmethod
    def devices() -> list[tuple[bytes, str]]:
        return [(bytes(d.id()), d.description()) for d in QMediaDevices.audioInputs()]

    def start(
        self,
        device_id: bytes | None = None,
        *,
        sample_rate: int = 16000,
        max_seconds: float = 120,
        streaming: bool = False,
    ) -> bool:
        if self.source is not None:
            return False
        if sample_rate not in (16000, 24000, 48000) or not 0.1 <= max_seconds <= 300:
            raise ValueError("Invalid recording rate or duration.")
        device = QMediaDevices.defaultAudioInput()
        if device_id is not None:
            device = next(
                (d for d in QMediaDevices.audioInputs() if bytes(d.id()) == device_id),
                None,
            )
        if device is None or device.isNull():
            self.failed.emit("microphone_unavailable")
            return False
        audio_format = QAudioFormat()
        audio_format.setSampleRate(sample_rate)
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not device.isFormatSupported(audio_format):
            self.failed.emit("audio_format_unsupported")
            return False
        self.sample_rate = sample_rate
        self.streaming = streaming
        self._stream_tail = b""
        self._captured_bytes = 0
        self.max_bytes = int(sample_rate * 2 * max_seconds)
        self.pcm.clear()
        self.source = QAudioSource(device, audio_format, self)
        self.stream = self.source.start()
        if self.stream is None or self.source.error() != QtAudio.Error.NoError:
            self._fail("microphone_start_failed")
            return False
        self.stream.readyRead.connect(self._read)
        self.monitor.start()
        self.timer.start(round(max_seconds * 1000))
        return True

    def _read(self) -> None:
        if self.stream is None:
            return
        data = bytes(self.stream.readAll())
        captured = self._captured_bytes if self.streaming else len(self.pcm)
        if captured + len(data) > self.max_bytes:
            self._fail("recording_timed_out")
            return
        self._captured_bytes += len(data)
        if not self.streaming:
            self.pcm.extend(data)
        samples = len(data) // 2
        if samples:
            values = struct.unpack(f"<{samples}h", data[: samples * 2])
            rms = math.sqrt(sum(value * value for value in values) / samples) / 32768
            self.level.emit(min(rms, 1.0))
        if self.streaming and self.source is not None:
            complete = self._stream_tail + data
            boundary = len(complete) - len(complete) % 2
            self._stream_tail = complete[boundary:]
            if boundary:
                self.pcm_ready.emit(complete[:boundary])

    def _check_source(self) -> None:
        # PySide6 6.12 cannot marshal QAudioSource's legacy QAudio::State signal.
        if self.source and (
            self.source.error() != QtAudio.Error.NoError
            or self.source.state() == QtAudio.State.StoppedState
        ):
            self._fail("microphone_interrupted")

    def _release(self) -> None:
        self.timer.stop()
        self.monitor.stop()
        source, self.source = self.source, None
        self.stream = None
        if source:
            source.stop()
            source.deleteLater()

    def _fail(self, reason: str) -> None:
        if self.source is None:
            return
        self._release()
        self.pcm.clear()
        self._stream_tail = b""
        self._captured_bytes = 0
        self.failed.emit(reason)

    def cancel(self) -> None:
        self._release()
        self.pcm.clear()
        self._stream_tail = b""
        self._captured_bytes = 0

    def stop(self) -> bytes | None:
        if self.source is None:
            return None
        if self.source.error() != QtAudio.Error.NoError:
            self._fail("microphone_interrupted")
            return None
        self._read()
        if self.source is None:
            return None
        self._release()
        size = self._captured_bytes if self.streaming else len(self.pcm)
        pcm = b"" if self.streaming else bytes(self.pcm)
        self.pcm.clear()
        self._stream_tail = b""
        self._captured_bytes = 0
        if not size or size % 2:
            self.failed.emit("empty_recording")
            return None
        audio = b"" if self.streaming else wav_bytes(pcm, self.sample_rate)
        self.finished.emit(audio, size / (2 * self.sample_rate))
        return audio
