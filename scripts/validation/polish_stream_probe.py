#!/usr/bin/env python3
"""Opt-in fixed-public-text SSE timing; no microphone or desktop delivery.

No network or credential access occurs without --live. That flag is an explicit
operator opt-in, not a substitute for approval of the live destination/request.
Only safe counters and timing are printed, including on failure.
"""

import argparse
import asyncio
import json
import logging
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
from inkecho.providers import ProviderClient, ProviderError
from inkecho.security import CredentialError, SecretStore

TEXT = "今天是晴天，我们去公园散步。"
PROMPT = "Return the user's text unchanged. Output only that text."


def load_record(path: Path, record_type):
    """Read only current-schema records; never migrate or write user settings."""
    raw = path.read_bytes()
    if len(raw) > 2_000_000:
        raise ConfigError("Configuration is too large.")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.pop("schema_version", None) != SCHEMA_VERSION:
        raise ConfigError("Current configuration schema required.")
    reject_secrets(data)
    return record_type(**data)


async def probe(root: Path) -> dict:
    settings = load_record(root / "config.json", Settings)
    require_id(settings.polishing_provider)
    provider = load_record(
        root / "providers" / f"{settings.polishing_provider}.json", Provider
    )
    url = urlsplit(provider.base_url)
    if (
        provider.id != settings.polishing_provider
        or provider.role != "polishing"
        or provider.adapter != "openai"
        or url.hostname != "api.deepseek.com"
        or url.port not in {None, 443}
        or url.path.rstrip("/") not in {"", "/v1"}
        or provider.model != "deepseek-flash"
    ):
        raise ProviderError("configuration")
    # Probe policy is fixed and does not alter persisted provider parameters.
    provider = replace(provider, parameters={"max_tokens": 64})
    key = await asyncio.to_thread(lambda: SecretStore().get(provider.key_ref))
    if not key:
        raise ProviderError("credentials")
    started = time.monotonic()
    first = None
    deltas = characters = 0

    async def receive(delta: str) -> None:
        nonlocal first, deltas, characters
        if first is None:
            first = time.monotonic() - started
        deltas += 1
        characters += len(delta)

    async with ProviderClient(timeout_seconds=30) as client:
        result = await client.polish_stream(provider, key, TEXT, PROMPT, receive)
    completed = time.monotonic() - started
    return {
        "mode": "live_fixed_public_text",
        "status": "passed",
        "first_delta_ms": round(first * 1000, 3) if first is not None else None,
        "completed_ms": round(completed * 1000, 3),
        "first_precedes_complete": first is not None and first < completed,
        "deltas": deltas,
        "characters": characters,
        "exact_public_text": result.text == TEXT,
        "usage_available": result.usage.total_tokens is not None,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--config-root", type=Path)
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps({"status": "not_run", "reason": "live_opt_in_required"}))
        return 2
    # Third-party debug output must not expose request/response content.
    logging.disable(logging.CRITICAL)
    root = args.config_root or ConfigStore().root
    try:
        result = asyncio.run(probe(root))
    except ProviderError as error:
        result = {"status": "failed", "code": error.code}
    except CredentialError:
        result = {"status": "failed", "code": "credentials"}
    except (ConfigError, OSError, ValueError, TypeError):
        result = {"status": "failed", "code": "configuration"}
    except Exception:
        result = {"status": "failed", "code": "probe_failed"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
