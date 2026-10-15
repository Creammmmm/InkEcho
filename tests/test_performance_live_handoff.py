"""Synthetic audio and anonymous local pipes only; no keyring or cloud."""

import hashlib
import importlib
import io
import json
import os
import socket
import struct
import threading
import wave
from contextlib import contextmanager
from pathlib import Path

import pytest


@pytest.fixture
def handoff(monkeypatch):
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "scripts/validation")
    )
    return importlib.import_module("performance_live_handoff")


@pytest.fixture
def sample(handoff):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        recording.writeframes(b"\0\0" * 80)
    audio = buffer.getvalue()
    constraints = handoff.AudioConstraints(
        hashlib.sha256(audio).hexdigest(), len(audio), 80
    )
    expected = handoff.ReadyExpected(
        "a" * 64, {name: "b" * 64 for name in handoff.ORIGINS}, 4321, "123456"
    )
    ready = {
        "version": 1,
        "kind": "ready",
        "plan_sha256": expected.plan_sha256,
        "origins": expected.origins.copy(),
        "producer": {
            "pid": expected.producer_pid,
            "start_ticks": expected.producer_start,
        },
        "budget": {arm: {"asr": 0, "polishing": 0} for arm in ("A", "B")},
    }
    return audio, constraints, expected, ready


def metadata(sample):
    _audio, constraints, expected, _ready = sample
    return {
        "version": 1,
        "kind": "handoff",
        "plan_sha256": expected.plan_sha256,
        "audio_sha256": constraints.sha256,
        "audio_bytes": constraints.size,
        "credentials": {
            "provider/qwen": "synthetic-qwen",
            "provider/deepseek": "synthetic-polish",
        },
    }


def frame(value, audio=b""):
    encoded = value if isinstance(value, bytes) else json.dumps(value).encode()
    return struct.pack("!I", len(encoded)) + encoded + audio


@contextmanager
def source(value):
    reader, writer = os.pipe()
    try:
        assert os.write(writer, value) == len(value)
        os.close(writer)
        writer = None
        yield reader
    finally:
        os.close(reader)
        if writer is not None:
            os.close(writer)


def receive(handoff, sample, value):
    _audio, constraints, expected, _ready = sample
    with source(value) as reader:
        return handoff.Receiver().receive(
            reader, expected.plan_sha256, constraints=constraints
        )


@contextmanager
def sink():
    reader, writer = os.pipe()
    try:
        yield writer
    finally:
        os.close(reader)
        os.close(writer)


def test_anonymous_pipe_roundtrip_lazy_reads_and_no_replay(handoff, sample):
    audio, constraints, expected, ready = sample
    events, failures, result = [], [], []
    reader, writer = os.pipe()
    sender = handoff.Sender()

    def consume():
        try:
            result.append(
                handoff.Receiver().receive(
                    reader, expected.plan_sha256, constraints=constraints
                )
            )
        except Exception as error:
            failures.append(error)
        finally:
            os.close(reader)

    thread = threading.Thread(target=consume)
    thread.start()
    try:
        sender.send(
            writer,
            ready,
            expected,
            revalidate=lambda: events.append("revalidate"),
            read_key=lambda ref: events.append(ref) or "synthetic-key",
            read_audio=lambda: events.append("audio") or audio,
            constraints=constraints,
        )
        with pytest.raises(handoff.HandoffError, match="^used$"):
            sender.send(
                writer,
                ready,
                expected,
                revalidate=lambda: None,
                read_key=lambda _: None,
                read_audio=lambda: None,
            )
    finally:
        os.close(writer)
        thread.join(2)
    assert not thread.is_alive() and not failures
    credentials, received = result[0]
    assert received == audio and events == ["revalidate", *handoff.REFS, "audio"]
    assert credentials.get("provider/qwen") == "synthetic-key"
    assert "synthetic-key" not in repr(credentials)
    with pytest.raises(handoff.HandoffError, match="^credentials$"):
        credentials.get("other")
    credentials.close()
    with pytest.raises(handoff.HandoffError, match="^credentials$"):
        credentials.get("provider/qwen")


