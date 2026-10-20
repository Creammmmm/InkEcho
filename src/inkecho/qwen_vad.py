"""Bounded multi-utterance Qwen server VAD; text delivery waits for session finish."""

import asyncio
import base64
import time

from inkecho.providers import ProviderError, Result, Usage
from inkecho.realtime import QwenRealtimeSession

MAX_ITEMS = 1000
MAX_TEXT = 100000


class QwenVadSession(QwenRealtimeSession):
    """Reuse the owned transport, but never manually commit a VAD audio buffer."""

    def __init__(self, config, key, **policy):
        super().__init__(config, key, **policy)
        self._items = {}
        self._committed = []
        self._vad_update_sent = False

    async def _send_audio(self):
        try:
            while True:
                chunk = await self._queue.get()
                self._check()
                if chunk is None:
                    # The documented finish operation flushes the final VAD turn.
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

    def _item(self, event):
        identifier = event.get("item_id")
        if not isinstance(identifier, str) or not 0 < len(identifier) <= 200:
            raise ProviderError("response")
        if identifier not in self._items:
            if len(self._items) >= MAX_ITEMS:
                raise ProviderError("response")
            self._items[identifier] = {
                "committed": False,
                "started": False,
                "stopped": False,
                "text": None,
                "draft": "",
            }
        return identifier, self._items[identifier]

    def _text(self):
        text = "".join(self._items[key]["text"] or "" for key in self._committed)
        if len(text) > MAX_TEXT:
            raise ProviderError("response")
        return text

    def _preview_text(self):
        order = self._committed + [
            key for key in self._items if key not in self._committed
        ]
        text = "".join(
            item["text"] if item["text"] is not None else item["draft"]
            for key in order
            for item in [self._items[key]]
        )
        if len(text) > MAX_TEXT:
            raise ProviderError("response")
        return text

    def _preview(self, text):
        if self._on_preview is not None and self.active():
            self._on_preview(text)

    async def _event(self, event):
        kind = event.get("type")
        if kind in {"session.created", "session.updated"}:
            self._event_id(event)
            session = event.get("session")
            if (
                not isinstance(session, dict)
                or session.get("model") != self.config.model
            ):
                raise ProviderError("response")
            identifier = session.get("id")
            if not isinstance(identifier, str) or not identifier:
                raise ProviderError("response")
            if kind == "session.created":
                if self._session_id is not None:
                    raise ProviderError("response")
                self._session_id = identifier
                await self._send(
                    "session.update",
                    session={
                        "input_audio_format": "pcm",
                        "sample_rate": 16000,
                        "input_audio_transcription": {},
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.0,
                            "silence_duration_ms": 400,
                        },
                    },
                )
                self._vad_update_sent = True
            else:
                detection = session.get("turn_detection")
                if (
                    not self._vad_update_sent
                    or identifier != self._session_id
                    or self._ready.done()
                    or not isinstance(detection, dict)
                    or detection.get("type") != "server_vad"
                    or type(detection.get("threshold")) not in (int, float)
                    or detection["threshold"] != 0.0
                    or type(detection.get("silence_duration_ms")) is not int
                    or detection["silence_duration_ms"] != 400
                    or session.get("sample_rate", 16000) != 16000
                    or session.get("input_audio_format") not in {"pcm", "pcm16"}
                ):
                    raise ProviderError("response")
                self._ready.set_result(None)
            return
        self._event_id(event)
        if kind == "error":
            raise ProviderError("unavailable")
        if not self._ready.done():
            raise ProviderError("response")
        if kind == "conversation.item.created":
            item = event.get("item")
            if not isinstance(item, dict) or item.get("type") != "message":
                raise ProviderError("response")
            return
        if kind == "session.finished":
            if not self._finish_sent:
                raise ProviderError("response")
            # Every announced speech turn must have both a commit and a final.
            if any(
                not item["committed"] or item["text"] is None
                for item in self._items.values()
            ):
                raise ProviderError("response")
            text = self._text()
            if text.strip() and self._on_completed is not None:
                callback, self._on_completed = self._on_completed, None
                callback(Result(text, Usage(), time.monotonic() - self._began))
            self._done.set_result(text)
            return
        identifier, item = self._item(event)
        if kind == "input_audio_buffer.speech_started":
            if item["started"] or item["committed"]:
                raise ProviderError("response")
            item["started"] = True
        elif kind == "input_audio_buffer.speech_stopped":
            if not item["started"] or item["stopped"] or item["committed"]:
                raise ProviderError("response")
            item["stopped"] = True
        elif kind == "input_audio_buffer.committed":
            if item["committed"]:
                raise ProviderError("response")
            previous = event.get("previous_item_id")
            expected = self._committed[-1] if self._committed else None
            if previous != expected:
                raise ProviderError("response")
            item["committed"] = True
            self._committed.append(identifier)
        elif kind == "conversation.item.input_audio_transcription.text":
            text, stash = event.get("text", ""), event.get("stash", "")
            if (
                (
                    "content_index" not in event
                    or (
                        type(event["content_index"]) is int
                        and event["content_index"] == 0
                    )
                )
                and isinstance(text, str)
                and isinstance(stash, str)
                and len(text) + len(stash) <= MAX_TEXT
                and item["text"] is None
            ):
                item["draft"] = text + stash
                self._preview(self._preview_text())
        elif kind in {
            "conversation.item.input_audio_transcription.completed",
            "conversation.item.input_audio_transcription.failed",
        }:
            if not item["committed"] or (
                "content_index" in event
                and (
                    type(event["content_index"]) is not int
                    or event["content_index"] != 0
                )
            ):
                raise ProviderError("response")
            if kind.endswith(".failed"):
                raise ProviderError("unavailable")
            text = event.get("transcript")
            if not isinstance(text, str) or len(text) > MAX_TEXT:
                raise ProviderError("response")
            if item["text"] is not None and item["text"] != text:
                raise ProviderError("response")
            item["text"] = text
            item["draft"] = ""
            self._text()
            self._preview(self._preview_text())
        else:
            raise ProviderError("response")

    def _event_id(self, event):
        identifier = event.get("event_id")
        if identifier is None:
            return
        if (
            not isinstance(identifier, str)
            or not 0 < len(identifier) <= 200
            or identifier in self._event_ids
            or len(self._event_ids) >= 10000
        ):
            raise ProviderError("response")
        self._event_ids.add(identifier)

    async def aclose(self):
        await super().aclose()
        self._items.clear()
        self._committed.clear()
