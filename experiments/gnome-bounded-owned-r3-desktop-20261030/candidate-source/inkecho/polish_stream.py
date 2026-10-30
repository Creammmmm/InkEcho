"""Bounded Chat Completions SSE, with awaited final-answer deltas only."""

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import aclosing

import httpx

from inkecho.config import Provider
from inkecho.providers import (
    ProviderClient,
    ProviderError,
    Result,
    polishing_request_body,
)

MAX_WIRE_BYTES = 2_000_000
MAX_EVENT_BYTES = 262_144
MAX_TEXT_CHARACTERS = 200_000
_NEWLINE = re.compile(rb"\r\n|\r|\n")


class _Events:
    """Parse SSE framing before strict UTF-8 decoding, including split CRLF."""

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.data: list[bytes] = []
        self.event_size = 0
        self.total = 0
        self.first_line = True

    def _line(self, line: bytes) -> str | None:
        if self.first_line:
            line = line.removeprefix(b"\xef\xbb\xbf")
            self.first_line = False
        # Invalid UTF-8 is rejected even in comments/unknown SSE fields.
        try:
            line.decode("utf-8", errors="strict")
        except UnicodeError:
            raise ProviderError("response") from None
        if not line:
            if not self.data:
                return None
            payload = b"\n".join(self.data).decode("utf-8", errors="strict")
            self.data.clear()
            self.event_size = 0
            return payload
        field, _, value = line.partition(b":")
        if field == b"data":
            value = value.removeprefix(b" ")
            self.event_size += len(value) + 1
            if self.event_size > MAX_EVENT_BYTES:
                raise ProviderError("response")
            self.data.append(value)
        return None

    def feed(self, chunk: bytes, *, eof: bool = False) -> Iterator[str]:
        self.total += len(chunk)
        if self.total > MAX_WIRE_BYTES:
            raise ProviderError("response")
        self.buffer.extend(chunk)
        while match := _NEWLINE.search(self.buffer):
            # A trailing CR may be the first half of CRLF in the next chunk.
            if not eof and match[0] == b"\r" and match.end() == len(self.buffer):
                break
            if match.start() > MAX_EVENT_BYTES:
                raise ProviderError("response")
            line = bytes(self.buffer[: match.start()])
            del self.buffer[: match.end()]
            payload = self._line(line)
            if payload is not None:
                yield payload
        if len(self.buffer) > MAX_EVENT_BYTES:
            raise ProviderError("response")
        # Incomplete events at EOF are not dispatched, as required by SSE.


class _Chat:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.characters = 0
        self.finished = False
        self.done = False
        self.visible_started = False
        self.identifier: str | None = None
        self.usage: dict | None = None

    def receive(self, payload: str) -> str | None:
        if self.done:
            raise ProviderError("response")
        if payload == "[DONE]":
            if not self.finished:
                raise ProviderError("response")
            self.done = True
            return None
        try:
            item = json.loads(payload)
        except (ValueError, UnicodeError):
            raise ProviderError("response") from None
        if not isinstance(item, dict) or "error" in item:
            raise ProviderError("response")
        identifier = item.get("id")
        if identifier is not None:
            if not isinstance(identifier, str) or not identifier:
                raise ProviderError("response")
            if self.identifier is not None and identifier != self.identifier:
                raise ProviderError("response")
            self.identifier = identifier
        choices = item.get("choices")
        if not isinstance(choices, list) or len(choices) > 1:
            raise ProviderError("response")
        usage = item.get("usage")
        if usage is not None:
            if not isinstance(usage, dict):
                raise ProviderError("response")
            self.usage = usage
        if not choices:
            # Some compatible endpoints send a separate trailing usage event.
            if usage is None or not self.finished:
                raise ProviderError("response")
            return None
        if self.finished:
            raise ProviderError("response")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ProviderError("response")
        index = choice.get("index", 0)
        if type(index) is not int or index != 0:
            raise ProviderError("response")
        delta = choice.get("delta")
        if not isinstance(delta, dict):
            raise ProviderError("response")
        if delta.get("tool_calls") or delta.get("function_call"):
            raise ProviderError("response")
        content = delta.get("content")
        if content is not None and not isinstance(content, str):
            raise ProviderError("response")
        finish = choice.get("finish_reason")
        if finish is not None:
            if finish != "stop":
                raise ProviderError("response")
            self.finished = True
        if content:
            if any(0xD800 <= ord(char) <= 0xDFFF for char in content):
                raise ProviderError("response")
            self.characters += len(content)
            if self.characters > MAX_TEXT_CHARACTERS:
                raise ProviderError("response")
            self.parts.append(content)
            if not self.visible_started:
                if not content.strip():
                    return None
                self.visible_started = True
                return "".join(self.parts)
            return content
        return None


async def polish_stream(
    client: ProviderClient,
    provider: Provider,
    key: str,
    text: str,
    prompt: str,
    on_delta: Callable[[str], Awaitable[None]],
) -> Result:
    """One SSE request with whole-operation timeout, no retries or reconnects."""
    client._validate(provider, key)
    body = polishing_request_body(provider, text, prompt, stream=True)
    http = client._http_client()
    started = time.monotonic()
    events, chat = _Events(), _Chat()

    async def consume(payload: str) -> None:
        delta = chat.receive(payload)
        if delta is not None:
            # Deliver cancellation already scheduled at a network boundary before
            # invoking a callback that might complete without yielding itself.
            await asyncio.sleep(0)
            await on_delta(delta)

    try:
        async with asyncio.timeout(client.timeout_seconds):
            async with http.stream(
                "POST",
                f"{provider.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Accept": "text/event-stream",
                },
                json=body,
                timeout=client.timeout_seconds,
                follow_redirects=False,
            ) as response:
                client._check_status(response.status_code)
                content_type = response.headers.get("content-type", "")
                if content_type.split(";", 1)[0].strip().lower() != "text/event-stream":
                    raise ProviderError("response")
                async with aclosing(response.aiter_bytes()) as chunks:
                    async for chunk in chunks:
                        for payload in events.feed(chunk):
                            await consume(payload)
                            if chat.done:
                                # DONE terminates this protocol. Do not wait for an
                                # HTTP peer that keeps the response open afterward.
                                return client._text_result(
                                    "".join(chat.parts), chat.usage, started
                                )
                for payload in events.feed(b"", eof=True):
                    await consume(payload)
                    if chat.done:
                        return client._text_result(
                            "".join(chat.parts), chat.usage, started
                        )
                raise ProviderError("response")
    except (TimeoutError, httpx.TimeoutException):
        raise ProviderError("timeout") from None
    except httpx.HTTPError:
        raise ProviderError("network") from None