def test_partial_writes_advance_offset_and_chunked_reads(handoff, sample, monkeypatch):
    audio, constraints, expected, ready = sample
    original_write, original_read = os.write, os.read
    writes = []

    def partial_write(fd, value):
        if not writes:
            writes.append(0)
            raise InterruptedError
        amount = original_write(fd, value[:7])
        writes.append(amount)
        return amount

    monkeypatch.setattr(handoff.os, "write", partial_write)
    monkeypatch.setattr(
        handoff.os, "read", lambda fd, size: original_read(fd, min(size, 3))
    )
    reader, writer = os.pipe()
    try:
        handoff.Sender().send(
            writer,
            ready,
            expected,
            revalidate=lambda: None,
            read_key=lambda _: "fake",
            read_audio=lambda: audio,
            constraints=constraints,
        )
        os.close(writer)
        writer = None
        credentials, received = handoff.Receiver().receive(
            reader, expected.plan_sha256, constraints=constraints
        )
        assert received == audio and credentials.get("provider/deepseek") == "fake"
        assert max(writes) == 7 and sum(writes) > len(audio)
    finally:
        os.close(reader)
        if writer is not None:
            os.close(writer)


@pytest.mark.parametrize(
    "change",
    [
        "extra",
        "version",
        "pid",
        "start",
        "origin",
        "missing_origin",
        "budget",
        "bool_budget",
        "plan",
    ],
)
def test_ready_mismatch_does_not_read_any_private_input(handoff, sample, change):
    _audio, _constraints, expected, ready = sample
    if change == "extra":
        ready["unknown"] = "private"
    elif change == "version":
        ready["version"] = True
    elif change == "pid":
        ready["producer"]["pid"] += 1
    elif change == "start":
        ready["producer"]["start_ticks"] = "0"
    elif change == "origin":
        ready["origins"]["inkecho.app"] = "c" * 64
    elif change == "missing_origin":
        ready["origins"].pop("inkecho.security")
    elif change == "budget":
        ready["budget"]["A"]["asr"] = 1
    elif change == "bool_budget":
        ready["budget"]["B"]["polishing"] = False
    else:
        ready["plan_sha256"] = "d" * 64
    calls = []
    with sink() as writer, pytest.raises(handoff.HandoffError, match="^ready$"):
        handoff.Sender().send(
            writer,
            ready,
            expected,
            revalidate=lambda: calls.append(1),
            read_key=lambda _: calls.append(2),
            read_audio=lambda: calls.append(3),
        )
    assert not calls


def test_ready_frame_duplicate_and_bounded_metadata(handoff, sample):
    expected, ready = sample[2:]
    with source(frame(ready)) as reader:
        assert handoff.receive_ready(reader, expected) == ready
    for payload in (
        frame(b'{"version":1,"version":1}'),
        struct.pack("!I", handoff.MAX_METADATA + 1),
    ):
        with (
            source(payload) as reader,
            pytest.raises(handoff.HandoffError, match="^schema$"),
        ):
            handoff.receive_ready(reader, expected)


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "unknown",
        "plan",
        "sha",
        "size",
        "refs",
        "missing_key",
        "empty",
        "crlf",
        "oversized_key",
        "bool_size",
    ],
)
def test_bad_handoff_metadata_rejected(handoff, sample, change):
    data = metadata(sample)
    if change == "version":
        data["version"] = 2
    elif change == "unknown":
        data["private"] = "do-not-echo"
    elif change == "plan":
        data["plan_sha256"] = "c" * 64
    elif change == "sha":
        data["audio_sha256"] = "c" * 64
    elif change == "size":
        data["audio_bytes"] += 1
    elif change == "refs":
        data["credentials"] = {"wrong": "fake"}
    elif change == "missing_key":
        data["credentials"].pop("provider/qwen")
    elif change == "bool_size":
        data["audio_bytes"] = True
    else:
        data["credentials"]["provider/qwen"] = {
            "empty": "",
            "crlf": "private\r\nvalue",
            "oversized_key": "x" * 4097,
        }[change]
    with pytest.raises(handoff.HandoffError) as caught:
        receive(handoff, sample, frame(data, sample[0]))
    assert caught.value.args[0] in handoff.CODES
    assert "private" not in str(caught.value)


