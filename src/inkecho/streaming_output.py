"""Bounded, serial incremental output; Unicode offsets never identify content."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from inkecho.platform.keyboard import KeyboardError
from inkecho.providers import ProviderError

CHUNK_CHARACTERS = 128
QUEUE_CHUNKS = 32
MAX_TEXT_CHARACTERS = 128_000


@dataclass(frozen=True)
class TextDelta:
    offset: int
    text: str = field(repr=False)


class StreamingOutput:
    """One producer and one consumer, with explicit final-prefix reconciliation.

    Offsets count Python Unicode codepoints in the original provider text, before
    CRLF normalization. Equal text at a new offset is intentional repetition.
    Caller supervises producer/consumer together and cancels the other on error.
    No failed or uncertain dispatch is retried.
    """

    def __init__(
        self,
        send: Callable[[str], Awaitable[int]],
        active: Callable[[], bool],
    ) -> None:
        self._send = send
        self._active = active
        self._queue: asyncio.Queue[TextDelta | None] = asyncio.Queue(QUEUE_CHUNKS)
        self._text = ""
        self._pending_cr = False
        self._leading = ""
        self._has_nonblank = False
        self._queued_characters = 0
        self._consumed_characters = 0
        self._finishing = False
        self._closed = False
        self.attempted = False
        self.sent_characters = 0

    def _check(self) -> None:
        if self._closed or not self._active():
            raise asyncio.CancelledError

    async def _enqueue(self, text: str) -> None:
        for offset in range(0, len(text), CHUNK_CHARACTERS):
            self._check()
            chunk = text[offset : offset + CHUNK_CHARACTERS]
            await self._queue.put(TextDelta(self._queued_characters, chunk))
            self._check()
            self._queued_characters += len(chunk)

    async def append(self, delta: TextDelta) -> None:
        self._check()
        if (
            self._finishing
            or type(delta.offset) is not int
            or not 0 <= delta.offset <= len(self._text)
            or not isinstance(delta.text, str)
            or any(
                (ord(char) < 32 and char not in "\r\n")
                or 0x7F <= ord(char) <= 0x9F
                or 0xD800 <= ord(char) <= 0xDFFF
                for char in delta.text
            )
        ):
            raise ProviderError("response")
        overlap = min(len(self._text) - delta.offset, len(delta.text))
        if delta.text[:overlap] != self._text[delta.offset : delta.offset + overlap]:
            raise ProviderError("response")
        fresh = delta.text[overlap:]
        if not fresh:
            return
        if len(self._text) + len(fresh) > MAX_TEXT_CHARACTERS:
            raise ProviderError("response")
        self._text += fresh
        raw = ("\r" if self._pending_cr else "") + fresh
        self._pending_cr = raw.endswith("\r")
        if self._pending_cr:
            raw = raw[:-1]
        normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
        if not self._has_nonblank:
            self._leading += normalized
            if not self._leading.strip():
                if len(self._leading) > CHUNK_CHARACTERS * QUEUE_CHUNKS:
                    raise ProviderError("response")
                return
            self._has_nonblank = True
            normalized, self._leading = self._leading, ""
        await self._enqueue(normalized)

    async def finish(self, final_text: str) -> None:
        """Queue only a verified final suffix and flush a pending CR once."""
        self._check()
        if (
            self._finishing
            or not isinstance(final_text, str)
            or not final_text.startswith(self._text)
        ):
            raise ProviderError("response")
        if not final_text.strip():
            raise ProviderError("empty")
        await self.append(TextDelta(len(self._text), final_text[len(self._text) :]))
        self._check()
        if self._pending_cr:
            self._pending_cr = False
            await self._enqueue("\n")
        self._finishing = True
        await self._queue.put(None)
        self._check()

    async def run(self) -> int:
        while True:
            self._check()
            delta = await self._queue.get()
            self._check()
            if delta is None:
                return self.sent_characters
            if delta.offset != self._consumed_characters:
                raise ProviderError("response")
            self.attempted = True
            count = await self._send(delta.text)
            self._check()
            if type(count) is not int or count != len(delta.text):
                raise KeyboardError("injection_failed")
            self.sent_characters += count
            self._consumed_characters += len(delta.text)

    def close(self) -> None:
        self._closed = True
        self._text = self._leading = ""
        self._pending_cr = False
        while not self._queue.empty():
            self._queue.get_nowait()
