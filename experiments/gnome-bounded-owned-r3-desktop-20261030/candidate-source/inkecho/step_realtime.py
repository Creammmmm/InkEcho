"""StepFun ASR-only manual commit, sharing bounded transport but not Qwen events."""

import asyncio
import base64
import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from inkecho.config import Provider
from inkecho.providers import ProviderError
from inkecho.realtime import QwenRealtimeSession

PROTOCOL = "stepfun_realtime"
PCM_FORMAT = {
    "type": "pcm",
    "codec": "pcm_s16le",
    "rate": 16000,
    "bits": 16,
    "channel": 1,
}


@dataclass(frozen=True)
class StepRealtimeConfig:
    endpoint: str
    model: str
    sample_rate: int = 16000
    language: str = "zh"

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
        except (TypeError, ValueError):
            raise ProviderError("configuration") from None
        if (
            self.sample_rate != 16000
            or type(self.sample_rate) is not int
            or self.model not in {"stepaudio-2.5-asr-stream", "step-asr-1.1-stream"}
            or not isinstance(self.language, str)
            or not re.fullmatch(r"[a-z]{2,3}", self.language)
        ):
            raise ProviderError("configuration")

    @property
    def url(self) -> str:
        """StepFun has no model query; selection is in session.update."""
        return self.endpoint

    @classmethod
    def from_provider(
        cls, provider: Provider, *, sample_rate: int = 16000
    ) -> "StepRealtimeConfig":
        if (
            provider.adapter != "stepfun-realtime"
            or provider.role != "transcription"
            or provider.parameters.get("asr_protocol") != PROTOCOL
            or set(provider.parameters) - {"asr_protocol", "realtime_url", "language"}
        ):
            raise ProviderError("configuration")
        endpoint = provider.parameters.get("realtime_url")
        if endpoint is None:
            base = urlsplit(provider.base_url)
            if base.hostname != "api.stepfun.com" or base.port not in {443, None}:
                raise ProviderError("configuration")
            endpoint = urlunsplit(
                ("wss", base.netloc, "/v1/realtime/asr/stream", "", "")
            )
        return cls(
            endpoint,
            provider.model,
            sample_rate,
            provider.parameters.get("language", "zh"),
        )


class StepRealtimeSession(QwenRealtimeSession):
    """Reuse queue/deadline/close only; override event state and the commit sender.

    Call graph: inherited start -> inherited _open(config.url without query),
    inherited _receive JSON loop -> this _event; inherited finish
    -> this _send_audio (one commit, never session.finish) -> matched completed.
    No early-result callback is exposed; partial/stash data never leave this class.
    """

    set_completed_callback = None

    async def _event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "error":
            raise ProviderError("unavailable")
        event_id = event.get("event_id")
        if event_id is not None:
            if (
                not isinstance(event_id, str)
                or not 0 < len(event_id) <= 200
                or event_id in self._event_ids
                or len(self._event_ids) >= 10000
            ):
                raise ProviderError("response")
            self._event_ids.add(event_id)
        meta = event.get("meta")
        if meta is not None and not isinstance(meta, dict):
            raise ProviderError("response")
        session_id = meta.get("session_id") if meta else None
        if session_id is not None and (
            not isinstance(session_id, str) or not 0 < len(session_id) <= 200
        ):
            raise ProviderError("response")
        if (
            session_id is not None
            and self._session_id is not None
            and self._session_id != session_id
        ):
            raise ProviderError("response")
        if session_id is not None:
            self._session_id = session_id
        if kind == "session.created":
            if self._manual_update_sent:
                raise ProviderError("response")
            self._manual_update_sent = True
            await self._send(
                "session.update",
                session={
                    "audio": {
                        "input": {
                            "format": PCM_FORMAT,
                            "transcription": {
                                "model": self.config.model,
                                "language": self.config.language,
                                "full_rerun_on_commit": True,
                            },
                            "turn_detection": {},
                        }
                    }
                },
            )
            return
        if kind == "session.updated":
            try:
                config = event["session"]["audio"]["input"]
                turn = config.get("turn_detection")
                if (
                    self._ready.done()
                    or not self._manual_update_sent
                    or config["format"] != PCM_FORMAT
                    or (turn is not None and turn != {})
                ):
                    raise ProviderError("response")
                transcription = config.get("transcription", {})
                if (
                    not isinstance(transcription, dict)
                    or transcription.get("model", self.config.model)
                    != self.config.model
                ):
                    raise ProviderError("response")
            except (KeyError, TypeError, AttributeError):
                raise ProviderError("response") from None
            self._ready.set_result(None)
            return
        if not self._ready.done():
            raise ProviderError("response")
        if kind in {
            "conversation.item.input_audio_transcription.delta",
            "conversation.item.created",
        }:
            return
        item_id = event.get("item_id")
        if (
            kind
            not in {
                "input_audio_buffer.committed",
                "conversation.item.input_audio_transcription.completed",
            }
            or not self._commit_sent
            or not isinstance(item_id, str)
            or not 0 < len(item_id) <= 200
        ):
            raise ProviderError("response")
        if kind == "input_audio_buffer.committed":
            if self._commit_acknowledged:
                raise ProviderError("response")
            self._item_id = item_id
            self._commit_acknowledged = True
            return
        if (
            not self._commit_acknowledged
            or self._item_id != item_id
            or type(event.get("content_index")) is not int
            or event["content_index"] != 0
        ):
            raise ProviderError("response")
        text = event.get("transcript")
        if not isinstance(text, str) or len(text) > 100000:
            raise ProviderError("response")
        self._done.set_result(text)

    async def _send_audio(self) -> None:
        try:
            while True:
                chunk = await self._queue.get()
                self._check()
                if chunk is None:
                    self._commit_sent = True
                    await self._send("input_audio_buffer.commit")
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