@pytest.mark.parametrize(
    "encoded",
    [
        b'{"version":1,"version":1}',
        b'{"private":"\xff"}',
        b'{"v":NaN}',
        b"[]",
        b'{"credentials":{"provider/qwen":"first","provider/qwen":"second"}}',
    ],
)
def test_invalid_utf8_json_and_duplicate_fields(handoff, sample, encoded):
    with pytest.raises(handoff.HandoffError, match="^schema$"):
        receive(handoff, sample, frame(encoded, sample[0]))


@pytest.mark.parametrize("cut", [0, 1, 3, 4, 10, -1])
def test_truncation_rejects_without_returning_credentials(handoff, sample, cut):
    value = frame(metadata(sample), sample[0])
    with pytest.raises(handoff.HandoffError, match="^eof$"):
        receive(handoff, sample, value[:cut])


def test_extra_bytes_and_changed_raw_audio_rejected(handoff, sample):
    with pytest.raises(handoff.HandoffError, match="^schema$"):
        receive(handoff, sample, frame(metadata(sample), sample[0]) + b"extra")
    with pytest.raises(handoff.HandoffError, match="^audio$"):
        receive(handoff, sample, frame(metadata(sample), sample[0][:-1] + b"x"))
    with pytest.raises(handoff.HandoffError, match="^schema$"):
        receive(handoff, sample, struct.pack("!I", handoff.MAX_METADATA + 1))


@pytest.mark.parametrize(
    "channels,width,rate,frames",
    [(2, 2, 16000, 80), (1, 1, 16000, 80), (1, 2, 8000, 80), (1, 2, 16000, 79)],
)
def test_wave_parameters_not_merely_hash(
    handoff, sample, channels, width, rate, frames
):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as recording:
        recording.setparams((channels, width, rate, 0, "NONE", "not compressed"))
        recording.writeframes(b"\0" * channels * width * frames)
    audio = buffer.getvalue()
    constraints = handoff.AudioConstraints(
        hashlib.sha256(audio).hexdigest(), len(audio), 80
    )
    with pytest.raises(handoff.HandoffError, match="^audio$"):
        handoff.validate_audio(audio, constraints)


@pytest.mark.parametrize(
    "stage,code",
    [
        ("revalidate", "revalidate"),
        ("key", "credentials"),
        ("audio", "audio"),
        ("write", "io"),
    ],
)
def test_private_failures_redacted_and_sender_cannot_retry(
    handoff, sample, stage, code, monkeypatch
):
    audio, constraints, expected, ready = sample
    calls = []

    def failing():
        raise RuntimeError("private-key-audio-backend-details")

    if stage == "write":
        monkeypatch.setattr(handoff.os, "write", lambda *_: failing())
    sender = handoff.Sender()
    options = dict(
        revalidate=failing if stage == "revalidate" else lambda: None,
        read_key=lambda _: failing() if stage == "key" else "fake",
        read_audio=failing if stage == "audio" else lambda: audio,
        constraints=constraints,
    )
    with (
        sink() as writer,
        pytest.raises(handoff.HandoffError, match=f"^{code}$") as caught,
    ):
        sender.send(writer, ready, expected, **options)
    assert "private" not in str(caught.value) and caught.value.__suppress_context__
    with pytest.raises(handoff.HandoffError, match="^used$"):
        sender.send(
            -1,
            ready,
            expected,
            revalidate=lambda: calls.append(1),
            read_key=lambda _: None,
            read_audio=lambda: None,
        )
    assert not calls


def test_receiver_failure_is_terminal_for_instance(handoff, sample):
    receiver = handoff.Receiver()
    with source(b"") as reader, pytest.raises(handoff.HandoffError, match="^eof$"):
        receiver.receive(reader, sample[2].plan_sha256, constraints=sample[1])
    with pytest.raises(handoff.HandoffError, match="^used$"):
        receiver.receive(-1, sample[2].plan_sha256, constraints=sample[1])


def test_default_constraints_fail_closed_for_synthetic_audio(handoff, sample):
    with pytest.raises(handoff.HandoffError, match="^audio$"):
        handoff.validate_audio(sample[0])


