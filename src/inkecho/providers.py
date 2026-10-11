"""Async cloud adapters with explicit audio protocol and sanitized failures."""

import asyncio
import base64
import io
import json
import time
import wave
from dataclasses import dataclass, field

import httpx

from inkecho.config import Provider

ERRORS = {
    "configuration": "Check the provider URL, model and request parameters.",
    "credentials": "Add an API key in the system credential store.",
    "authentication": "The service rejected the API key or account permissions.",
    "rate_limit": "The service is busy or its request quota was reached.",
    "model": "The service does not support this model or request format.",
    "unavailable": "The service is temporarily unavailable.",
    "network": "Cannot connect to the service. Check your network.",
    "timeout": "The service did not reply within the configured time limit.",
    "response": "The service returned an invalid response.",
    "empty": "The service returned no text.",
    "audio": "Provide a nonempty mono 16-bit WAV within the audio size limit.",
}


class ProviderError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(ERRORS[code])


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True)
class Result:
    text: str = field(repr=False)
    usage: Usage
    seconds: float


@dataclass(frozen=True)
class Connection:
    models: tuple[str, ...]
    capability_verified: bool = False


class ProviderClient:
    """An optional HTTP client supports testing with a trusted local TLS server."""

    def __init__(
        self, *, timeout_seconds: float = 30, http: httpx.AsyncClient | None = None
    ) -> None:
        if not 0.05 <= timeout_seconds <= 120:
            raise ValueError("Request timeout must be between 0.05 and 120 seconds.")
        self.timeout_seconds = timeout_seconds
        self.http = http

    @staticmethod
    def _validate(provider: Provider, key: str, *, model: bool = True) -> None:
        if not key or not key.strip() or "\n" in key or "\r" in key:
            raise ProviderError("credentials")
        if not provider.base_url or (model and not provider.model.strip()):
            raise ProviderError("configuration")
        if provider.adapter not in {"qwen", "openai"}:
            raise ProviderError("configuration")

    async def _request(
        self, provider: Provider, key: str, path: str, body: dict | None = None
    ) -> dict:
        client = self.http or httpx.AsyncClient(verify=True, trust_env=False)
        try:
            async with asyncio.timeout(self.timeout_seconds):
                # Only idempotent discovery retries. Never repeat a billable POST.
                for attempt in range(2 if body is None else 1):
                    async with client.stream(
                        "GET" if body is None else "POST",
                        f"{provider.base_url.rstrip('/')}/{path}",
                        headers={"Authorization": f"Bearer {key}"},
                        json=body,
                        timeout=self.timeout_seconds,
                        follow_redirects=False,
                    ) as response:
                        if (
                            body is None
                            and attempt == 0
                            and response.status_code
                            in {
                                429,
                                502,
                                503,
                                504,
                            }
                        ):
                            await asyncio.sleep(0.2)
                            continue
                        status = response.status_code
                        if status in {401, 403}:
                            raise ProviderError("authentication")
                        if status == 429:
                            raise ProviderError("rate_limit")
                        if status in {400, 404, 405, 422}:
                            raise ProviderError("model")
                        if status >= 500:
                            raise ProviderError("unavailable")
                        if status < 200 or status >= 300:
                            raise ProviderError("response")
                        data = bytearray()
                        async for chunk in response.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > 2_000_000:
                                raise ProviderError("response")
                        try:
                            result = json.loads(data)
                        except (ValueError, UnicodeError):
                            raise ProviderError("response") from None
                        if not isinstance(result, dict) or "error" in result:
                            raise ProviderError("response")
                        return result
        except (TimeoutError, httpx.TimeoutException):
            raise ProviderError("timeout") from None
        except httpx.HTTPError:
            raise ProviderError("network") from None
        finally:
            if self.http is None:
                await client.aclose()

    @staticmethod
    def _result(data: dict, started: float) -> Result:
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("response") from None
        if not isinstance(text, str):
            raise ProviderError("response")
        if not text.strip():
            raise ProviderError("empty")
        usage = data.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        counts = [
            usage.get(key)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        ]
        counts = [n if type(n) is int and n >= 0 else None for n in counts]
        return Result(text, Usage(*counts), time.monotonic() - started)

    async def models(self, provider: Provider, key: str) -> list[str]:
        self._validate(provider, key, model=False)
        result = await self._request(provider, key, "models")
        models = result.get("data")
        if not isinstance(models, list):
            raise ProviderError("response")
        return sorted(
            {
                model["id"]
                for model in models
                if isinstance(model, dict)
                and isinstance(model.get("id"), str)
                and model["id"].strip()
            }
        )

    async def check_connection(self, provider: Provider, key: str) -> Connection:
        return Connection(tuple(await self.models(provider, key)))

    async def transcribe(self, provider: Provider, key: str, audio: bytes) -> Result:
        self._validate(provider, key)
        if provider.role != "transcription" or provider.adapter != "qwen":
            raise ProviderError("configuration")
        # 10 MB encoded service limit: reject before making a larger base64 copy.
        if not audio or len(audio) > 7_499_970:
            raise ProviderError("audio")
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                if (
                    wav.getnchannels() != 1
                    or wav.getsampwidth() != 2
                    or not wav.getnframes()
                    or len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2
                ):
                    raise ProviderError("audio")
        except (wave.Error, EOFError):
            raise ProviderError("audio") from None
        if set(provider.parameters) - {"asr_options"}:
            raise ProviderError("configuration")
        body = {
            "model": provider.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": "data:audio/wav;base64,"
                                + base64.b64encode(audio).decode()
                            },
                        }
                    ],
                }
            ],
            "stream": False,
            **provider.parameters,
        }
        started = time.monotonic()
        return self._result(
            await self._request(provider, key, "chat/completions", body), started
        )

    async def polish(
        self, provider: Provider, key: str, text: str, prompt: str
    ) -> Result:
        self._validate(provider, key)
        if provider.role != "polishing" or provider.adapter != "openai":
            raise ProviderError("configuration")
        if not text.strip() or not prompt.strip():
            raise ProviderError("empty")
        allowed = {
            "temperature",
            "top_p",
            "max_tokens",
            "frequency_penalty",
            "presence_penalty",
        }
        if set(provider.parameters) - allowed:
            raise ProviderError("configuration")
        body = {
            "model": provider.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": text},
            ],
            "stream": False,
            **provider.parameters,
        }
        started = time.monotonic()
        return self._result(
            await self._request(provider, key, "chat/completions", body), started
        )

    async def test_capability(
        self, provider: Provider, key: str, *, audio: bytes | None = None
    ) -> Result:
        """Explicit potentially billable request; never run automatically."""
        if provider.role == "transcription":
            if audio is None:
                raise ProviderError("audio")
            return await self.transcribe(provider, key, audio)
        return await self.polish(
            provider, key, "Connection test.", "Return the input unchanged."
        )
