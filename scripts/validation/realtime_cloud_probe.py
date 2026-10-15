"""One authorized live ASR request using only an SHA-pinned public audio fixture.

Never accepts arbitrary microphone audio and never dispatches desktop input.
Prints fixed metadata fields, with no provider bodies or free-form exceptions.
"""

import argparse
import asyncio
import hashlib
import json
import time
import wave
from dataclasses import replace
from pathlib import Path

from inkecho.config import ConfigStore, Provider, require_id
from inkecho.providers import ProviderError
from inkecho.realtime import CHUNK_BYTES, QwenRealtimeSession, RealtimeConfig
from inkecho.security import SecretStore

AUDIO = Path("/tmp/inkecho-public-asr-fixture.wav")
AUDIO_SHA = "0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def probe() -> dict:
    state = {
        "fixture_verified": False,
        "final_received": False,
        "characters": 0,
        "elapsed_seconds": 0.0,
        "stop_to_final_seconds": None,
        "config_unchanged": False,
        "error_code": None,
    }
    began = time.monotonic()
    paths = []
    original = []
    session = None
    try:
        if digest(AUDIO) != AUDIO_SHA:
            state["error_code"] = "fixture"
            return state
        with wave.open(str(AUDIO), "rb") as recording:
            if (
                recording.getnchannels() != 1
                or recording.getsampwidth() != 2
                or recording.getframerate() != 16000
                or recording.getcomptype() != "NONE"
                or recording.getnframes() > 16000 * 30
            ):
                state["error_code"] = "fixture"
                return state
            pcm = recording.readframes(recording.getnframes())
        state["fixture_verified"] = True
        root = ConfigStore().root
        settings_path = root / "config.json"
        identifier = json.loads(settings_path.read_bytes())["transcription_provider"]
        require_id(identifier)
        provider_path = root / "providers" / f"{identifier}.json"
        paths = [settings_path, provider_path]
        original = [digest(path) for path in paths]
        values = json.loads(provider_path.read_bytes())
        if values.pop("schema_version", None) != 1:
            raise ProviderError("configuration")
        provider = replace(
            Provider(**values),
            model="qwen3-asr-flash-realtime",
            parameters={"asr_protocol": "qwen_realtime"},
        )
        key = SecretStore().get(provider.key_ref)
        if not key:
            raise ProviderError("credentials")
        session = QwenRealtimeSession(
            RealtimeConfig.from_provider(provider),
            key,
            timeout_seconds=20,
            deadline=time.monotonic() + 45,
        )
        key = None
        async with asyncio.timeout(45):
            await session.start()
            paced_start = time.monotonic()
            for offset in range(0, len(pcm), CHUNK_BYTES):
                await session.feed(pcm[offset : offset + CHUNK_BYTES])
                target = paced_start + min(offset + CHUNK_BYTES, len(pcm)) / 32000
                await asyncio.sleep(max(0, target - time.monotonic()))
            pcm = b""
            stopped = time.monotonic()
            result = await session.finish()
            state["stop_to_final_seconds"] = round(time.monotonic() - stopped, 4)
            state["characters"] = len(result.text)
            state["final_received"] = True
    except ProviderError as error:
        state["error_code"] = error.code
    except (TimeoutError, asyncio.CancelledError):
        state["error_code"] = "timeout_or_cancelled"
    except Exception:
        state["error_code"] = "probe_unavailable"
    finally:
        if session is not None:
            try:
                await session.aclose()
            except Exception:
                state["error_code"] = "cleanup"
        state["elapsed_seconds"] = round(time.monotonic() - began, 4)
        try:
            state["config_unchanged"] = bool(paths) and original == [
                digest(path) for path in paths
            ]
        except OSError:
            state["config_unchanged"] = False
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live:
        print(json.dumps({"error_code": "live_flag_required"}))
        return 2
    state = asyncio.run(probe())
    print(json.dumps(state, sort_keys=True))
    return 0 if state["final_received"] and state["config_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