@pytest.mark.parametrize("kind", ["file", "fifo", "socket", "invalid"])
def test_non_anonymous_fds_rejected_before_callbacks(handoff, sample, tmp_path, kind):
    path = tmp_path / "controlled-target"
    sockets = []
    if kind == "file":
        path.write_bytes(b"unchanged")
        fd = os.open(path, os.O_RDWR)
    elif kind == "fifo":
        os.mkfifo(path)
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    elif kind == "socket":
        sockets = list(socket.socketpair())
        fd = sockets[0].fileno()
    else:
        fd = -1
    events = []
    sender = handoff.Sender()
    try:
        with pytest.raises(handoff.HandoffError, match="^io$"):
            sender.send(
                fd,
                sample[3],
                sample[2],
                revalidate=lambda: events.append(1),
                read_key=lambda _: events.append(2),
                read_audio=lambda: events.append(3),
            )
        assert not events
        with pytest.raises(handoff.HandoffError, match="^used$"):
            sender.send(
                fd,
                sample[3],
                sample[2],
                revalidate=lambda: None,
                read_key=lambda _: None,
                read_audio=lambda: None,
            )
        receiver = handoff.Receiver()
        with pytest.raises(handoff.HandoffError, match="^io$"):
            receiver.receive(fd, sample[2].plan_sha256, constraints=sample[1])
        with pytest.raises(handoff.HandoffError, match="^used$"):
            receiver.receive(fd, sample[2].plan_sha256, constraints=sample[1])
        with pytest.raises(handoff.HandoffError, match="^io$"):
            handoff.receive_ready(fd, sample[2])
        if kind == "file":
            assert path.read_bytes() == b"unchanged"
    finally:
        if sockets:
            for channel in sockets:
                channel.close()
        elif fd >= 0:
            os.close(fd)


def test_anonymous_pipe_direction_enforced(handoff, sample):
    reader, writer = os.pipe()
    calls = []
    try:
        with pytest.raises(handoff.HandoffError, match="^io$"):
            handoff.Sender().send(
                reader,
                sample[3],
                sample[2],
                revalidate=lambda: calls.append(1),
                read_key=lambda _: None,
                read_audio=lambda: None,
            )
        assert not calls
        with pytest.raises(handoff.HandoffError, match="^io$"):
            handoff.Receiver().receive(
                writer, sample[2].plan_sha256, constraints=sample[1]
            )
        with pytest.raises(handoff.HandoffError, match="^io$"):
            handoff.receive_ready(writer, sample[2])
    finally:
        os.close(reader)
        os.close(writer)


def test_large_synthetic_audio_crosses_real_pipe_capacity(handoff, sample):
    buffer = io.BytesIO()
    frames = 282322
    with wave.open(buffer, "wb") as recording:
        recording.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        recording.writeframes(b"\0\0" * frames)
    audio = buffer.getvalue()
    constraints = handoff.AudioConstraints(
        hashlib.sha256(audio).hexdigest(), len(audio), frames
    )
    reader, writer = os.pipe()
    outcomes, failures = [], []

    def consume():
        try:
            outcomes.append(
                handoff.Receiver().receive(
                    reader, sample[2].plan_sha256, constraints=constraints
                )
            )
        except Exception as error:
            failures.append(error)
        finally:
            os.close(reader)

    thread = threading.Thread(target=consume)
    thread.start()
    try:
        handoff.Sender().send(
            writer,
            sample[3],
            sample[2],
            revalidate=lambda: None,
            read_key=lambda _: "synthetic",
            read_audio=lambda: audio,
            constraints=constraints,
        )
    finally:
        os.close(writer)
        thread.join(2)
    assert not thread.is_alive() and not failures
    assert outcomes[0][1] == audio and len(audio) > 500000


def test_truncated_pcm_rejected_even_with_matching_byte_hash(handoff, sample):
    audio = sample[0][:-2]
    constraints = handoff.AudioConstraints(
        hashlib.sha256(audio).hexdigest(), len(audio), 80
    )
    with pytest.raises(handoff.HandoffError, match="^audio$"):
        handoff.validate_audio(audio, constraints)
