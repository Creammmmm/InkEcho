"""Bounded, serial incremental output; Unicode offsets never identify content."""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from inkecho.platform.keyboard import KeyboardError
from inkecho.providers import ProviderError
from inkecho.text_normalization import normalize_newlines
from inkecho.text_units import (
    FCITX_BATCH_BYTES,
    FCITX_BATCH_SCALARS,
    UNSENT_NEIGHBOR_ROUTE,
    NeighborPlanner,
)

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
        *,
        prepare=None,
        batch_enabled=None,
    ) -> None:
        self._send = send
        self._prepare = prepare
        self._batch_enabled = batch_enabled
        self._planner = None
        self._active = active
        self._queue: deque[TextDelta | None] = deque()
        self._available = asyncio.Event()
        self._space = asyncio.Event()
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

    async def _put(self, delta: TextDelta | None) -> None:
        while len(self._queue) >= QUEUE_CHUNKS:
            self._check()
            self._space.clear()
            await self._space.wait()
        self._check()
        self._queue.append(delta)
        self._available.set()

    async def _take(self) -> TextDelta | None:
        while not self._queue:
            self._check()
            self._available.clear()
            await self._available.wait()
        self._check()
        delta = self._queue.popleft()
        if delta is not None:
            parts = [delta.text]
            length = len(delta.text)
            # Inspect only queued blocks. Leave an oversized next block queued:
            # a prefetched block would exceed the 4096 queued + 128 in-flight bound.
            while self._queue and self._queue[0] is not None:
                following = self._queue[0]
                if length + len(following.text) > CHUNK_CHARACTERS:
                    break
                if following.offset != delta.offset + length:
                    raise ProviderError("response")
                parts.append(self._queue.popleft().text)
                length += len(following.text)
            delta = TextDelta(delta.offset, "".join(parts))
        self._space.set()
        return delta

    async def _enqueue(self, text: str) -> None:
        for offset in range(0, len(text), CHUNK_CHARACTERS):
            self._check()
            chunk = text[offset : offset + CHUNK_CHARACTERS]
            await self._put(TextDelta(self._queued_characters, chunk))
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
        normalized = normalize_newlines(raw)
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
        await self._put(None)
        self._check()

    async def _emit(self, text):
        if not text:
            return
        self._check()
        previously_attempted = self.attempted
        self.attempted = True
        count = await self._send(text)
        self._check()
        if count is UNSENT_NEIGHBOR_ROUTE:
            if (
                previously_attempted
                or self.sent_characters
                or self._planner is not None
                or self._batch_enabled is None
                or not self._batch_enabled()
            ):
                raise KeyboardError("injection_failed")
            # Re-plan only body proven never attempted on either route. This is
            # not a retry after unknown delivery, nor a global lookahead delay.
            self.attempted = False
            self._planner = NeighborPlanner()
            await self._emit_units(self._planner.feed(text))
            return
        if type(count) is not int or count != len(text):
            raise KeyboardError("injection_failed")
        self.sent_characters += count
        self._consumed_characters += count

    async def _emit_units(self, units):
        index = 0
        while index < len(units):
            batch = units[index]
            index += 1
            if self.sent_characters and self._batch_enabled and self._batch_enabled():
                while index < len(units):
                    candidate = batch + units[index]
                    if (
                        len(candidate) > FCITX_BATCH_SCALARS
                        or len(candidate.encode("utf-8")) > FCITX_BATCH_BYTES
                    ):
                        break
                    batch = candidate
                    index += 1
            await self._emit(batch)

    async def run(self) -> int:
        received = 0
        prepared = False
        try:
            while True:
                self._check()
                delta = await self._take()
                self._check()
                if delta is None:
                    if self._planner is not None:
                        await self._emit_units(self._planner.finish())
                    return self.sent_characters
                if delta.offset != received:
                    raise ProviderError("response")
                received += len(delta.text)
                if not prepared:
                    prepared = True
                    if self._prepare is not None:
                        enabled = await self._prepare()
                        self._check()
                        if enabled is True:
                            self._planner = NeighborPlanner()
                if self._planner is None:
                    await self._emit(delta.text)
                    continue
                await self._emit_units(self._planner.feed(delta.text))
                # A confirmed-unsent Fcitx route may hand off through existing
                # guards. Preserve order, flush its held tail once, and restore
                # ordinary chunk timing on the selected non-Fcitx route.
                if self._batch_enabled is not None and not self._batch_enabled():
                    pending = self._planner.pending
                    self._planner.cancel()
                    self._planner = None
                    await self._emit(pending)
        finally:
            if self._planner is not None:
                self._planner.cancel()

    def close(self) -> None:
        if self._planner is not None:
            self._planner.cancel()
        self._closed = True
        self._text = self._leading = ""
        self._pending_cr = False
        self._queue.clear()
        self._available.set()
        self._space.set()
