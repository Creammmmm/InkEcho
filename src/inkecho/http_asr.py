"""Independent synchronous-file ASR wire formats, using the shared async pool."""

import asyncio
import base64
import io
import json
import time
import wave

import httpx

from inkecho.config import Provider
from inkecho.provider_credentials import decode_credentials
from inkecho.providers import ProviderClient, ProviderError, Result
from inkecho.security import CredentialError


def validate_audio(audio: bytes) -> None:
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
    except (wave.Error, EOFError, ValueError):
        raise ProviderError("audio") from None


async def transcribe(
    client: ProviderClient, provider: Provider, secret: str, audio: bytes
) -> Result:
    """Send one billable POST only, with bounded response and cancellation."""
    validate_audio(audio)
    try:
        key = decode_credentials(secret, ("api_key",))["api_key"]
    except CredentialError:
        raise ProviderError("credentials") from None
    started = time.monotonic()
    if provider.adapter == "openrouter-asr":
        if set(provider.parameters) - {"language", "temperature"}:
            raise ProviderError("configuration")
        body = {
            "model": provider.model,
            "input_audio": {"data": base64.b64encode(audio).decode(), "format": "wav"},
            "response_format": "json",
            **provider.parameters,
        }
        data = await client._request(provider, key, "audio/transcriptions", body)
        return client._text_result(data.get("text"), data.get("usage"), started)
    if provider.adapter == "mimo-asr":
        if set(provider.parameters) - {"asr_options"}:
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
        return client._result(
            await client._request(provider, key, "chat/completions", body), started
        )
    eleven = provider.adapter == "elevenlabs"
    allowed = {"language_code"} if eleven else {"language", "prompt", "temperature"}
    if set(provider.parameters) - allowed or any(
        type(v) not in {str, int, float} for v in provider.parameters.values()
    ):
        raise ProviderError("configuration")
    fields = {"model_id" if eleven else "model": provider.model, **provider.parameters}
    if not eleven:
        fields["response_format"] = "json"
    headers = {"xi-api-key": key} if eleven else {"Authorization": f"Bearer {key}"}
    path = "speech-to-text" if eleven else "audio/transcriptions"
    try:
        async with asyncio.timeout(client.timeout_seconds):
            async with client._http_client().stream(
                "POST",
                f"{provider.base_url.rstrip('/')}/{path}",
                headers=headers,
                data={k: str(v) for k, v in fields.items()},
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
