"""Qwen's explicit WebSocket ASR protocol; no speculative HTTP compatibility."""

import asyncio
import base64
import contextlib
import json
import logging
import re
import ssl
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

from inkecho.config import Provider
from inkecho.providers import ProviderError, Result, Usage

CHUNK_BYTES = 3200  # 100 ms of mono 16-bit little-endian PCM at 16 kHz.
QUEUE_CHUNKS = 20
MAX_FEED_BYTES = 32000
PROTOCOL = "qwen_realtime"
# Protocol diagnostics can include Authorization or audio at DEBUG level.
WIRE_LOGGER = logging.Logger("inkecho.realtime.wire")
WIRE_LOGGER.disabled = True


def _socket_url(endpoint: str, model: str) -> str:
    try:
        if not isinstance(endpoint, str):
            raise ValueError
        url = urlsplit(endpoint)
        if (
            url.scheme != "wss"
            or not url.hostname
            or url.username
            or url.password
            or url.fragment
            or not url.path
            or any(ord(char) <= 32 for char in endpoint)
        ):
            raise ValueError
        _ = url.port  # Validate the port without exposing invalid input.
        query = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True)
        if query and query != [("model", model)]:
            raise ValueError
        return urlunsplit(
            (url.scheme, url.netloc, url.path, urlencode({"model": model}), "")
        )
    except (ValueError, TypeError):
        raise ProviderError("configuration") from None


def _official_endpoint(endpoint: str) -> bool:
    """Recognize standard Qwen realtime URLs, including saved explicit URLs."""
    try:
        url = urlsplit(endpoint)
        host = url.hostname or ""
        official = host in {
            "dashscope.aliyuncs.com",
            "dashscope-intl.aliyuncs.com",
        } or bool(
            re.fullmatch(
                r"[A-Za-z0-9-]+\.(cn-beijing|ap-southeast-1)\.maas\.aliyuncs\.com",
                host,
            )
        )
        return bool(
            official
            and url.scheme == "wss"
            and url.path == "/api-ws/v1/realtime"
            and url.port in (None, 443)
            and not url.username
            and not url.password
            and not url.fragment
        )
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class RealtimeConfig:
    endpoint: str
    model: str
    sample_rate: int = 16000
    server_vad: bool = False

    def __post_init__(self):
        if (
            type(self.server_vad) is not bool
            or type(self.sample_rate) is not int
            or self.sample_rate != 16000
            or not isinstance(self.model, str)
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", self.model)
        ):
            raise ProviderError("configuration")
        _socket_url(self.endpoint, self.model)

    @property
    def url(self) -> str:
        return _socket_url(self.endpoint, self.model)

    @classmethod
    def from_provider(cls, provider: Provider, *, sample_rate: int = 16000):
        """Require a selected protocol; custom HTTP gateways need an explicit URL."""
        if (
            provider.role != "transcription"
            or provider.parameters.get("asr_protocol") != PROTOCOL
            or set(provider.parameters)
            - {"asr_protocol", "realtime_url", "turn_detection"}
        ):
            raise ProviderError("configuration")
        mode = provider.parameters.get("turn_detection")
        if mode not in (None, "manual", "server_vad"):
            raise ProviderError("configuration")
        endpoint = provider.parameters.get("realtime_url")
        if endpoint is None:
            url = urlsplit(provider.base_url)
            host = url.hostname or ""
            official = host in {
                "dashscope.aliyuncs.com",
                "dashscope-intl.aliyuncs.com",
            } or re.fullmatch(
                r"[A-Za-z0-9-]+\.(cn-beijing|ap-southeast-1)\.maas\.aliyuncs\.com",
                host,
            )
            if (
                not official
                or url.scheme != "https"
                or url.username
                or url.password
                or url.query
                or url.fragment
                or url.port not in (None, 443)
            ):
                raise ProviderError("configuration")
            endpoint = f"wss://{host}/api-ws/v1/realtime"
        if not isinstance(endpoint, str):
            raise ProviderError("configuration")
        return cls(
            endpoint,
            provider.model.strip(),
            sample_rate,
            server_vad=mode == "server_vad"
            or (mode is None and _official_endpoint(endpoint)),
        )


class _DirectConnect(connect):
    def process_redirect(self, exc):
        # Never carry the credential header into a redirected connection.
        return exc


