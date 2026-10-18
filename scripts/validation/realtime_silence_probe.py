#!/usr/bin/env python3
"""Opt-in one-second generated-silence protocol check, never a speech test.

Without --live this reads no configuration/key and opens no connection. Live
execution requires separate operator approval for the single official request.
No microphone, WAV file, local audio, user text or prompt is read or sent.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import logging
import re
import time
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

from inkecho.config import (
    SCHEMA_VERSION,
    ConfigError,
    ConfigStore,
    Provider,
    Settings,
    reject_secrets,
    require_id,
)
from inkecho.providers import ProviderError
from inkecho.realtime import PROTOCOL, QwenRealtimeSession, RealtimeConfig
from inkecho.security import CredentialError, FileCredentialStore

MODEL = "qwen3-asr-flash-realtime"
SILENCE_CHUNK = bytes(3200)  # 100 ms mono PCM16 at 16 kHz, generated here.
CHUNKS = 10
TIMEOUT_SECONDS = 20


class ObservedSession(QwenRealtimeSession):
    """Test-only booleans after the production adapter validates each event."""

    def __init__(self, *args, handshake_only=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.handshake_only = handshake_only
        self.created = self.updated = self.committed = self.finished = False
        self.commit_sent = self.finish_requested = False
        self.update_requested = self.update_sent = False
        self.frames_sent = 0
        self.event_diagnostic = {}

    async def _event(self, event):
        # Fixed classifications only; never retain the event or any raw value.
        kind = event.get("type")
        known = {
            "session.created",
            "session.updated",
            "session.finished",
            "error",
            "input_audio_buffer.committed",
            "conversation.item.created",
            "conversation.item.input_audio_transcription.text",
            "conversation.item.input_audio_transcription.completed",
            "conversation.item.input_audio_transcription.failed",
        }
        session = event.get("session")
        values = session if isinstance(session, dict) else {}
        identifier = event.get("event_id")
        form = values.get("input_audio_format")
        rate = values.get("sample_rate")
        turn = values.get("turn_detection")
        item = event.get("item")
        item_values = item if isinstance(item, dict) else {}
        item_id = item_values.get("id")
        event_item_id = event.get("item_id")
        provisional_id = getattr(self, "_provisional_item_id", None)
        transcript = event.get("transcript")
        index = event.get("content_index")
        self.event_diagnostic = {
            "event_kind": kind if isinstance(kind, str) and kind in known else "other",
            "event_id_present": "event_id" in event,
            "event_id_string": isinstance(identifier, str),
            "event_id_length_valid": isinstance(identifier, str)
            and 0 < len(identifier) <= 200,
            "event_id_duplicate": isinstance(identifier, str)
            and identifier in self._event_ids,
            "session_object": isinstance(session, dict),
            "model_present": "model" in values,
            "model_match": values.get("model") == self.config.model,
            "session_id_present": "id" in values,
            "session_id_string": isinstance(values.get("id"), str),
            "session_id_known": self._session_id is not None,
            "session_id_match": values.get("id") == self._session_id,
            "format_missing": "input_audio_format" not in values,
            "format_pcm": form == "pcm",
            "format_pcm16": form == "pcm16",
            "format_other": "input_audio_format" in values
            and form not in ("pcm", "pcm16"),
            "sample_rate_missing": "sample_rate" not in values,
            "sample_rate_integer": type(rate) is int,
            "sample_rate_match": type(rate) is int and rate == 16000,
            "turn_detection_missing": "turn_detection" not in values,
            "turn_detection_null": "turn_detection" in values and turn is None,
            "turn_detection_object": isinstance(turn, dict),
            "ready_already_done": self._ready is not None and self._ready.done(),
            "item_present": "item" in event,
            "item_object": isinstance(item, dict),
            "item_id_nonempty": isinstance(item_id, str) and bool(item_id),
            "item_id_length_valid": isinstance(item_id, str)
            and 0 < len(item_id) <= 200,
            "item_id_known": self._item_id is not None,
            "item_id_match": self._item_id is not None and item_id == self._item_id,
            "item_role_user": item_values.get("role") == "user",
            "item_type_message": item_values.get("type") == "message",
            "commit_sent": self._commit_sent,
            "finishing": self._finishing,
            "event_item_id_valid": isinstance(event_item_id, str)
            and 0 < len(event_item_id) <= 200,
            "event_item_id_missing": "item_id" not in event,
            "event_item_id_null": "item_id" in event and event_item_id is None,
            "event_item_id_empty": isinstance(event_item_id, str) and not event_item_id,
            "event_item_id_invalid": event_item_id is not None
            and (
                not isinstance(event_item_id, str) or not 0 < len(event_item_id) <= 200
            ),
            "event_item_id_matches_committed": self._item_id is not None
            and event_item_id == self._item_id,
            "event_item_id_matches_provisional": provisional_id is not None
            and event_item_id == provisional_id,
            "transcript_string": isinstance(transcript, str),
            "transcript_nonempty": isinstance(transcript, str)
            and bool(transcript.strip()),
            "content_index_missing": "content_index" not in event,
            "content_index_int0": type(index) is int and index == 0,
            "content_index_invalid": "content_index" in event
            and (type(index) is not int or index != 0),
        }
        await super()._event(event)
        if kind == "session.created":
            self.created = True
        elif kind == "session.updated":
            self.updated = True
        elif kind == "input_audio_buffer.committed":
            self.committed = True
        elif kind == "session.finished":
            self.finished = True

    async def _send(self, event_type, **body):
        if self.handshake_only and event_type in {
            "input_audio_buffer.append",
            "input_audio_buffer.commit",
            "session.finish",
        }:
            raise ProviderError("configuration")
        if event_type == "session.update":
            self.update_requested = True
        if event_type == "input_audio_buffer.append":
            if self.frames_sent >= CHUNKS or body.get("audio") != base64.b64encode(
                SILENCE_CHUNK
            ).decode("ascii"):
                raise ProviderError("configuration")
        if event_type == "session.finish":
            self.finish_requested = True
        await super()._send(event_type, **body)
        if event_type == "session.update":
            self.update_sent = True
        if event_type == "input_audio_buffer.append":
            self.frames_sent += 1
        elif event_type == "input_audio_buffer.commit":
            self.commit_sent = True


def read_record(path: Path, record_type):
    with path.open("rb") as stream:
        raw = stream.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ConfigError("Configuration is too large.")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ConfigError("Current configuration object required.")
    version = data.pop("schema_version", None)
    if type(version) is not int or version != SCHEMA_VERSION:
        raise ConfigError("Current configuration schema required.")
    reject_secrets(data)
    return record_type(**data), hashlib.sha256(raw).digest()


def official_config(provider: Provider) -> RealtimeConfig:
    """Clone the current official ASR profile; never use a configured gateway."""
    url = urlsplit(provider.base_url)
    host = url.hostname or ""
    workspace = re.fullmatch(
        r"[a-z0-9-]+\.(?:cn-beijing|ap-southeast-1)\.maas\.aliyuncs\.com", host
    ) and not host.startswith("trial.")
    shared = host in {"dashscope.aliyuncs.com", "dashscope-intl.aliyuncs.com"}
    if (
        provider.role != "transcription"
        or provider.adapter != "qwen"
        or url.scheme != "https"
        or not (workspace or shared)
        or url.port not in {None, 443}
        or url.path.rstrip("/") not in {"/compatible-mode/v1", "/api/v1"}
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise ProviderError("configuration")
    copied = replace(provider, model=MODEL, parameters={"asr_protocol": PROTOCOL})
    return RealtimeConfig.from_provider(copied)


async def exercise(config: RealtimeConfig, key: str, *, handshake_only=False) -> dict:
    started = time.monotonic()
    session = ObservedSession(
        config,
        key,
        handshake_only=handshake_only,
        timeout_seconds=TIMEOUT_SECONDS,
        deadline=started + TIMEOUT_SECONDS,
    )
    ready = False
    code = None
    transcript_nonempty = False
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            await session.start()
            ready = True
            if not handshake_only:
                for _ in range(CHUNKS):
                    await session.feed(SILENCE_CHUNK)
                    await asyncio.sleep(0.1)
                result = await session.finish()
                transcript_nonempty = bool(result.text.strip())
    except ProviderError as error:
        code = error.code
    except TimeoutError:
        code = "timeout"
    finally:
        await session.aclose()
    complete = (
        ready
        and session.created
        and session.updated
        and session.committed
        and session.commit_sent
        and session.finish_requested
        and session.finished
        and session.frames_sent == CHUNKS
    )
    if (
        handshake_only
        and ready
        and session.created
        and session.updated
        and code is None
    ):
        status = "handshake_ready"
    elif not handshake_only and complete and code in {None, "empty"}:
        status = (
            "protocol_finished_with_text"
            if transcript_nonempty
            else "protocol_finished_without_speech"
        )
        code = None
    else:
        status = "failed"
        code = code or "protocol_incomplete"
    return {
        "mode": "handshake_only_protocol_diagnostic"
        if handshake_only
        else "generated_silence_protocol_only",
        "status": status,
        "code": code,
        "session_created": session.created,
        "session_updated": session.updated,
        "commit_acknowledged": session.committed,
        "commit_sent": session.commit_sent,
        "finish_requested": session.finish_requested,
        "session_finished": session.finished,
        "frames_sent": session.frames_sent,
        "generated_audio_ms": 0 if handshake_only else 1000,
        "transcript_nonempty": transcript_nonempty,
        "event_diagnostic": session.event_diagnostic,
        "update_requested": session.update_requested,
        "update_sent": session.update_sent,
        "completed_ms": round((time.monotonic() - started) * 1000, 3),
    }


async def probe(root: Path, *, handshake_only=False) -> dict:
    settings_path = root / "config.json"
    settings, settings_hash = read_record(settings_path, Settings)
    require_id(settings.transcription_provider)
    provider_path = root / "providers" / f"{settings.transcription_provider}.json"
    provider, provider_hash = read_record(provider_path, Provider)
    if provider.id != settings.transcription_provider:
        raise ProviderError("configuration")
    config = official_config(provider)
    key = await asyncio.to_thread(
        lambda: FileCredentialStore(root).get(provider.key_ref)
    )
    if not key:
        raise ProviderError("credentials")
    result = await exercise(config, key, handshake_only=handshake_only)
    unchanged = (
        hashlib.sha256(settings_path.read_bytes()).digest() == settings_hash
        and hashlib.sha256(provider_path.read_bytes()).digest() == provider_hash
    )
    result["config_unchanged"] = unchanged
    if not unchanged:
        result.update(status="failed", code="configuration_changed")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--handshake-only", action="store_true")
    parser.add_argument("--config-root", type=Path)
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps({"status": "not_run", "reason": "live_opt_in_required"}))
        return 2
    logging.disable(logging.CRITICAL)
    try:
        result = asyncio.run(
            probe(
                args.config_root or ConfigStore().root,
                handshake_only=args.handshake_only,
            )
        )
    except ProviderError as error:
        result = {"status": "failed", "code": error.code}
    except CredentialError:
        result = {"status": "failed", "code": "credentials"}
    except (ConfigError, OSError, ValueError, TypeError):
        result = {"status": "failed", "code": "configuration"}
    except KeyboardInterrupt:
        result = {"status": "failed", "code": "cancelled"}
    except Exception:
        result = {"status": "failed", "code": "probe_failed"}
    print(json.dumps(result, sort_keys=True))
    return (
        0
        if result["status"]
        in {
            "protocol_finished_without_speech",
            "protocol_finished_with_text",
            "handshake_ready",
        }
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
