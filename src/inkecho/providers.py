"""Async cloud adapters with explicit audio protocol and sanitized failures."""

import asyncio
import base64
import io
import json
import re
import time
import wave
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from http.cookiejar import CookieJar, DefaultCookiePolicy
from urllib.parse import urlsplit, urlunsplit

import httpx

from inkecho.config import Provider

ERRORS = {
    "configuration": "Check the provider URL, model and request parameters.",
    "credentials": "Add an API key in the system credential store.",
    "protocol": "Choose a model for synchronous HTTP audio transcription; "
    "realtime, streaming and filetrans protocols are not implemented.",
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


def validate_provider_protocol(provider: Provider) -> None:
    """Reject known incompatible families without an allowlist of HTTP models."""
    if provider.role != "transcription" or provider.adapter != "qwen":
        return
    model = provider.model.strip().lower()
    if model.startswith(("qwen", "fun-asr")) and {
        "realtime",
        "streaming",
        "filetrans",
    }.intersection(model.split("-")):
        raise ProviderError("protocol")


def uses_dashscope_audio(model: str) -> bool:
    return (
        re.fullmatch(
            r"(?:qwen-audio-3\.\d+-asr-flash|fun-asr-flash)(?:-\d{4}-\d{2}-\d{2})?",
            model.strip().lower(),
        )
        is not None
    )


def dashscope_base_url(base_url: str) -> str:
    """Change only a recognized API suffix, preserving origin and proxy prefix."""
    try:
        url = urlsplit(base_url)
        if (
            url.scheme != "https"
            or not url.netloc
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Invalid provider URL")
        path = url.path.rstrip("/")
        if path.endswith("/compatible-mode/v1"):
            path = path.removesuffix("/compatible-mode/v1") + "/api/v1"
        elif not path.endswith("/api/v1"):
            raise ValueError("Unknown API path")
        return urlunsplit((url.scheme, url.netloc, path, "", ""))
    except ValueError:
        raise ProviderError("configuration") from None


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


def polishing_request_body(
    provider: Provider, text: str, prompt: str, *, stream: bool = False
) -> dict:
    """Build one chat request, including only verified vendor thinking controls.

    Provider IDs and model names alone cannot establish a gateway's protocol.
    Unknown origins keep ordinary chat parameters and receive no thinking flags.
    Explicit supported thinking settings take precedence over the low-latency default.
    """
    if provider.role != "polishing" or provider.adapter != "openai":
        raise ProviderError("configuration")
    if not text.strip() or not prompt.strip():
        raise ProviderError("empty")
    url = urlsplit(provider.base_url)
    control = None
    if (
        url.hostname == "api.deepseek.com"
        and url.port in {None, 443}
        and url.path.rstrip("/") in {"", "/v1"}
        and provider.model in {"deepseek-flash", "deepseek-v4-flash", "deepseek-v4-pro"}
    ):
        control = "thinking"
    # Deliberately narrow: thinking-only models and unverified future revisions
    # must not inherit controls from an arbitrary model prefix.
    qwen_models = {
        "qwen-plus",
        "qwen-plus-latest",
        "qwen-plus-2025-04-28",
        "qwen-flash",
        "qwen-flash-2025-07-28",
        "qwen3.6-plus",
        "qwen3.6-plus-2026-04-02",
    }
    qwen_host = url.hostname in {
        "dashscope.aliyuncs.com",
        "dashscope-intl.aliyuncs.com",
        "dashscope-us.aliyuncs.com",
    } or re.fullmatch(
        r"[a-z0-9-]+\.(?:cn-beijing|ap-southeast-1)\.maas\.aliyuncs\.com",
        url.hostname or "",
    )
    if (
        qwen_host
        and url.port in {None, 443}
        and url.path.rstrip("/") == "/compatible-mode/v1"
        and provider.model in qwen_models
    ):
        control = "enable_thinking"
    allowed = {
        "temperature",
        "top_p",
        "max_tokens",
        "frequency_penalty",
        "presence_penalty",
    }
    if control:
        allowed.add(control)
    if set(provider.parameters) - allowed:
        raise ProviderError("configuration")
    controls = {}
    if control == "thinking":
        value = provider.parameters.get("thinking", {"type": "disabled"})
        if (
            not isinstance(value, dict)
            or set(value) != {"type"}
            or value["type"] not in ("enabled", "disabled")
        ):
            raise ProviderError("configuration")
        controls[control] = dict(value)
    elif control == "enable_thinking":
        value = provider.parameters.get(control, False)
        if type(value) is not bool:
            raise ProviderError("configuration")
        controls[control] = value
    return {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        "stream": stream,
        **provider.parameters,
        **controls,
    }


@dataclass
class _HttpPool:
    http: httpx.AsyncClient | None = None
    external: bool = False
    closed: bool = False
    closing: asyncio.Task | None = None


class _NoCookies(DefaultCookiePolicy):
    def set_ok(self, cookie, request) -> bool:
        # HTTP API credentials are per request, never an implicit pooled session.
        return False


class ProviderClient:
    """Lifecycle-owned connection pool; injected HTTP clients remain caller-owned.

    Use one owner per application/event loop, then ``with_timeout`` for request
    policies sharing its pool. Close the owner after cancelling pending calls.
    Closing a borrowed policy never closes the shared transport.
    """

    def __init__(
        self, *, timeout_seconds: float = 30, http: httpx.AsyncClient | None = None
    ) -> None:
        if not 0.05 <= timeout_seconds <= 120:
            raise ValueError("Request timeout must be between 0.05 and 120 seconds.")
        self.timeout_seconds = timeout_seconds
        self._pool = _HttpPool(http=http, external=http is not None)
        self._owner = True

    @property
    def http(self) -> httpx.AsyncClient | None:
        return self._pool.http

    def with_timeout(self, seconds: float) -> "ProviderClient":
        """Borrow this lifecycle's pool with an independent request deadline."""
        borrowed = ProviderClient(timeout_seconds=seconds)
        borrowed._pool = self._pool
        borrowed._owner = False
        return borrowed

    def _http_client(self) -> httpx.AsyncClient:
        if self._pool.closed:
            raise ProviderError("configuration")
        if self._pool.http is None:
            self._pool.http = httpx.AsyncClient(
                verify=True,
                trust_env=False,
                follow_redirects=False,
                cookies=CookieJar(policy=_NoCookies()),
                limits=httpx.Limits(
                    max_connections=20,
                    max_keepalive_connections=10,
                    keepalive_expiry=90,
                ),
            )
        if self._pool.http.is_closed:
            raise ProviderError("configuration")
        return self._pool.http

    async def aclose(self) -> None:
        """Close an owned pool once; never close an injected HTTP transport."""
        if not self._owner:
            return
        self._pool.closed = True
        if self._pool.http is None or self._pool.external:
            return
        if self._pool.closing is None:
            self._pool.closing = asyncio.create_task(self._pool.http.aclose())
        # Cancellation of a shutdown caller must not abandon transport cleanup.
        await asyncio.shield(self._pool.closing)

    async def __aenter__(self) -> "ProviderClient":
        return self

    async def __aexit__(self, *_args) -> None:
        await self.aclose()

    @staticmethod
    def _validate(provider: Provider, key: str, *, model: bool = True) -> None:
        if not key or not key.strip() or "\n" in key or "\r" in key:
            raise ProviderError("credentials")
        if not provider.base_url or (model and not provider.model.strip()):
            raise ProviderError("configuration")
        if provider.adapter not in {"qwen", "openai"}:
            raise ProviderError("configuration")

    @staticmethod
    def _check_status(status: int) -> None:
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

    async def _request(
        self,
        provider: Provider,
        key: str,
        path: str,
        body: dict | None = None,
        *,
        headers: dict | None = None,
    ) -> dict:
        client = self._http_client()
        try:
            async with asyncio.timeout(self.timeout_seconds):
                # Only idempotent discovery retries. Never repeat a billable POST.
                for attempt in range(2 if body is None else 1):
                    async with client.stream(
                        "GET" if body is None else "POST",
                        f"{provider.base_url.rstrip('/')}/{path}",
                        headers={"Authorization": f"Bearer {key}", **(headers or {})},
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
                        self._check_status(response.status_code)
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

    @staticmethod
    def _result(data: dict, started: float) -> Result:
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ProviderError("response") from None
        return ProviderClient._text_result(text, data.get("usage"), started)

    @staticmethod
    def _text_result(text, usage, started: float) -> Result:
        if not isinstance(text, str):
            raise ProviderError("response")
        if not text.strip():
            raise ProviderError("empty")
        if not isinstance(usage, dict):
            usage = {}
        counts = [
            usage.get(key)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        ]
        counts = [n if type(n) is int and n >= 0 else None for n in counts]
        return Result(text, Usage(*counts), time.monotonic() - started)

    @staticmethod
    def _dashscope_result(data: dict, started: float) -> Result:
        output = data.get("output")
        if not isinstance(output, dict):
            raise ProviderError("response")
        text = output.get("text")
        if text is None or (isinstance(text, str) and not text.strip()):
            nested = output.get("output", output)
            sentence = nested.get("sentence") if isinstance(nested, dict) else None
            if isinstance(sentence, dict):
                text = sentence.get("text", text)
        usage = data.get("usage")
        if isinstance(usage, dict):
            usage = {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
            }
        return ProviderClient._text_result(text, usage, started)

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
        validate_provider_protocol(provider)
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
                    or wav.getframerate() <= 0
                    or len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2
                ):
                    raise ProviderError("audio")
                sample_rate = wav.getframerate()
                duration = wav.getnframes() / sample_rate
        except (wave.Error, EOFError):
            raise ProviderError("audio") from None
        dashscope = uses_dashscope_audio(provider.model)
        allowed = (
            {
                "language_hints",
                "vocabulary",
                "vocabulary_id",
                "speaker_diarization_enabled",
                "keep_dialect",
            }
            if dashscope
            else {"asr_options"}
        )
        if set(provider.parameters) - allowed:
            raise ProviderError("configuration")
        if dashscope:
            if duration > 300:
                raise ProviderError("audio")
            provider = replace(provider, base_url=dashscope_base_url(provider.base_url))
        messages = [
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
        ]
        if dashscope:
            body = {
                "model": provider.model,
                "input": {"messages": messages},
                "parameters": {
                    "format": "wav",
                    "sample_rate": str(sample_rate),
                    **provider.parameters,
                },
            }
        else:
            body = {
                "model": provider.model,
                "messages": messages,
                "stream": False,
                **provider.parameters,
            }
        started = time.monotonic()
        if dashscope:
            data = await self._request(
                provider,
                key,
                "services/aigc/multimodal-generation/generation",
                body,
                headers={"X-DashScope-SSE": "disable"},
            )
            return self._dashscope_result(data, started)
        return self._result(
            await self._request(provider, key, "chat/completions", body), started
        )

    async def polish(
        self, provider: Provider, key: str, text: str, prompt: str
    ) -> Result:
        self._validate(provider, key)
        body = polishing_request_body(provider, text, prompt)
        started = time.monotonic()
        return self._result(
            await self._request(provider, key, "chat/completions", body), started
        )

    async def polish_stream(
        self,
        provider: Provider,
        key: str,
        text: str,
        prompt: str,
        on_delta: Callable[[str], Awaitable[None]],
    ) -> Result:
        """Await each final-answer delta once; never replay a partial stream.

        The callback supplies backpressure and must enforce task authorization
        before delivery. The returned full text is for accounting, not replay.
        """
        from inkecho.polish_stream import polish_stream

        return await polish_stream(self, provider, key, text, prompt, on_delta)

    async def test_capability(
        self, provider: Provider, key: str, *, audio: bytes | None = None
    ) -> Result:
        """Explicit potentially billable request; never run automatically."""
        if provider.role == "transcription":
            validate_provider_protocol(provider)
            if audio is None:
                raise ProviderError("audio")
            return await self.transcribe(provider, key, audio)
        return await self.polish(
            provider, key, "Connection test.", "Return the input unchanged."
        )
