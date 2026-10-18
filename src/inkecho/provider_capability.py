"""Explicit realtime capability tests with completed synthetic or sampled WAVs."""

import asyncio
import io
import struct
import time
import wave

from inkecho.config import Provider
from inkecho.providers import ProviderClient, ProviderError, Result
from inkecho.realtime import MAX_FEED_BYTES, QwenRealtimeSession


async def realtime_capability(
    provider: Provider, key: str, audio: bytes, *, timeout_seconds: float
) -> Result:
    """Validate a completed 16 kHz mono PCM WAV, then use the real WSS adapter.

    This test does not inject text and is not proof of live microphone streaming.
    """
    ProviderClient._validate(provider, key)
    if provider.role != "transcription":
        raise ProviderError("configuration")
    from inkecho.asr_streaming import create_streaming_session, streaming_config

    config = streaming_config(provider)
    if not isinstance(audio, bytes) or not audio or len(audio) > 7_499_970:
        raise ProviderError("audio")
    try:
        with wave.open(io.BytesIO(audio), "rb") as recording:
            if (
                recording.getnchannels() != 1
                or recording.getsampwidth() != 2
                or recording.getcomptype() != "NONE"
                or recording.getframerate() != 16000
                or not 0 < recording.getnframes() <= 16000 * 300
            ):
                raise ProviderError("audio")
            # Reading one extra frame reveals an incomplete trailing 16-bit
            # sample, which getnframes() otherwise rounds down silently.
            pcm = recording.readframes(recording.getnframes() + 1)
            if len(pcm) != recording.getnframes() * 2:
                raise ProviderError("audio")
    except (wave.Error, EOFError, ValueError, TypeError, struct.error):
        raise ProviderError("audio") from None
    deadline = time.monotonic() + timeout_seconds
    connection = create_streaming_session(
        provider,
        config,
        key,
        qwen_factory=QwenRealtimeSession,
        timeout_seconds=timeout_seconds,
        deadline=deadline,
    )
    try:
        async with asyncio.timeout(timeout_seconds):
            await connection.start()
            for offset in range(0, len(pcm), MAX_FEED_BYTES):
                await connection.feed(pcm[offset : offset + MAX_FEED_BYTES])
            return await connection.finish()
    except TimeoutError:
        raise ProviderError("timeout") from None
    finally:
        await connection.aclose()
