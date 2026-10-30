"""Independent synchronous-file ASR wire formats, using the shared async pool."""

import asyncio
import base64
import io
import json
import math
import re
import time
import wave

import httpx

from inkecho.config import Provider
from inkecho.provider_credentials import decode_credentials
from inkecho.providers import ProviderClient, ProviderError, Result
from inkecho.security import CredentialError


def validate_audio(audio: bytes) -> float:
    """Bound uploads and validate a complete mono PCM WAV before any request."""
    if not isinstance(audio, bytes) or not audio or len(audio) > 7_499_970:
        raise ProviderError("audio")
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            frames = wav.getnframes()
            if (
                wav.getnchannels() != 1
                or wav.getsampwidth() != 2
                or wav.getcomptype() != "NONE"
                or not frames
                or not wav.getframerate()
                or len(wav.readframes(frames + 1)) != frames * 2
            ):
                raise ProviderError("audio")
            return frames / wav.getframerate()
    except (wave.Error, EOFError, ValueError):
        raise ProviderError("audio") from None


async def transcribe(
    client: ProviderClient, provider: Provider, secret: str, audio: bytes
) -> Result:
    """Send one billable POST only, with bounded response and cancellation."""
    duration = validate_audio(audio)
    if provider.adapter == "zhipu-asr" and duration > 30:
        raise ProviderError("audio")
    try:
        key = decode_credentials(secret, ("api_key",))["api_key"]
    except CredentialError:
        raise ProviderError("credentials") from None
    started = time.monotonic()
    if provider.adapter in {"openrouter-asr", "zenmux-asr"}:
        allowed = (
            {"language", "temperature"}
            if provider.adapter == "openrouter-asr"
            else {"language", "enable_itn"}
        )
        if set(provider.parameters) - allowed:
            raise ProviderError("configuration")
        validate_options(provider.parameters)
        body = {
            "model": provider.model,
            "input_audio": {"data": base64.b64encode(audio).decode(), "format": "wav"},
            "response_format": "json",
            **provider.parameters,
        }
        data = await client._request(provider, key, "audio/transcriptions", body)
        return client._text_result(data.get("text"), data.get("usage"), started)
    if provider.adapter in {"mimo-asr", "orca-audio"}:
        if set(provider.parameters) - (
            {"asr_options"} if provider.adapter == "mimo-asr" else set()
        ):
            raise ProviderError("configuration")
        options = provider.parameters.get("asr_options", {})
        if (
            not isinstance(options, dict)
            or set(options) - {"language"}
            or options.get("language", "auto") not in {"auto", "zh", "en"}
        ):
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
            "asr_options": options,
        }
        if provider.adapter == "orca-audio":
            body.pop("asr_options")
            content = body["messages"][0]["content"]
            content.insert(
                0,
                {
                    "type": "text",
                    "text": (
                        "Transcribe the audio exactly. Return only the transcript, "
                        "without commentary."
                    ),
                },
            )
            content[1]["input_audio"] = {
                "data": base64.b64encode(audio).decode(),
                "format": "wav",
            }
        data = await client._request(provider, key, "chat/completions", body)
        choices = data.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices else None
        message = choice.get("message") if isinstance(choice, dict) else None
        if (
            not isinstance(message, dict)
            or choice.get("finish_reason") != "stop"
            or message.get("tool_calls")
        ):
            raise ProviderError("response")
        return client._result(data, started)
    eleven = provider.adapter == "elevenlabs"
    allowed = {
        "elevenlabs": {"language_code"},
        "stepfun-http": {"hotwords"},
        "zhipu-asr": {"prompt", "hotwords"},
        "minimax-asr": {"language"},
    }.get(provider.adapter, {"language", "prompt", "temperature"})
    if set(provider.parameters) - allowed:
        raise ProviderError("configuration")
    validate_options(provider.parameters, zhipu=provider.adapter == "zhipu-asr")
    fields = {"model_id" if eleven else "model": provider.model, **provider.parameters}
    if not eleven and provider.adapter != "zhipu-asr":
        fields["response_format"] = "json"
    headers = {"xi-api-key": key} if eleven else {"Authorization": f"Bearer {key}"}
    path = (
        "speech-to-text"
        if eleven
        else "speech_to_text"
        if provider.adapter == "minimax-asr"
        else "audio/transcriptions"
    )
    if provider.adapter == "zhipu-asr" and "hotwords" in fields:
        fields["hotwords[]"] = fields.pop("hotwords")
    if provider.adapter in {"zhipu-asr", "minimax-asr"}:
        fields["stream"] = "false"
    if provider.adapter == "minimax-asr" and "language" in fields:
        headers["language"] = fields.pop("language")
    try:
        async with asyncio.timeout(client.timeout_seconds):
            async with client._http_client().stream(
                "POST",
                f"{provider.base_url.rstrip('/')}/{path}",
                headers=headers,
                data={
                    k: [str(x) for x in v] if isinstance(v, list) else str(v)
                    for k, v in fields.items()
                },
                files={"file": ("recording.wav", audio, "audio/wav")},
                timeout=client.timeout_seconds,
                follow_redirects=False,
            ) as response:
                client._check_status(response.status_code)
                raw = bytearray()
                async for part in response.aiter_bytes():
                    raw.extend(part)
                    if len(raw) > 2_000_000:
                        raise ProviderError("response")
                try:
                    data = json.loads(raw)
                except (ValueError, UnicodeError):
                    raise ProviderError("response") from None
                if not isinstance(data, dict) or "error" in data:
                    raise ProviderError("response")
                return client._text_result(data.get("text"), data.get("usage"), started)
    except (TimeoutError, httpx.TimeoutException):
        raise ProviderError("timeout") from None
    except httpx.HTTPError:
        raise ProviderError("network") from None


def validate_options(values: dict, *, zhipu: bool = False) -> None:
    """Validate documented scalar controls before they become headers or JSON."""
    for name, value in values.items():
        if name in {"language", "language_code"}:
            if not isinstance(value, str) or not re.fullmatch(
                r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", value
            ):
                raise ProviderError("configuration")
        elif name == "temperature":
            if (
                type(value) not in {int, float}
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                raise ProviderError("configuration")
        elif name == "enable_itn":
            if type(value) is not bool:
                raise ProviderError("configuration")
        elif name == "hotwords":
            try:
                words = value if zhipu else json.loads(value)
            except (TypeError, ValueError):
                raise ProviderError("configuration") from None
            if (
                not isinstance(words, list)
                or len(words) > 100
                or any(
                    not isinstance(w, str) or not w.strip() or len(w) > 200
                    for w in words
                )
            ):
                raise ProviderError("configuration")
        elif name == "prompt":
            if not isinstance(value, str) or len(value) > 8000:
                raise ProviderError("configuration")
