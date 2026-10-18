"""Small bounded wire helpers for credentialed ASR, with no replay or logging."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from inkecho.provider_credentials import decode_credentials
from inkecho.providers import ProviderError
from inkecho.realtime import WIRE_LOGGER, _DirectConnect
from inkecho.security import CredentialError


def validate_endpoint(value: str) -> None:
    """Persist only a plain WSS endpoint, never a signed query or credentials."""
    try:
        url = urlsplit(value)
        if (
            url.scheme != "wss"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or not url.path
            or len(value) > 2000
            or any(ord(c) <= 32 for c in value)
        ):
            raise ValueError
        _ = url.port
    except (TypeError, ValueError):
        raise ProviderError("configuration") from None


def credential_bundle(value: str, fields: tuple[str, ...]) -> dict[str, str]:
    try:
        return decode_credentials(value, fields)
    except CredentialError:
        raise ProviderError("credentials") from None


async def open_socket(session, url: str, headers: dict | None = None) -> None:
    """Register a single direct socket; credentialed redirects are never followed."""
    session._socket = await _DirectConnect(
        url,
        additional_headers=headers,
        ssl=session._tls_context,
        proxy=None,
        compression=None,
        open_timeout=session.timeout_seconds,
        close_timeout=1,
        max_size=1024 * 1024,
        max_queue=8,
        write_limit=32768,
        logger=WIRE_LOGGER,
    )


async def send_frame(session, payload: bytes | dict) -> None:
    session._check()
    value = json.dumps(payload) if isinstance(payload, dict) else payload
    await session._wait(session._socket.send(value), timeout=session.timeout_seconds)
    session._check()


async def paced_audio(
    session,
    frame_bytes: int,
    emit: Callable[[bytes], Awaitable[None]],
    finish: Callable[[], Awaitable[None]],
) -> None:
    """Reframe the bounded 100ms capture queue without padding, loss or bursts."""
    tail = bytearray()

    async def send(piece):
        session._check()
        await emit(piece)
        await session._wait(
            asyncio.sleep(len(piece) / 32000), timeout=session.timeout_seconds
        )

    try:
        while True:
            chunk = await session._queue.get()
            session._check()
            if chunk is None:
                if tail:
                    await send(bytes(tail))
                    tail.clear()
                session._finish_sent = True
                await finish()
                return
            if (
                not isinstance(chunk, bytes)
                or not 0 < len(chunk) <= 3200
                or len(chunk) % 2
            ):
                raise ProviderError("audio")
            tail.extend(chunk)
            while len(tail) >= frame_bytes:
                piece = bytes(tail[:frame_bytes])
                del tail[:frame_bytes]
                await send(piece)
    except asyncio.CancelledError:
        return
    except ProviderError as error:
        session._fail(error.code)
    except Exception:
        session._fail("network")
    finally:
        tail.clear()
