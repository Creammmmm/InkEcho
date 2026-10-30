"""Explicit native polishing protocols; no gateway guessing or POST replay."""

import asyncio
import json
import math
import re
import time
from collections.abc import Awaitable, Callable
from contextlib import aclosing
from urllib.parse import quote, urlsplit

import httpx

from inkecho.config import Provider
from inkecho.polish_stream import MAX_TEXT_CHARACTERS, MAX_WIRE_BYTES, _Events
from inkecho.providers import ProviderClient, ProviderError, Result

ADAPTERS = frozenset({"responses", "messages", "gemini"})


def auth_headers(provider: Provider, key: str) -> dict[str, str]:
    if provider.adapter == "gemini":
        return {"x-goog-api-key": key}
    if provider.adapter == "messages":
        url = urlsplit(provider.base_url)
        if (
            url.hostname == "api.minimax.io"
            and url.path.rstrip("/") == "/anthropic/v1"
            and url.port in {None, 443}
        ):
            return {"Authorization": f"Bearer {key}", "anthropic-version": "2023-06-01"}
        return {"x-api-key": key, "anthropic-version": "2023-06-01"}
    return {"Authorization": f"Bearer {key}"}


def request(
    provider: Provider, key: str, text: str, prompt: str, *, stream: bool = False
) -> tuple[str, dict[str, str], dict]:
    """Construct only this selected protocol, with credentials in headers."""
    if provider.role != "polishing" or provider.adapter not in ADAPTERS:
        raise ProviderError("configuration")
    if not text.strip() or not prompt.strip():
        raise ProviderError("empty")
    values = provider.parameters
    common = {"temperature", "top_p"}
    for name, value in values.items():
        if name in {"temperature", "top_p"}:
            if (
                type(value) not in {int, float}
                or not math.isfinite(value)
                or not 0 <= value <= (1 if name == "top_p" else 2)
            ):
                raise ProviderError("configuration")
        elif name in {"max_tokens", "max_output_tokens"}:
            if type(value) is not int or not 1 <= value <= 131072:
                raise ProviderError("configuration")
    if provider.adapter == "responses":
        if set(values) - common - {"max_output_tokens"}:
            raise ProviderError("configuration")
        return (
            "responses",
            {"Authorization": f"Bearer {key}"},
            {
                "model": provider.model,
                "instructions": prompt,
                "input": [
                    {"role": "user", "content": [{"type": "input_text", "text": text}]}
                ],
                "store": False,
                "stream": stream,
                **values,
            },
        )
    if provider.adapter == "messages":
        if set(values) - common - {"max_tokens"}:
            raise ProviderError("configuration")
        headers = auth_headers(provider, key)
        return (
            "messages",
            headers,
            {
                "model": provider.model,
                "system": prompt,
                "messages": [{"role": "user", "content": text}],
                "max_tokens": 2048,
                "stream": stream,
                **values,
            },
        )
    if set(values) - {"temperature", "top_p", "max_output_tokens"}:
        raise ProviderError("configuration")
    model = provider.model.removeprefix("models/")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,200}", model):
        raise ProviderError("configuration")
    method = "streamGenerateContent?alt=sse" if stream else "generateContent"
    names = {
        "temperature": "temperature",
        "top_p": "topP",
        "max_output_tokens": "maxOutputTokens",
    }
    body = {
        "systemInstruction": {"parts": [{"text": prompt}]},
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {names[name]: value for name, value in values.items()},
    }
    return f"models/{quote(model, safe='')}:{method}", {"x-goog-api-key": key}, body


def plain(value: object) -> str:
    if not isinstance(value, str) or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ProviderError("response")
    return value


