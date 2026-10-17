"""One reviewed public-WAV Qwen realtime capability call; no polish/input/mic."""

import argparse
import asyncio
import json
import time
from dataclasses import replace
from pathlib import Path

from artifact_scope import audit_package, checksum, selected_artifact
from native_guard import save

PUBLIC_WAV = Path("/tmp/inkecho-public-asr-fixture.wav")
PUBLIC_SHA = "0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf"
PUBLIC_BYTES = 571456


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["artifact", "package-root", "frozen-source-root", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--expected-provider-sha", required=True)
    parser.add_argument("--run-cloud", action="store_true")
    args = parser.parse_args()
    if not args.run_cloud or args.output.exists():
        raise SystemExit(2) from None
    selected = selected_artifact(args.artifact, args.expected_sha)
    audit = audit_package(
        args.package_root, args.frozen_source_root, args.expected_version
    )
    from inkecho.config import Provider
    from inkecho.provider_capability import realtime_capability
    from inkecho.providers import ProviderError, validate_provider_protocol
    from inkecho.realtime import RealtimeConfig

    path = Path("/home/lth/.config/inkecho/providers/qwen.json")

    def validate_inputs():
        if checksum(path) != args.expected_provider_sha:
            raise ValueError("reviewed_provider_changed")
        if (
            PUBLIC_WAV.stat().st_size != PUBLIC_BYTES
            or checksum(PUBLIC_WAV) != PUBLIC_SHA
        ):
            raise ValueError("public_fixture_changed")

    validate_inputs()
    data = json.loads(path.read_text())
    data.pop("schema_version", None)
    provider = Provider(**data)
    if provider.key_ref != "provider/qwen" or provider.adapter != "qwen":
        raise SystemExit(2) from None
    provider = replace(
        provider,
        model="qwen3-asr-flash-realtime",
        parameters={"asr_protocol": "qwen_realtime"},
    )
    validate_provider_protocol(provider)
    RealtimeConfig.from_provider(provider, sample_rate=16000)
    report = {
        "passed": False,
        "artifact": selected,
        "runtime": audit,
        "asr_attempts_reserved": 0,
        "maximum_asr_attempts": 1,
        "polishing_calls": 0,
        "retries": 0,
        "microphone": False,
        "desktop_input": False,
        "public_wav_sha256": PUBLIC_SHA,
        "raw_text_saved": False,
        "accuracy_evaluated": False,
    }
    save(args.output, report)
    key = audio = result = None
    try:
        validate_inputs()
        from inkecho.security import SecretStore

        key = SecretStore().get("provider/qwen")
        if not key:
            raise ValueError("credential_unavailable")
        validate_inputs()
        audio = PUBLIC_WAV.read_bytes()
        report["asr_attempts_reserved"] = 1
        save(args.output, report)
        began = time.monotonic()
        result = asyncio.run(
            realtime_capability(provider, key, audio, timeout_seconds=45)
        )
        report.update(
            final_received=True,
            characters=len(result.text),
            elapsed_ms=round((time.monotonic() - began) * 1000, 3),
            passed=bool(result.text),
        )
    except ProviderError as error:
        report["failure_code"] = error.code
    except Exception:
        report["failure_code"] = "realtime_capability_failed"
    finally:
        key = audio = result = None
        save(args.output, report)
        print(json.dumps(report))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "code": "acceptance_preflight_failed"}))
        raise SystemExit(2) from None
