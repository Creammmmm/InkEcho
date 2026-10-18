"""Tencent ASR v2: HMAC-SHA1 query authentication and indexed final sentences."""

import base64
import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass
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

PROTOCOL = "tencent_asr"
FIELDS = ("app_id", "secret_id", "secret_key")


@dataclass(frozen=True)
class TencentConfig:
    endpoint: str
    model: str
    sample_rate: int = 16000

    def __post_init__(self) -> None:
        validate_endpoint(self.endpoint)
        if (
            not isinstance(self.model, str)
            or self.model not in {"16k_zh", "16k_en", "16k_zh_large"}
            or type(self.sample_rate) is not int
            or self.sample_rate != 16000
        ):
            raise ProviderError("configuration")

    @classmethod
    def from_provider(
        cls, provider: Provider, *, sample_rate: int = 16000
    ) -> "TencentConfig":
        if (
            provider.role != "transcription"
            or provider.adapter != "tencent-asr"
            or provider.parameters.get("asr_protocol") != PROTOCOL
            or set(provider.parameters) - {"asr_protocol", "realtime_url"}
        ):
            raise ProviderError("configuration")
        endpoint = provider.parameters.get("realtime_url")
        if endpoint is None:
            if urlsplit(provider.base_url).hostname != "asr.cloud.tencent.com":
                raise ProviderError("configuration")
            endpoint = "wss://asr.cloud.tencent.com/asr/v2"
        return cls(endpoint, provider.model, sample_rate)


def signed_url(
    config: TencentConfig,
    bundle: dict[str, str],
    voice_id: str,
    *,
    now: int | None = None,
    nonce: int | None = None,
) -> str:
    """Sign the exact sorted query before percent-encoding the signature."""
    if not bundle["app_id"].isdigit() or len(bundle["app_id"]) > 30:
        raise ProviderError("credentials")
    timestamp = int(time.time()) if now is None else now
    params = {
        "secretid": bundle["secret_id"],
        "timestamp": timestamp,
        "expired": timestamp + 600,
        "nonce": secrets.randbelow(2**31) if nonce is None else nonce,
        "engine_model_type": config.model,
        "voice_id": voice_id,
        "voice_format": 1,
        "needvad": 1,
    }
    base = config.endpoint.rstrip("/") + "/" + bundle["app_id"]
    parsed = urlsplit(base)
    canonical = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    signature = hmac.new(
        bundle["secret_key"].encode(),
        ("GET" + parsed.netloc + parsed.path + "?" + canonical).encode(),
        hashlib.sha1,
    ).digest()
    params["signature"] = base64.b64encode(signature).decode()
    return base + "?" + urlencode(params)


class TencentSession(QwenRealtimeSession):
    """One voice_id; slice_type2 text only, gated by the explicit final1 reply."""

    set_completed_callback = None

    def __init__(self, config: TencentConfig, key: str, **policy) -> None:
        super().__init__(config, key, **policy)
        self._voice_id = str(uuid.uuid4())
        self._sentences: dict[int, str] = {}
        self._pending_slices: set[int] = set()

    async def _open(self) -> None:
        bundle = credential_bundle(self._key, FIELDS)
        await open_socket(self, signed_url(self.config, bundle, self._voice_id))

    async def _emit_audio(self, pcm: bytes) -> None:
        await send_frame(self, pcm)

    async def _end_audio(self) -> None:
        await send_frame(self, {"type": "end"})

    async def _send_audio(self) -> None:
        await paced_audio(self, 1280, self._emit_audio, self._end_audio)

    async def _event(self, event: dict) -> None:
        code = event.get("code")
        if type(code) is not int:
            raise ProviderError("response")
        if code != 0:
            raise ProviderError("unavailable")
        if event.get("voice_id") != self._voice_id:
            raise ProviderError("response")
        final = event.get("final", 0)
        if type(final) is not int or final not in {0, 1}:
            raise ProviderError("response")
        result = event.get("result")
        if not self._ready.done():
            if result is not None or final:
                raise ProviderError("response")
            self._ready.set_result(None)
            return
        if result is not None:
            self._sentence(result)
        if final:
            if (
                not self._finish_sent
                or self._pending_slices
                or sorted(self._sentences) != list(range(len(self._sentences)))
            ):
                raise ProviderError("response")
            self._done.set_result(
                "".join(self._sentences[n] for n in sorted(self._sentences))
            )

    def _sentence(self, result: dict) -> None:
        if not isinstance(result, dict):
            raise ProviderError("response")
        index, kind = result.get("index"), result.get("slice_type")
        if (
            type(index) is not int
            or not 0 <= index < 10000
            or type(kind) is not int
            or kind not in {0, 1, 2}
        ):
            raise ProviderError("response")
        if kind != 2:
            self._pending_slices.add(index)
            return
        text = result.get("voice_text_str")
        if not isinstance(text, str) or len(text) > 100000:
            raise ProviderError("response")
        if index in self._sentences and self._sentences[index] != text:
            raise ProviderError("response")
        self._sentences[index] = text
        self._pending_slices.discard(index)
        if sum(map(len, self._sentences.values())) > 100000:
            raise ProviderError("response")

    async def aclose(self) -> None:
        await super().aclose()
        self._sentences.clear()
        self._pending_slices.clear()