class QwenRealtimeSession:
    """One connection, one manually committed utterance, final text only.

    feed_nowait is safe from an event-loop-owned Qt readyRead slot, including
    while start connects. It never blocks or silently drops a full queue.
    All calls must use the same event loop; this is not a thread-safe recorder.
    """

    def __init__(
        self,
        config: RealtimeConfig,
        key: str,
        *,
        timeout_seconds: float = 30,
        deadline: float | None = None,
        active: Callable[[], bool] = lambda: True,
        tls_context: ssl.SSLContext | None = None,
    ) -> None:
        if not key.strip() or "\n" in key or "\r" in key:
            raise ProviderError("credentials")
        if not 0.05 <= timeout_seconds <= 120:
            raise ProviderError("configuration")
        if tls_context is not None and (
            not tls_context.check_hostname
            or tls_context.verify_mode != ssl.CERT_REQUIRED
        ):
            raise ProviderError("configuration")
        self.config = config
        self._key = key
        self.timeout_seconds = timeout_seconds
        self.deadline = deadline
        self.active = active
        self._tls_context = tls_context or ssl.create_default_context()
        self._queue: asyncio.Queue[bytes | None] = asyncio.Queue(QUEUE_CHUNKS)
        self._tail = bytearray()
        self._socket = None
        self._tasks: list[asyncio.Task] = []
        self._failure: asyncio.Future | None = None
        self._failure_code: str | None = None
        self._ready: asyncio.Future | None = None
        self._done: asyncio.Future | None = None
        self._session_id: str | None = None
        self._item_id: str | None = None
        self._transcript: str | None = None
        self._on_completed: Callable[[Result], None] | None = None
        self._on_preview: Callable[[str], None] | None = None
        self._event_ids: set[str] = set()
        self._started = False
        self._finishing = False
        self._finish_sent = False
        self._commit_sent = False
        self._commit_acknowledged = False
        self._manual_update_sent = False
        self._closed = False
        self._audio_bytes = 0
        self._began = 0.0
        self._feed_lock = asyncio.Lock()

    def set_completed_callback(self, callback: Callable[[Result], None]) -> None:
        """Observe one validated final utterance; finish still confirms closure."""
        if self._started or self._closed or not callable(callback):
            raise ProviderError("configuration")
        self._on_completed = callback

    def set_preview_callback(self, callback: Callable[[str], None]) -> None:
        """Observe RAM-only drafts; never contributes to completed/final results."""
        if self._started or self._closed or not callable(callback):
            raise ProviderError("configuration")
        self._on_preview = callback

    def _check(self) -> None:
        if self._closed or not self.active():
            self._fail("cancelled")
            raise asyncio.CancelledError
        if self.deadline is not None and time.monotonic() >= self.deadline:
            self._fail("timeout")
            raise ProviderError("timeout")
        if self._failure_code is not None:
            code = self._failure_code
            if code == "cancelled":
                raise asyncio.CancelledError
            raise ProviderError(code)

    def _fail(self, code: str) -> None:
        if self._failure_code is None:
            self._failure_code = code
        if self._failure is not None and not self._failure.done():
            self._failure.set_result(code)
        self._tail.clear()
        while not self._queue.empty():
            self._queue.get_nowait()
        current = asyncio.current_task()
        for task in self._tasks:
            if task is not current:
                task.cancel()
        if self._socket is not None:
            self._socket.transport.abort()

    async def _wait(self, operation: Awaitable, *, timeout: float | None = None):
        task = asyncio.ensure_future(operation)
        try:
            self._check()
            pending = {task}
            if self._failure is not None:
                pending.add(self._failure)
            done, _ = await asyncio.wait(
                pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            self._check()
            if task not in done:
                self._fail("timeout")
                raise ProviderError("timeout")
            return task.result()
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

    async def start(self) -> None:
        if self._started or self._closed:
            raise ProviderError("configuration")
        self._started = True
        self._began = time.monotonic()
        loop = asyncio.get_running_loop()
        self._failure = loop.create_future()
        self._ready = loop.create_future()
        self._done = loop.create_future()
        self._tasks.append(asyncio.create_task(self._watch()))
        try:
            await self._wait(self._open(), timeout=self.timeout_seconds)
            self._key = ""
            self._tasks.append(asyncio.create_task(self._receive()))
            await self._wait(asyncio.shield(self._ready), timeout=self.timeout_seconds)
            self._tasks.append(asyncio.create_task(self._send_audio()))
        except BaseException as error:
            await self.aclose()
            if isinstance(error, (asyncio.CancelledError, ProviderError)):
                raise
            if isinstance(error, InvalidStatus):
                status = error.response.status_code
                code = "authentication" if status in (401, 403) else "network"
                raise ProviderError(code) from None
            raise ProviderError("network") from None

    async def _open(self) -> None:
        # Register ownership before the caller's post-await stale-task check.
        self._socket = await _DirectConnect(
            self.config.url,
            additional_headers={"Authorization": f"Bearer {self._key}"},
            ssl=self._tls_context,
            proxy=None,
            compression=None,
            open_timeout=self.timeout_seconds,
            close_timeout=1,
            max_size=1024 * 1024,
            max_queue=8,
            write_limit=32768,
            logger=WIRE_LOGGER,
        )

    async def _watch(self) -> None:
        try:
            while True:
                self._check()
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            return
        except ProviderError:
            return

    async def wait_failure(self) -> None:
        """Observe recording-time transport failure without cancelling its state.

        Intentional close or stale task ownership raises CancelledError. A monitor
        being cancelled does not cancel the shared failure future or the socket.
        """
        self._check()
        if self._failure is None:
            raise ProviderError("configuration")
        await asyncio.shield(self._failure)
        self._check()

    async def _send(self, event_type: str, **body) -> None:
        self._check()
        await self._wait(
            self._socket.send(
                json.dumps({"event_id": uuid.uuid4().hex, "type": event_type, **body})
            ),
            timeout=self.timeout_seconds,
        )
        self._check()

    def feed_nowait(self, pcm: bytes) -> None:
        self._check()
        if self._finishing or not isinstance(pcm, bytes) or len(pcm) % 2:
            self._fail("audio")
            raise ProviderError("audio")
        chunks = (len(self._tail) + len(pcm)) // CHUNK_BYTES
        if len(pcm) > MAX_FEED_BYTES or chunks > QUEUE_CHUNKS - self._queue.qsize():
            self._fail("unavailable")
            raise ProviderError("unavailable")
        self._tail.extend(pcm)
        self._audio_bytes += len(pcm)
        while len(self._tail) >= CHUNK_BYTES:
            self._queue.put_nowait(bytes(self._tail[:CHUNK_BYTES]))
            del self._tail[:CHUNK_BYTES]

    async def feed(self, pcm: bytes) -> None:
        """Async producers receive bounded backpressure, with no frame retry."""
        try:
            async with asyncio.timeout(self.timeout_seconds):
                await self._feed(pcm)
        except TimeoutError:
            self._fail("timeout")
            raise ProviderError("timeout") from None
        except asyncio.CancelledError:
            await self.aclose()
            raise

    async def _feed(self, pcm: bytes) -> None:
        async with self._feed_lock:
            if not isinstance(pcm, bytes) or len(pcm) % 2 or len(pcm) > MAX_FEED_BYTES:
                self._fail("audio")
                raise ProviderError("audio")
            for offset in range(0, len(pcm), CHUNK_BYTES):
                piece = pcm[offset : offset + CHUNK_BYTES]
                self._check()
                if self._finishing:
                    raise ProviderError("audio")
                if len(self._tail) + len(piece) >= CHUNK_BYTES:
                    while self._queue.full():
                        await self._wait(
                            asyncio.sleep(0.01), timeout=self.timeout_seconds
                        )
                self.feed_nowait(piece)

    async def _send_audio(self) -> None:
        try:
            while True:
                chunk = await self._queue.get()
                self._check()
                if chunk is None:
                    self._commit_sent = True
                    await self._send("input_audio_buffer.commit")
                    self._finish_sent = True
                    await self._send("session.finish")
                    return
                await self._send(
                    "input_audio_buffer.append",
                    audio=base64.b64encode(chunk).decode("ascii"),
                )
        except asyncio.CancelledError:
            return
        except ProviderError as error:
            self._fail(error.code)
        except Exception:
            self._fail("network")

    async def finish(self) -> Result:
        self._check()
        if not self._started or self._finishing:
            raise ProviderError("configuration")
        self._finishing = True
        try:
            async with asyncio.timeout(self.timeout_seconds):
                await self._wait(asyncio.shield(self._ready))
                if self._audio_bytes == 0:
                    raise ProviderError("audio")
                if self._tail:
                    await self._wait(self._queue.put(bytes(self._tail)))
                    self._tail.clear()
                await self._wait(self._queue.put(None))
                text = await self._wait(asyncio.shield(self._done))
                self._check()
                if not text.strip():
                    raise ProviderError("empty")
                return Result(text, Usage(), time.monotonic() - self._began)
        except TimeoutError:
            raise ProviderError("timeout") from None
        finally:
            await self.aclose()

    async def _receive(self) -> None:
        try:
            async for message in self._socket:
                self._check()
                if not isinstance(message, str):
                    raise ProviderError("response")
                event = json.loads(message)
                if not isinstance(event, dict):
                    raise ProviderError("response")
                await self._event(event)
                if self._done.done():
                    return
            if not self._done.done():
                self._fail("network")
        except asyncio.CancelledError:
            return
        except ProviderError as error:
            self._fail(error.code)
        except Exception:
            self._fail("response")

    async def _event(self, event: dict) -> None:
        kind = event.get("type")
        event_id = event.get("event_id")
        # Events without an ID exist in the documented item.failed response.
        if event_id is not None:
            if not isinstance(event_id, str) or not event_id or len(event_id) > 200:
                raise ProviderError("response")
            if event_id in self._event_ids:
                raise ProviderError("response")
            if len(self._event_ids) >= 10000:
                raise ProviderError("response")
            self._event_ids.add(event_id)
        if kind == "error":
            raise ProviderError("unavailable")
        if kind in {"session.created", "session.updated"}:
            session = event.get("session")
            if (
                not isinstance(session, dict)
                or session.get("model") != self.config.model
            ):
                raise ProviderError("response")
            session_id = session.get("id")
            if not isinstance(session_id, str) or not session_id:
                raise ProviderError("response")
            if kind == "session.created":
                if self._session_id is not None:
                    raise ProviderError("response")
                self._session_id = session_id
                await self._send(
                    "session.update",
                    session={
                        "input_audio_format": "pcm",
                        "sample_rate": 16000,
                        "input_audio_transcription": {},
                        "turn_detection": None,
                    },
                )
                self._manual_update_sent = True
            else:
                # Official manual-mode confirmations can omit this field.
                # Accept that only after sending our explicit null update.
                if (
                    not self._manual_update_sent
                    or self._session_id != session_id
                    or self._ready.done()
                    or session.get("turn_detection") is not None
                    or session.get("sample_rate", 16000) != 16000
                    or session.get("input_audio_format") not in {"pcm", "pcm16"}
                ):
                    raise ProviderError("response")
                self._ready.set_result(None)
            return
        if self._ready is None or not self._ready.done():
            raise ProviderError("response")
        if kind == "input_audio_buffer.committed":
            if not self._commit_sent:
                raise ProviderError("response")
            self._bind_item_id(event)
            self._commit_acknowledged = True
        elif kind == "conversation.item.created":
            item = event.get("item")
            if not isinstance(item, dict) or item.get("type") != "message":
                raise ProviderError("response")
            # The service can announce a placeholder before manual commit.
            # Its contents and identity are not authoritative recognition data.
        elif kind == "conversation.item.input_audio_transcription.text":
            # Optional previews are replaceable snapshots, not committed content.
            # Malformed drafts are ignored without weakening final validation.
            text, stash = event.get("text", ""), event.get("stash", "")
            if (
                isinstance(text, str)
                and isinstance(stash, str)
                and len(text) + len(stash) <= 100000
                and (
                    "content_index" not in event
                    or (
                        type(event["content_index"]) is int
                        and event["content_index"] == 0
                    )
                )
                and not self._closed
                and self._failure_code is None
                and self._transcript is None
                and self.active()
                and self._on_preview is not None
            ):
                self._on_preview(text + stash)
            return  # Previews never contribute to the final result.
        elif kind in {
            "conversation.item.input_audio_transcription.completed",
            "conversation.item.input_audio_transcription.failed",
        }:
            if (
                not self._commit_sent
                or not self._commit_acknowledged
                or (
                    "content_index" in event
                    and (
                        type(event["content_index"]) is not int
                        or event["content_index"] != 0
                    )
                )
            ):
                raise ProviderError("response")
            self._bind_item_id(event)
            if kind.endswith(".failed"):
                raise ProviderError("unavailable")
            if kind.endswith(".completed"):
                text = event.get("transcript")
                if not isinstance(text, str) or len(text) > 100000:
                    raise ProviderError("response")
                if self._transcript is not None and self._transcript != text:
                    raise ProviderError("response")
                first = self._transcript is None
                self._transcript = text
                if first and text.strip() and self._on_completed is not None:
                    callback, self._on_completed = self._on_completed, None
                    callback(Result(text, Usage(), time.monotonic() - self._began))
            # Partial text is deliberately never delivered or used as final text.
        elif kind == "session.finished":
            if not self._finish_sent or not self._commit_acknowledged:
                raise ProviderError("response")
            self._done.set_result(self._transcript or "")
        else:
            raise ProviderError("response")

    def _bind_item_id(self, event: dict) -> None:
        # One connection carries one manual commit; optional service IDs add
        # consistency checks but never replace this session's task ownership.
        item = event.get("item_id")
        if item is None:
            return
        if (
            not isinstance(item, str)
            or not 0 < len(item) <= 200
            or (self._item_id is not None and self._item_id != item)
        ):
            raise ProviderError("response")
        self._item_id = item

    async def aclose(self) -> None:
        """Cancel without commit, retries, partial fallback, or remaining audio."""
        self._closed = True
        self._key = ""
        self._fail("cancelled")
        for task in self._tasks:
            if task is not asyncio.current_task():
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        if self._socket is not None:
            with contextlib.suppress(Exception):
                await self._socket.close()
        self._transcript = None
        self._on_completed = None
        self._on_preview = None
        self._event_ids.clear()
