"""One-shot RAM handoff primitives, with no CLI, keyring or network access.

The future controller must authenticate the SSH peer, pin the reviewed expected
READY identity, and close the write side after sending. These functions neither
grant live authorization nor establish a transport. Test constraints must never
be exposed by a live controller. Python objects are not cryptographically erased.
"""

import fcntl
import hashlib
import io
import json
import os
import re
import stat
import struct
import wave
from collections.abc import Callable
from dataclasses import dataclass

REFS = ("provider/qwen", "provider/deepseek")
ORIGINS = frozenset(
    {
        "inkecho.app",
        "inkecho.performance",
        "inkecho.providers",
        "inkecho.realtime",
        "inkecho.polish_stream",
        "inkecho.streaming_output",
        "inkecho.platform.keyboard",
        "inkecho.runtime",
        "inkecho.security",
    }
)
MAX_METADATA = 16384
MAX_AUDIO = 1048576
CODES = frozenset(
    {"schema", "ready", "audio", "credentials", "io", "eof", "used", "revalidate"}
)


class HandoffError(ValueError):
    """Only fixed codes cross this module's error boundary."""

    def __init__(self, code: str):
        super().__init__(code if code in CODES else "schema")


def _pipe(fd: int, *, writing: bool) -> None:
    """Linux anonymous pipes only; reject files, named FIFOs and sockets."""
    try:
        if type(fd) is not int or fd < 0:
            raise ValueError
        info = os.fstat(fd)
        if (
            not stat.S_ISFIFO(info.st_mode)
            or os.readlink(f"/proc/self/fd/{fd}") != f"pipe:[{info.st_ino}]"
            or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
            != (os.O_WRONLY if writing else os.O_RDONLY)
        ):
            raise ValueError
    except Exception:
        raise HandoffError("io") from None


