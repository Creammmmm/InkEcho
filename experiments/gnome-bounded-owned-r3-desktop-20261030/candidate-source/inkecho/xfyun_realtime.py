"""iFLYTEK IAT: signed WebSocket, 40ms frames and final revision-aware text."""

import base64
import hashlib
import hmac
import re
import time
from dataclasses import dataclass
from email.utils import formatdate
from urllib.parse import urlencode, urlsplit

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

PROTOCOL = "xfyun_iat"
FIELDS = ("app_id", "api_key", "api_secret")


@dataclass(frozen=True)
class XfyunConfig:
    endpoint: str
    model: str
    sample_rate: int = 16000

    def __post_init__(self) -> None:
        validate_endpoint(self.endpoint)
        if (
            self.model != "iat"
            or type(self.sample_rate) is not int
            or self.sample_rate != 16000
        ):
            raise ProviderError("configuration")

    @classmethod
    def from_provider(
        cls, provider: Provider, *, sample_rate: int = 16000
    ) -> "XfyunConfig":
        if (
            provider.role != "transcription"
            or provider.adapter != "xfyun"
            or provider.parameters.get("asr_protocol") != PROTOCOL
            or set(provider.parameters) - {"asr_protocol", "realtime_url"}
        ):
            raise ProviderError("configuration")
        endpoint = provider.parameters.get("realtime_url")
        if endpoint is None:
            if urlsplit(provider.base_url).hostname != "iat-api.xfyun.cn":
                raise ProviderError("configuration")
            endpoint = "wss://iat-api.xfyun.cn/v2/iat"
        return cls(endpoint, provider.model, sample_rate)


def signed_url(
    endpoint: str, credentials: dict[str, str], now: float | None = None
) -> str:
    """Build the documented host/date/request-line HMAC-SHA256 in memory only."""
    url = urlsplit(endpoint)
    date = formatdate(time.time() if now is None else now, usegmt=True)
    canonical = f"host: {url.netloc}\ndate: {date}\nGET {url.path} HTTP/1.1"
    signature = base64.b64encode(
        hmac.new(
            credentials["api_secret"].encode(), canonical.encode(), hashlib.sha256
        ).digest()
    ).decode()
    authorization = (
        f'api_key="{credentials["api_key"]}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    return (
        endpoint
        + "?"
        + urlencode(
            {
                "authorization": base64.b64encode(authorization.encode()).decode(),
                "date": date,
                "host": url.netloc,
            }
        )
    )


class XfyunSession(QwenRealtimeSession):
    """Reuse bounded transport lifecycle only; IAT owns first/status2 and revisions."""

    set_completed_callback = None

    def __init__(self, config: XfyunConfig, key: str, **policy) -> None:
        super().__init__(config, key, **policy)
        self._app_id = ""
        self._first_frame = True
        self._pieces: dict[int, str] = {}
        self._seen: dict[int, tuple] = {}
        self._sid = None
        self._sequence_base: int | None = None

    async def _open(self) -> None:
        bundle = credential_bundle(self._key, FIELDS)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", bundle["app_id"]):
            raise ProviderError("credentials")
        self._app_id = bundle["app_id"]
        await open_socket(self, signed_url(self.config.endpoint, bundle))
        self._ready.set_result(None)  # IAT config is carried by the first audio frame.

    def feed_nowait(self, pcm: bytes) -> None:
        if isinstance(pcm, bytes) and self._audio_bytes + len(pcm) > 60 * 32000:
            self._fail("audio")
            raise ProviderError("audio")
        super().feed_nowait(pcm)

    async def _emit_audio(self, pcm: bytes) -> None:
        data = {
            "data": {
                "status": 0 if self._first_frame else 1,
                "format": "audio/L16;rate=16000",
                "encoding": "raw",
                "audio": base64.b64encode(pcm).decode(),
            }
        }
        if self._first_frame:
            data["common"] = {"app_id": self._app_id}
            data["business"] = {
                "language": "zh_cn",
                "domain": "iat",
                "accent": "mandarin",
                "dwa": "wpgs",
            }
            self._first_frame = False
            self._app_id = ""
        await send_frame(self, data)

    async def _end_audio(self) -> None:
        await send_frame(
            self,
            {
                "data": {
                    "status": 2,
                    "format": "audio/L16;rate=16000",
                    "encoding": "raw",
                    "audio": "",
                }
            },
        )

    async def _send_audio(self) -> None:
        await paced_audio(self, 1280, self._emit_audio, self._end_audio)

    async def _event(self, event: dict) -> None:
        code, sid = event.get("code"), event.get("sid")
        if type(code) is not int:
            raise ProviderError("response")
        if code != 0:
            raise ProviderError("unavailable")
        # The provider documents sid on the first response, not every event.
        if sid is not None:
            if (
                not isinstance(sid, str)
                or not 0 < len(sid) <= 200
                or self._sid not in {None, sid}
            ):
                raise ProviderError("response")
            self._sid = sid
        elif self._sid is None:
            raise ProviderError("response")
        data = event.get("data")
        if (
            not isinstance(data, dict)
            or type(data.get("status")) is not int
            or data["status"] not in {0, 1, 2}
        ):
            raise ProviderError("response")
        result = data.get("result")
        if result is not None:
            self._revision(result)
        if data["status"] == 2:
            if not self._finish_sent:
                raise ProviderError("response")
            self._done.set_result(
                "".join(self._pieces[n] for n in sorted(self._pieces))
            )

    def _revision(self, result: dict) -> None:
        try:
            if not isinstance(result, dict):
                raise TypeError
            sn, words = result["sn"], result["ws"]
            if (
                type(sn) is not int
                or not 0 <= sn < 10000
                or not isinstance(words, list)
                or len(words) > 10000
            ):
                raise TypeError
            values = []
            for word in words:
                value = word["cw"][0]["w"]
                if not isinstance(value, str):
                    raise TypeError
                values.append(value)
            text = "".join(values)
            mode = result.get("pgs", "apd")
            span = result.get("rg", [])
            if mode not in {"apd", "rpl"}:
                raise TypeError
            if mode == "rpl" and (
                not isinstance(span, list)
                or len(span) != 2
                or any(type(n) is not int for n in span)
                or not 0 <= span[0] <= span[1] < sn
            ):
                raise TypeError
            signature = (hashlib.sha256(text.encode()).hexdigest(), mode, tuple(span))
            if sn in self._seen:
                if self._seen[sn] != signature:
                    raise TypeError
                return
            # WebSocket responses are ordered. Reject a missing/new out-of-order
            # revision rather than risk resurrecting a superseded interval.
            if self._sequence_base is None:
                if sn not in {0, 1}:
                    raise TypeError
                self._sequence_base = sn
            if sn != self._sequence_base + len(self._seen):
                raise TypeError
            if len(self._seen) >= 10000 or len(text) > 100000:
                raise TypeError
            if mode == "rpl":
                for old in list(self._pieces):
                    if span[0] <= old <= span[1]:
                        del self._pieces[old]
            self._pieces[sn] = text
            self._seen[sn] = signature
            if sum(map(len, self._pieces.values())) > 100000:
                raise TypeError
        except (KeyError, IndexError, TypeError):
            raise ProviderError("response") from None

    async def aclose(self) -> None:
        await super().aclose()
        self._app_id = ""
        self._pieces.clear()
        self._seen.clear()
