"""The feasibility probe must not report unavailable or empty audio as success."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/audio_probe.py"
spec = importlib.util.spec_from_file_location("audio_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.fixture
def audio(monkeypatch):
    state = SimpleNamespace(bytes=128, error="NoError", stopped=False, cleared=False)
    audio_format = SimpleNamespace(
        sampleRate=lambda: 48000,
        channelCount=lambda: 1,
        sampleFormat=lambda: SimpleNamespace(name="Int16"),
    )
    device = SimpleNamespace(
        description=lambda: "Test microphone", preferredFormat=lambda: audio_format
    )
    state.devices = [device]
    monkeypatch.setattr(probe.sys, "argv", [str(SCRIPT), "--record"])
    monkeypatch.setattr(
        probe,
        "QCoreApplication",
        lambda _: SimpleNamespace(exec=lambda: None, quit=lambda: None),
    )
    monkeypatch.setattr(
        probe,
        "QMediaDevices",
        SimpleNamespace(
            audioInputs=lambda: state.devices, defaultAudioInput=lambda: device
        ),
    )
    monkeypatch.setattr(probe, "QTimer", SimpleNamespace(singleShot=lambda *_: None))
    monkeypatch.setattr(
        probe,
        "QBuffer",
        lambda: SimpleNamespace(
            open=lambda _: True,
            size=lambda: state.bytes,
            close=lambda: None,
            setData=lambda data: setattr(state, "cleared", data == b""),
        ),
    )
    monkeypatch.setattr(
        probe,
        "QAudioSource",
        lambda *_: SimpleNamespace(
            start=lambda _: None,
            stop=lambda: setattr(state, "stopped", True),
            error=lambda: SimpleNamespace(name=state.error),
        ),
    )
    return state


def test_missing_device_fails(audio):
    audio.devices = []
    assert probe.main() == 1


@pytest.mark.parametrize("byte_count,error", [(0, "NoError"), (128, "IOError")])
def test_invalid_capture_fails_and_releases_memory(audio, byte_count, error):
    audio.bytes, audio.error = byte_count, error
    assert probe.main() == 1
    assert audio.stopped and audio.cleared


def test_success_only_reports_metadata_and_releases_memory(audio, capsys):
    assert probe.main() == 0
    assert audio.stopped and audio.cleared
    assert '"audio_saved": false' in capsys.readouterr().out