def _sha(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


@dataclass(frozen=True)
class AudioConstraints:
    sha256: str
    size: int
    frames: int


PUBLIC_AUDIO = AudioConstraints(
    "0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf",
    571456,
    282322,
)


def validate_audio(audio: bytes, constraints: AudioConstraints = PUBLIC_AUDIO) -> None:
    """Validate original bytes; never convert or re-encode the WAV."""
    try:
        if (
            type(audio) is not bytes
            or not _sha(constraints.sha256)
            or type(constraints.size) is not int
            or not 0 < constraints.size <= MAX_AUDIO
            or type(constraints.frames) is not int
            or not 0 < constraints.frames <= MAX_AUDIO // 2
            or len(audio) != constraints.size
            or hashlib.sha256(audio).hexdigest() != constraints.sha256
        ):
            raise ValueError
        with wave.open(io.BytesIO(audio), "rb") as recording:
            if (
                recording.getparams()[:4] != (1, 2, 16000, constraints.frames)
                or recording.getcomptype() != "NONE"
                or len(recording.readframes(constraints.frames))
                != constraints.frames * 2
                or recording.readframes(1)
            ):
                raise ValueError
    except Exception:
        raise HandoffError("audio") from None


def _credentials(values: object) -> dict[str, str]:
    if type(values) is not dict or set(values) != set(REFS):
        raise HandoffError("credentials")
    for key in values.values():
        if (
            type(key) is not str
            or not key
            or any(char.isspace() or ord(char) < 33 or ord(char) == 127 for char in key)
        ):
            raise HandoffError("credentials")
        try:
            if len(key.encode("utf-8", "strict")) > 4096:
                raise ValueError
        except (ValueError, UnicodeError):
            raise HandoffError("credentials") from None
    return values.copy()


class RamCredentials:
    """The get(reference) interface consumed by Session; no backend or fallback."""

    def __init__(self, values: dict[str, str]):
        self._values = _credentials(values)

    def get(self, reference: str) -> str:
        if type(reference) is not str or reference not in self._values:
            raise HandoffError("credentials")
        return self._values[reference]

    def close(self) -> None:
        self._values.clear()

    def __repr__(self) -> str:
        return "RamCredentials(<redacted>)"


@dataclass(frozen=True)
class ReadyExpected:
    plan_sha256: str
    origins: dict[str, str]
    producer_pid: int
    producer_start: str


def validate_ready(ready: object, expected: ReadyExpected) -> None:
    """Compare all fields to independently pinned launcher/package evidence."""
    if (
        type(ready) is not dict
        or set(ready)
        != {"version", "kind", "plan_sha256", "origins", "producer", "budget"}
        or type(ready["version"]) is not int
        or ready["version"] != 1
        or ready["kind"] != "ready"
        or not _sha(expected.plan_sha256)
        or ready["plan_sha256"] != expected.plan_sha256
        or type(expected.origins) is not dict
        or set(expected.origins) != ORIGINS
        or any(not _sha(value) for value in expected.origins.values())
        or type(ready["origins"]) is not dict
        or ready["origins"] != expected.origins
        or type(expected.producer_pid) is not int
        or expected.producer_pid <= 0
        or type(expected.producer_start) is not str
        or re.fullmatch(r"[1-9][0-9]{0,19}", expected.producer_start) is None
        or type(ready["producer"]) is not dict
        or set(ready["producer"]) != {"pid", "start_ticks"}
        or type(ready["producer"]["pid"]) is not int
        or ready["producer"]
        != {"pid": expected.producer_pid, "start_ticks": expected.producer_start}
        or type(ready["budget"]) is not dict
        or set(ready["budget"]) != {"A", "B"}
    ):
        raise HandoffError("ready")
    for arm in ready["budget"].values():
        if (
            type(arm) is not dict
            or set(arm) != {"asr", "polishing"}
            or any(type(count) is not int or count != 0 for count in arm.values())
        ):
            raise HandoffError("ready")


def read_exact(fd: int, count: int) -> bytes:
    """Advance only; truncated streams never cause a reconnect or replay."""
    _pipe(fd, writing=False)
    result = bytearray()
    while len(result) < count:
        try:
            block = os.read(fd, min(65536, count - len(result)))
        except InterruptedError:
            continue
        except Exception:
            raise HandoffError("io") from None
        if not block:
            raise HandoffError("eof")
        result.extend(block)
    return bytes(result)


def write_exact(fd: int, value: bytes) -> None:
    _pipe(fd, writing=True)
    offset = 0
    while offset < len(value):
        try:
            count = os.write(fd, memoryview(value)[offset:])
        except InterruptedError:
            continue
        except Exception:
            raise HandoffError("io") from None
        if count <= 0:
            raise HandoffError("io")
        offset += count


def _json(encoded: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def invalid_constant(_value):
        raise ValueError

    try:
        result = json.loads(
            encoded.decode("utf-8", "strict"),
            object_pairs_hook=unique,
            parse_constant=invalid_constant,
        )
        if type(result) is not dict:
            raise ValueError
        return result
    except Exception:
        raise HandoffError("schema") from None


def receive_ready(fd: int, expected: ReadyExpected) -> dict:
    """Read one bounded READY frame; its pipe may remain open for later status."""
    _pipe(fd, writing=False)
    size = struct.unpack("!I", read_exact(fd, 4))[0]
    if not 0 < size <= MAX_METADATA:
        raise HandoffError("schema")
    ready = _json(read_exact(fd, size))
    validate_ready(ready, expected)
    return ready


class Sender:
    """One attempt per instance, even after partial writes or validation failure."""

    def __init__(self):
        self._used = False

    def send(
        self,
        fd: int,
        ready: dict,
        expected: ReadyExpected,
        *,
        revalidate: Callable[[], None],
        read_key: Callable[[str], str],
        read_audio: Callable[[], bytes],
        constraints: AudioConstraints = PUBLIC_AUDIO,
    ) -> None:
        if self._used:
            raise HandoffError("used")
        self._used = True
        _pipe(fd, writing=True)
        validate_ready(ready, expected)
        try:
            revalidate()
        except Exception:
            raise HandoffError("revalidate") from None
        try:
            values = _credentials(
                {reference: read_key(reference) for reference in REFS}
            )
        except Exception:
            raise HandoffError("credentials") from None
        try:
            audio = read_audio()
        except Exception:
            raise HandoffError("audio") from None
        validate_audio(audio, constraints)
        metadata = {
            "version": 1,
            "kind": "handoff",
            "plan_sha256": expected.plan_sha256,
            "audio_sha256": constraints.sha256,
            "audio_bytes": constraints.size,
            "credentials": values,
        }
        encoded = json.dumps(
            metadata, ensure_ascii=True, separators=(",", ":")
        ).encode()
        if len(encoded) > MAX_METADATA:
            raise HandoffError("schema")
        write_exact(fd, struct.pack("!I", len(encoded)))
        write_exact(fd, encoded)
        write_exact(fd, audio)


class Receiver:
    def __init__(self):
        self._used = False

    def receive(
        self,
        fd: int,
        plan_sha256: str,
        *,
        constraints: AudioConstraints = PUBLIC_AUDIO,
    ) -> tuple[RamCredentials, bytes]:
        """Read to EOF before releasing any credentials/audio to the caller."""
        if self._used:
            raise HandoffError("used")
        self._used = True
        _pipe(fd, writing=False)
        size = struct.unpack("!I", read_exact(fd, 4))[0]
        if not 0 < size <= MAX_METADATA:
            raise HandoffError("schema")
        metadata = _json(read_exact(fd, size))
        if (
            set(metadata)
            != {
                "version",
                "kind",
                "plan_sha256",
                "audio_sha256",
                "audio_bytes",
                "credentials",
            }
            or type(metadata["version"]) is not int
            or metadata["version"] != 1
            or metadata["kind"] != "handoff"
            or not _sha(plan_sha256)
            or metadata["plan_sha256"] != plan_sha256
            or metadata["audio_sha256"] != constraints.sha256
            or type(metadata["audio_bytes"]) is not int
            or metadata["audio_bytes"] != constraints.size
            or not 0 < constraints.size <= MAX_AUDIO
        ):
            raise HandoffError("schema")
        values = _credentials(metadata["credentials"])
        audio = read_exact(fd, constraints.size)
        validate_audio(audio, constraints)
        while True:
            try:
                tail = os.read(fd, 1)
                break
            except InterruptedError:
                continue
            except Exception:
                raise HandoffError("io") from None
        if tail:
            raise HandoffError("schema")
        return RamCredentials(values), audio
