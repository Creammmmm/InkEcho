"""Volcengine binary ASR framing; only explicitly final results are returned."""

import gzip
import json
import uuid
import zlib
from dataclasses import dataclass
from urllib.parse import urlsplit

from websockets.exceptions import ConnectionClosed

from inkecho.asr_wire import (
    credential_bundle,
    open_socket,
    paced_audio,
    send_frame,
    validate_endpoint,
)
from inkecho.config import Provider
from inkecho.providers import ProviderError
from inkecho.realtime import QwenRealtimeSession

PROTOCOL = "volc_binary"
LIMIT = 1024 * 1024


def encode_frame(kind: int, payload: bytes, *, final: bool = False) -> bytes:
    """Encode documented client frames without a sequence field."""
    compressed = gzip.compress(payload, mtime=0)
    if kind not in {1, 2}:
        raise ProviderError("configuration")
    serialization = 0x10 if kind == 1 else 0
    header = bytes((0x11, (kind << 4) | (2 if final else 0), serialization | 1, 0))
    return header + len(compressed).to_bytes(4, "big") + compressed


def decode_frame(raw: bytes) -> tuple[bool, dict]:
    """Bound both compressed and expanded messages; final flags own completion."""
    try:
        if not isinstance(raw, bytes) or not 8 <= len(raw) <= LIMIT:
            raise ValueError
        version, size = raw[0] >> 4, (raw[0] & 15) * 4
        kind, flags = raw[1] >> 4, raw[1] & 15
        serial, compression = raw[2] >> 4, raw[2] & 15
        if version != 1 or size < 4 or size > len(raw) - 4:
            raise ValueError
        if kind == 15:
            raise ProviderError("unavailable")
        if kind != 9 or flags not in {0, 1, 2, 3} or serial != 1:
            raise ValueError
        offset = size + (4 if flags & 1 else 0)
        if len(raw) < offset + 4:
            raise ValueError
        length = int.from_bytes(raw[offset : offset + 4], "big")
        body = raw[offset + 4 :]
        if len(body) != length:
            raise ValueError
        if compression == 1:
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
            body = decoder.decompress(body, LIMIT + 1)
            if len(body) > LIMIT or not decoder.eof or decoder.unused_data:
                raise ValueError
        elif compression != 0:
            raise ValueError
        value = json.loads(body)
        if not isinstance(value, dict):
            raise ValueError
        return bool(flags & 2), value
    except (ValueError, TypeError, IndexError, zlib.error, UnicodeError):
        raise ProviderError("response") from None


@dataclass(frozen=True)
class VolcConfig:
    endpoint: str
    model: str
    resource_id: str
    credential_mode: str = "api_key"
    sample_rate: int = 16000

    def __post_init__(self) -> None:
        validate_endpoint(self.endpoint)
        if (
            self.model != "bigmodel"
            or type(self.sample_rate) is not int
            or self.sample_rate != 16000
            or not isinstance(self.credential_mode, str)
            or self.credential_mode not in {"api_key", "app_access"}
            or not isinstance(self.resource_id, str)
            or not 0 < len(self.resource_id) <= 200
            or any(ord(c) <= 32 or ord(c) >= 127 for c in self.resource_id)
        ):
            raise ProviderError("configuration")

    @classmethod
    def from_provider(cls, provider: Provider, *, sample_rate: int = 16000):
        if (
            provider.role != "transcription"
            or provider.adapter != "volcengine"
            or provider.parameters.get("asr_protocol") != PROTOCOL
            or set(provider.parameters)
            - {"asr_protocol", "realtime_url", "resource_id", "credential_mode"}
        ):
            raise ProviderError("configuration")
        endpoint = provider.parameters.get("realtime_url")
        if endpoint is None:
            if urlsplit(provider.base_url).hostname != "openspeech.bytedance.com":
                raise ProviderError("configuration")
            endpoint = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"
        return cls(
            endpoint,
            provider.model,
            provider.parameters.get("resource_id", ""),
            provider.parameters.get("credential_mode", "api_key"),
            sample_rate,
        )


class VolcSession(QwenRealtimeSession):
    """Keep bounded lifecycle but own binary receive, headers and terminal flag."""

    set_completed_callback = None

    async def _open(self) -> None:
        mode = self.config.credential_mode
        fields = ("api_key",) if mode == "api_key" else ("app_key", "access_key")
        credentials = credential_bundle(self._key, fields)
        headers = {
            "X-Api-Resource-Id": self.config.resource_id,
            "X-Api-Connect-Id": uuid.uuid4().hex,
            "X-Api-Request-Id": uuid.uuid4().hex,
        }
        if mode == "api_key":
            headers["X-Api-Key"] = credentials["api_key"]
        else:
            headers["X-Api-App-Key"] = credentials["app_key"]
            headers["X-Api-Access-Key"] = credentials["access_key"]
        await open_socket(self, self.config.endpoint, headers)
        payload = {
            "user": {"uid": uuid.uuid4().hex},
            "audio": {
                "format": "pcm",
                "codec": "raw",
                "rate": 16000,
                "bits": 16,
                "channel": 1,
            },
            "request": {"model_name": "bigmodel", "enable_itn": True},
        }
        await send_frame(self, encode_frame(1, json.dumps(payload).encode()))
        # This protocol has no Qwen-style session.updated barrier; async servers
        # can omit replies for audio frames that produce no new recognition.
        self._ready.set_result(None)

    async def _emit_audio(self, pcm: bytes) -> None:
        await send_frame(self, encode_frame(2, pcm))

    async def _end_audio(self) -> None:
        await send_frame(self, encode_frame(2, b"", final=True))

    async def _send_audio(self) -> None:
        await paced_audio(self, 3200, self._emit_audio, self._end_audio)

    async def _receive(self) -> None:
        try:
            while not self._done.done():
                self._check()
                raw = await self._socket.recv()
                self._check()
                final, event = decode_frame(raw)
                code = event.get("code", 20000000)
                if type(code) is not int or code not in {0, 20000000}:
                    raise ProviderError("unavailable")
                if not final:
                    continue
                if not self._finish_sent:
                    raise ProviderError("response")
                result = event.get("result")
                text = result.get("text") if isinstance(result, dict) else None
                if not isinstance(text, str) or len(text) > 100000:
                    raise ProviderError("response")
                self._done.set_result(text)
        except ProviderError as exc:
            self._fail(exc.code)
        except ConnectionClosed:
            self._fail("response")
        except Exception:
            self._fail("network")