def response_text(value: dict) -> tuple[str, dict]:
    """Only complete assistant output_text, never reasoning/refusal/tool content."""
    if value.get("status") != "completed" or not isinstance(value.get("output"), list):
        raise ProviderError("response")
    parts = []
    for item in value["output"]:
        if not isinstance(item, dict):
            raise ProviderError("response")
        if item.get("type") == "reasoning":
            continue
        if (
            item.get("type") != "message"
            or item.get("role") != "assistant"
            or item.get("status") != "completed"
            or not isinstance(item.get("content"), list)
        ):
            raise ProviderError("response")
        for content in item["content"]:
            if not isinstance(content, dict) or content.get("type") != "output_text":
                raise ProviderError("response")
            parts.append(plain(content.get("text")))
    usage = value.get("usage") or {}
    if not isinstance(usage, dict):
        raise ProviderError("response")
    return "".join(parts), {
        "prompt_tokens": usage.get("input_tokens"),
        "completion_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def message_text(value: dict) -> tuple[str, dict]:
    if (
        value.get("type") != "message"
        or value.get("role") != "assistant"
        or value.get("stop_reason") != "end_turn"
        or not isinstance(value.get("content"), list)
    ):
        raise ProviderError("response")
    parts = []
    for part in value["content"]:
        if not isinstance(part, dict):
            raise ProviderError("response")
        kind = part.get("type")
        if kind == "text":
            parts.append(plain(part.get("text")))
        elif not isinstance(kind, str) or kind not in {"thinking", "redacted_thinking"}:
            raise ProviderError("response")
    usage = value.get("usage") or {}
    if not isinstance(usage, dict):
        raise ProviderError("response")
    return "".join(parts), {
        "prompt_tokens": usage.get("input_tokens"),
        "completion_tokens": usage.get("output_tokens"),
    }


def gemini_text(value: dict, *, final: bool) -> tuple[str, dict, bool]:
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 1:
        raise ProviderError("response")
    candidate = candidates[0]
    if (
        not isinstance(candidate, dict)
        or type(candidate.get("index", 0)) is not int
        or candidate.get("index", 0) != 0
    ):
        raise ProviderError("response")
    finish = candidate.get("finishReason")
    if finish is not None and finish != "STOP" or final and finish != "STOP":
        raise ProviderError("response")
    content = candidate.get("content", {})
    if not isinstance(content, dict) or content.get("role", "model") != "model":
        raise ProviderError("response")
    parts = content.get("parts", [])
    if not isinstance(parts, list):
        raise ProviderError("response")
    texts = []
    for part in parts:
        if not isinstance(part, dict):
            raise ProviderError("response")
        if "thought" in part and type(part["thought"]) is not bool:
            raise ProviderError("response")
        if part.get("thought") is True:
            continue
        if "text" not in part or set(part) - {"text", "thought", "thoughtSignature"}:
            raise ProviderError("response")
        texts.append(plain(part["text"]))
    usage = value.get("usageMetadata") or {}
    if not isinstance(usage, dict):
        raise ProviderError("response")
    return (
        "".join(texts),
        {
            "prompt_tokens": usage.get("promptTokenCount"),
            "completion_tokens": usage.get("candidatesTokenCount"),
            "total_tokens": usage.get("totalTokenCount"),
        },
        finish == "STOP",
    )


class NativeStream:
    """Small protocol state machines with a single final success barrier."""

    def __init__(self, family: str) -> None:
        self.family = family
        self.done = False
        self.parts: list[str] = []
        self.usage = {}
        self.identifier = None
        self.sequence = -1
        self.blocks = {}
        self.closed = set()
        self.stop_reason = None
        self.characters = 0
        self.items = {}
        self.items_done = set()
        self.parts_done = set()
        self.finalizing = False

    def receive(self, payload: str) -> str | None:
        if self.done:
            raise ProviderError("response")
        try:
            value = json.loads(payload)
        except (ValueError, UnicodeError):
            raise ProviderError("response") from None
        if not isinstance(value, dict) or "error" in value:
            raise ProviderError("response")
        if self.family != "gemini" and not isinstance(value.get("type"), str):
            raise ProviderError("response")
        if self.family == "gemini":
            text, self.usage, self.done = gemini_text(value, final=False)
        elif self.family == "messages":
            text = self._messages(value)
        else:
            text = self._responses(value)
        if text:
            plain(text)
            self.characters += len(text)
            if self.characters > MAX_TEXT_CHARACTERS:
                raise ProviderError("response")
            self.parts.append(text)
            return text
        return None

    def _messages(self, value):
        kind = value.get("type")
        if kind == "ping":
            return None
        if kind == "message_start":
            item = value.get("message")
            if (
                self.identifier is not None
                or not isinstance(item, dict)
                or item.get("role") != "assistant"
                or item.get("type") != "message"
                or item.get("content") != []
            ):
                raise ProviderError("response")
            identifier, usage = plain(item.get("id")), item.get("usage", {})
            if not identifier or not isinstance(usage, dict):
                raise ProviderError("response")
            self.identifier = identifier
            self.usage = dict(usage)
            return None
        if not self.identifier:
            raise ProviderError("response")
        if kind.startswith("content_block_"):
            index = value.get("index")
            if (
                self.finalizing
                or type(index) is not int
                or not 0 <= index < 1024
                or index in self.closed
            ):
                raise ProviderError("response")
            if kind == "content_block_start":
                block = value.get("content_block")
                if (
                    index in self.blocks
                    or index != len(self.blocks)
                    or set(self.blocks) != self.closed
                    or not isinstance(block, dict)
                    or not isinstance(block.get("type"), str)
                    or block["type"] not in {"text", "thinking", "redacted_thinking"}
                ):
                    raise ProviderError("response")
                self.blocks[index] = block["type"]
                if block["type"] == "text":
                    return plain(block.get("text"))
            elif kind == "content_block_stop":
                if index not in self.blocks:
                    raise ProviderError("response")
                self.closed.add(index)
            elif kind == "content_block_delta":
                delta = value.get("delta")
                if (
                    index not in self.blocks
                    or not isinstance(delta, dict)
                    or not isinstance(delta.get("type"), str)
                ):
                    raise ProviderError("response")
                if delta.get("type") == "text_delta" and self.blocks[index] == "text":
                    return plain(delta.get("text"))
                if self.blocks[index] != "thinking" or delta.get("type") not in {
                    "thinking_delta",
                    "signature_delta",
                }:
                    raise ProviderError("response")
            else:
                raise ProviderError("response")
        elif kind == "message_delta":
            delta = value.get("delta")
            usage = value.get("usage", {})
            if (
                not isinstance(delta, dict)
                or not isinstance(usage, dict)
                or set(self.blocks) != self.closed
            ):
                raise ProviderError("response")
            reason = delta.get("stop_reason")
            if reason is not None and reason != "end_turn":
                raise ProviderError("response")
            self.finalizing = True
            if reason == "end_turn":
                self.stop_reason = reason
            self.usage.update(usage)  # Counts are cumulative, not incremental.
        elif kind == "message_stop":
            if self.stop_reason != "end_turn" or set(self.blocks) != self.closed:
                raise ProviderError("response")
            self.done = True
            self.usage = {
                "prompt_tokens": self.usage.get("input_tokens"),
                "completion_tokens": self.usage.get("output_tokens"),
            }
        else:
            raise ProviderError("response")
        return None

    def _responses(self, value):
        kind, sequence = value.get("type"), value.get("sequence_number")
        if type(sequence) is not int or sequence <= self.sequence:
            raise ProviderError("response")
        self.sequence = sequence
        if kind in {"response.created", "response.in_progress"}:
            response = value.get("response")
            if (
                not isinstance(response, dict)
                or response.get("status") != "in_progress"
            ):
                raise ProviderError("response")
            identifier = plain(response.get("id"))
            if self.identifier not in {None, identifier}:
                raise ProviderError("response")
            self.identifier = identifier
            return None
        if not self.identifier:
            raise ProviderError("response")
        if kind == "response.completed":
            response = value.get("response")
            if not isinstance(response, dict) or response.get("id") != self.identifier:
                raise ProviderError("response")
            text, self.usage = response_text(response)
            output = response["output"]
            if len(output) != len(self.items) or any(
                self.items.get(index) != (item.get("id"), item.get("type"))
                for index, item in enumerate(output)
            ):
                raise ProviderError("response")
            if (
                text != "".join(self.parts)
                or set(self.blocks) != self.closed
                or set(self.blocks) != self.parts_done
                or set(self.items) != self.items_done
            ):
                raise ProviderError("response")
            self.done = True
            return None
        if kind in {"response.output_text.delta", "response.output_text.done"}:
            index, content, item_id = (
                value.get("output_index"),
                value.get("content_index"),
                value.get("item_id"),
            )
            if (
                self.finalizing
                or type(index) is not int
                or type(content) is not int
                or not 0 <= index < 1024
                or not 0 <= content < 1024
                or not isinstance(item_id, str)
                or not item_id
            ):
                raise ProviderError("response")
            slot = (index, content, item_id)
            if slot not in self.blocks or slot in self.closed:
                raise ProviderError("response")
            if kind.endswith(".delta"):
                delta = plain(value.get("delta"))
                self.blocks[slot] = self.blocks.get(slot, "") + delta
                return delta
            if plain(value.get("text")) != self.blocks.get(slot, ""):
                raise ProviderError("response")
            self.closed.add(slot)
            return None
        if kind in {"response.output_item.added", "response.output_item.done"}:
            index, item = value.get("output_index"), value.get("item")
            if (
                type(index) is not int
                or not 0 <= index < 1024
                or not isinstance(item, dict)
            ):
                raise ProviderError("response")
            identifier = plain(item.get("id"))
            if not identifier:
                raise ProviderError("response")
            item_type = item.get("type")
            if not isinstance(item_type, str) or item_type not in {
                "message",
                "reasoning",
            }:
                raise ProviderError("response")
            if item_type == "message" and item.get("role") != "assistant":
                raise ProviderError("response")
            if kind.endswith(".added"):
                if (
                    index in self.items
                    or index != len(self.items)
                    or set(self.items) != self.items_done
                ):
                    raise ProviderError("response")
                if item_type == "message" and (
                    item.get("content") != [] or item.get("status") != "in_progress"
                ):
                    raise ProviderError("response")
                self.items[index] = (identifier, item_type)
            else:
                if (
                    self.items.get(index) != (identifier, item_type)
                    or index in self.items_done
                ):
                    raise ProviderError("response")
                if item_type == "message":
                    text, _ = response_text({"status": "completed", "output": [item]})
                    slots = [key for key in self.blocks if key[0] == index]
                    if any(
                        key not in self.parts_done for key in slots
                    ) or text != "".join(self.blocks[key] for key in slots):
                        raise ProviderError("response")
                self.items_done.add(index)
            return None
        if kind in {"response.content_part.added", "response.content_part.done"}:
            index, content, identifier, part = (
                value.get("output_index"),
                value.get("content_index"),
                value.get("item_id"),
                value.get("part"),
            )
            if (
                type(index) is not int
                or type(content) is not int
                or not 0 <= content < 1024
                or self.items.get(index) != (identifier, "message")
                or not isinstance(part, dict)
                or part.get("type") != "output_text"
                or index in self.items_done
            ):
                raise ProviderError("response")
            slot = (index, content, identifier)
            if kind.endswith(".added"):
                prior = [key for key in self.blocks if key[0] == index]
                if (
                    slot in self.blocks
                    or content != len(prior)
                    or any(key not in self.parts_done for key in prior)
                    or plain(part.get("text")) != ""
                ):
                    raise ProviderError("response")
                self.blocks[slot] = ""
            else:
                if (
                    slot not in self.closed
                    or slot in self.parts_done
                    or plain(part.get("text")) != self.blocks[slot]
                ):
                    raise ProviderError("response")
                self.parts_done.add(slot)
            return None
        if kind in {
            "response.reasoning_summary_part.added",
            "response.reasoning_summary_part.done",
            "response.reasoning_summary_text.delta",
            "response.reasoning_summary_text.done",
        }:
            index = value.get("output_index")
            if type(index) is not int or self.items.get(index) != (
                value.get("item_id"),
                "reasoning",
            ):
                raise ProviderError("response")
            return None
        raise ProviderError("response")


async def polish(
    client: ProviderClient,
    provider: Provider,
    key: str,
    text: str,
    prompt: str,
    on_delta: Callable[[str], Awaitable[None]] | None = None,
) -> Result:
    """One native request; callback backpressure and cancellation never replay."""
    path, headers, body = request(
        provider, key, text, prompt, stream=on_delta is not None
    )
    started = time.monotonic()
    state = NativeStream(provider.adapter)
    headers = {
        **headers,
        "Accept": "text/event-stream" if on_delta else "application/json",
    }
    try:
        async with asyncio.timeout(client.timeout_seconds):
            async with client._http_client().stream(
                "POST",
                f"{provider.base_url.rstrip('/')}/{path}",
                headers=headers,
                json=body,
                timeout=client.timeout_seconds,
                follow_redirects=False,
            ) as response:
                client._check_status(response.status_code)
                if on_delta:
                    if (
                        response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                        != "text/event-stream"
                    ):
                        raise ProviderError("response")
                    events = _Events()
                    async with aclosing(response.aiter_bytes()) as chunks:
                        async for chunk in chunks:
                            for payload in events.feed(chunk):
                                delta = state.receive(payload)
                                if delta:
                                    await asyncio.sleep(0)
                                    await on_delta(delta)
                                if state.done:
                                    return client._text_result(
                                        "".join(state.parts), state.usage, started
                                    )
                    raise ProviderError("response")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_WIRE_BYTES:
                        raise ProviderError("response")
                try:
                    value = json.loads(data)
                except (ValueError, UnicodeError):
                    raise ProviderError("response") from None
                if not isinstance(value, dict) or "error" in value:
                    raise ProviderError("response")
                if provider.adapter == "responses":
                    result, usage = response_text(value)
                elif provider.adapter == "messages":
                    result, usage = message_text(value)
                else:
                    result, usage, _ = gemini_text(value, final=True)
                if len(result) > MAX_TEXT_CHARACTERS:
                    raise ProviderError("response")
                return client._text_result(result, usage, started)
    except (TimeoutError, httpx.TimeoutException):
        raise ProviderError("timeout") from None
    except httpx.HTTPError:
        raise ProviderError("network") from None


async def models(client: ProviderClient, provider: Provider, key: str) -> list[str]:
    """Native discovery uses header credentials and bounded explicit pagination."""
    headers = auth_headers(provider, key)
    found, token = set(), None
    try:
        async with asyncio.timeout(client.timeout_seconds):
            for _ in range(10):
                params = {}
                if token:
                    params[
                        "pageToken" if provider.adapter == "gemini" else "after_id"
                    ] = token
                async with client._http_client().stream(
                    "GET",
                    f"{provider.base_url.rstrip('/')}/models",
                    headers=headers,
                    params=params,
                    timeout=client.timeout_seconds,
                    follow_redirects=False,
                ) as response:
                    client._check_status(response.status_code)
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_WIRE_BYTES:
                            raise ProviderError("response")
                try:
                    value = json.loads(body)
                except (ValueError, UnicodeError):
                    raise ProviderError("response") from None
                if not isinstance(value, dict) or "error" in value:
                    raise ProviderError("response")
                items = value.get("models" if provider.adapter == "gemini" else "data")
                if not isinstance(items, list):
                    raise ProviderError("response")
                for item in items:
                    if not isinstance(item, dict):
                        raise ProviderError("response")
                    if provider.adapter == "gemini":
                        methods = item.get("supportedGenerationMethods", [])
                        if not isinstance(methods, list) or any(
                            not isinstance(method, str) for method in methods
                        ):
                            raise ProviderError("response")
                        if "generateContent" not in methods:
                            continue
                        name = item.get("name")
                    else:
                        name = item.get("id")
                    if not isinstance(name, str) or not name.strip() or len(name) > 200:
                        raise ProviderError("response")
                    found.add(name)
                if provider.adapter == "messages" and value.get("has_more") is True:
                    if (
                        not isinstance(value.get("last_id"), str)
                        or not value["last_id"]
                    ):
                        raise ProviderError("response")
                next_token = (
                    value.get("nextPageToken")
                    if provider.adapter == "gemini"
                    else (
                        value.get("last_id")
                        if provider.adapter == "messages"
                        and value.get("has_more") is True
                        else None
                    )
                )
                if not next_token:
                    return sorted(found)
                if (
                    not isinstance(next_token, str)
                    or len(next_token) > 1000
                    or next_token == token
                ):
                    raise ProviderError("response")
                token = next_token
            raise ProviderError("response")
    except (TimeoutError, httpx.TimeoutException):
        raise ProviderError("timeout") from None
    except httpx.HTTPError:
        raise ProviderError("network") from None
