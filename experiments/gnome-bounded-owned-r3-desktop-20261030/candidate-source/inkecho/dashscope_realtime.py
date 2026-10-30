"""DashScope task WebSocket ASR: binary PCM and task completion, not Qwen events."""

import asyncio
import json
import re
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

from inkecho.config import Provider
from inkecho.providers import ProviderError
from inkecho.realtime import QwenRealtimeSession

PROTOCOL = "dashscope_task"
MODEL = re.compile(
    r"(?:fun-asr-realtime|paraformer-realtime-v2)(?:-\d{4}-\d{2}-\d{2})?"
)


@dataclass(frozen=True)
class DashscopeRealtimeConfig:
    endpoint: str
    model: str
    sample_rate: int = 16000

    def __post_init__(self) -> None:
        try:
            url = urlsplit(self.endpoint)
            if (
                url.scheme != "wss"
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
                or not url.path
                or any(ord(c) <= 32 for c in self.endpoint)
            ):
                raise ValueError
            _ = url.port
        except (ValueError, TypeError):
            raise ProviderError("configuration") from None
        if (
            type(self.sample_rate) is not int
            or self.sample_rate != 16000
            or not isinstance(self.model, str)
            or not MODEL.fullmatch(self.model)
        ):
            raise ProviderError("configuration")

    @property
    def url(self) -> str:
        return self.endpoint

    @classmethod
    def from_provider(
        cls, provider: Provider, *, sample_rate: int = 16000
    ) -> "DashscopeRealtimeConfig":
        if (
            provider.role != "transcription"
            or provider.adapter != "dashscope-ws"
            or provider.parameters.get("asr_protocol") != PROTOCOL
            or set(provider.parameters) - {"asr_protocol", "realtime_url"}
        ):
            raise ProviderError("configuration")
        endpoint = provider.parameters.get("realtime_url")
        if endpoint is None:
            base = urlsplit(provider.base_url)
            if base.hostname not in {
                "dashscope.aliyuncs.com",
                "dashscope-intl.aliyuncs.com",
            } or base.port not in {None, 443}:
                raise ProviderError("configuration")
            endpoint = f"wss://{base.hostname}/api-ws/v1/inference/"
        return cls(endpoint, provider.model, sample_rate)


class DashscopeRealtimeSession(QwenRealtimeSession):
    """Inherit only bounded connection/queue/deadline/close; own task wire events."""

    set_completed_callback = None

    def __init__(self, config: DashscopeRealtimeConfig, key: str, **policy) -> None:
        super().__init__(config, key, **policy)
        self._task_id = str(uuid.uuid4())
        self._sentences: dict[int, tuple[int, str]] = {}
        self._sentence_chars = 0
        self._pending_sentences: set[int] = set()

    async def _open(self) -> None:
        await super()._open()
        await self._send_task(
            "run-task",
            {
                "task_group": "audio",
                "task": "asr",
                "function": "recognition",
                "model": self.config.model,
                "parameters": {"format": "pcm", "sample_rate": 16000},
                "input": {},
            },
        )

    async def _send_task(self, action: str, payload: dict) -> None:
        self._check()
        body = {
            "header": {
                "action": action,
                "task_id": self._task_id,
                "streaming": "duplex",
            },
            "payload": payload,
        }
        await self._wait(
            self._socket.send(json.dumps(body)), timeout=self.timeout_seconds
        )
        self._check()

    async def _event(self, event: dict) -> None:
        header = event.get("header")
        if not isinstance(header, dict) or header.get("task_id") != self._task_id:
            raise ProviderError("response")
        kind = header.get("event")
        if kind == "task-failed":
            raise ProviderError("unavailable")
        if kind == "task-started":
            if self._ready.done():
                raise ProviderError("response")
            self._ready.set_result(None)
            return
        if not self._ready.done():
            raise ProviderError("response")
        if kind == "task-finished":
            if not self._finish_sent or self._pending_sentences:
                raise ProviderError("response")
            self._done.set_result(
                "".join(text for _, (_, text) in sorted(self._sentences.items()))
            )
            return
        if kind != "result-generated":
            raise ProviderError("response")
        try:
            sentence = event["payload"]["output"]["sentence"]
            if not isinstance(sentence, dict):
                raise TypeError
            if sentence.get("heartbeat") is True:
                return
            final = sentence["sentence_end"]
            if type(final) is not bool:
                raise TypeError
            if not final:
                begin = sentence.get("begin_time")
                if (
                    type(begin) is not int
                    or not 0 <= begin <= 2**31
                    or len(self._pending_sentences) >= 10000
                ):
                    raise TypeError
                self._pending_sentences.add(begin)
                return
            begin, end, text = (
                sentence["begin_time"],
                sentence["end_time"],
                sentence["text"],
            )
            if (
                type(begin) is not int
                or type(end) is not int
                or not 0 <= begin <= end <= 2**31
                or not isinstance(text, str)
                or len(text) > 100000
            ):
                raise TypeError
        except (KeyError, TypeError):
            raise ProviderError("response") from None
        self._pending_sentences.discard(begin)
        old = self._sentences.get(begin)
        if old is not None:
            if old != (end, text):
                raise ProviderError("response")
            return
        if any(
            begin < old_end and old_begin < end
            for old_begin, (old_end, _) in self._sentences.items()
        ):
            raise ProviderError("response")
        if len(self._sentences) >= 10000 or self._sentence_chars + len(text) > 100000:
            raise ProviderError("response")
        self._sentences[begin] = (end, text)
        self._sentence_chars += len(text)

    async def _send_audio(self) -> None:
        try:
            while True:
                chunk = await self._queue.get()
                self._check()
                if chunk is None:
                    self._finish_sent = True
                    await self._send_task("finish-task", {"input": {}})
                    return
                if not 0 < len(chunk) <= 3200:
                    raise ProviderError("audio")
                await self._wait(self._socket.send(chunk), timeout=self.timeout_seconds)
                # Bound pre-recorded probes to the same 100ms PCM cadence as capture.
                await self._wait(
                    asyncio.sleep(len(chunk) / 32000), timeout=self.timeout_seconds
                )
        except asyncio.CancelledError:
            return
        except ProviderError as error:
            self._fail(error.code)
        except Exception:
            self._fail("network")

    async def aclose(self) -> None:
        await super().aclose()
        self._sentences.clear()
        self._pending_sentences.clear()
        self._sentence_chars = 0
