#!/usr/bin/env python3
"""Plan a bounded public-WAV comparison; default is read-only, no credentials.

--offline uses only local TLS, generated PCM and fake credentials. --live is an
execution branch requiring separate human authorization; do not infer consent
from this flag or a prepared plan. No live execution is part of preparation.
"""

import argparse
import asyncio
import base64
import hashlib
import importlib
import io
import json
import os
import signal
import tempfile
import time
import wave
from dataclasses import replace
from pathlib import Path

import performance_cloud_comparison as previous
from performance_memory_target import DeliveryGuard, MemoryTarget, RunHandle
from performance_memory_target import failure_code as control_failure_code

ROOT = Path(__file__).resolve().parents[2]
POLISH_URL = "https://api.deepseek.com/chat/completions"
ASR_URL = previous.ASR_BASE + "/chat/completions"
REFS = {"qwen": "provider/qwen", "deepseek": "provider/deepseek"}
POLL_SECONDS = 0.02
SCENARIOS = ("normal", "cancel", "expire", "late")
ERROR_CODES = frozenset(
    {
        "configuration_invalid",
        "provider_metadata_mismatch",
        "request_not_allowed",
        "request_budget_exhausted",
        "unconfirmed_output",
        "credential_reference_rejected",
        "session_not_started",
        "producer_not_terminal",
        "arm_acceptance_failed",
        "cancel_acceptance_failed",
        "local_fixture_failed",
        "runtime_origin_mismatch",
        "result_metadata_invalid",
        "public_wave_changed",
        "reviewed_plan_changed",
        "observation_timeout",
        "reviewed_plan_required",
        "live_controls_required",
        "plan_only_flag_conflict",
        "noble_desktop_controls_not_prepared",
    }
)


def reject_credential_fields(value):
    forbidden = {
        "apikey",
        "xapikey",
        "apitoken",
        "accesstoken",
        "authorization",
        "password",
        "secret",
        "clientsecret",
        "clienttoken",
        "bearertoken",
        "auth",
        "authentication",
        "credentials",
        "cookie",
        "setcookie",
        "token",
    }
    if type(value) is dict:
        for key, child in value.items():
            normalized = "".join(char for char in key.lower() if "a" <= char <= "z")
            if normalized in forbidden:
                raise ProbeError("configuration_invalid")
            reject_credential_fields(child)
    elif type(value) is list:
        for child in value:
            reject_credential_fields(child)


class ProbeError(ValueError):
    """A fixed code, never a server/backend exception or response body."""


def error_code(error):
    if (
        type(error) is ProbeError
        and len(error.args) == 1
        and type(error.args[0]) is str
        and error.args[0] in ERROR_CODES
    ):
        return error.args[0]
    code = control_failure_code(error)
    return "comparison_failed" if code == "comparison_unexpected_failure" else code


def note_failure(handle, error):
    if "live_failure_code" not in handle.record:
        handle.record.update(
            live_failure_code=error_code(error), failed_phase=handle.record["phase"]
        )
        handle.save()


def read_metadata(config_root):
    """Only fixed provider references and hashes leave ordinary configuration."""
    records, hashes = {}, {}
    for name in ("config.json", "providers/qwen.json", "providers/deepseek.json"):
        path = config_root / name
        raw = path.read_bytes()
        if len(raw) > 100000:
            raise ProbeError("configuration_invalid")
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ProbeError("configuration_invalid") from None
        if (
            type(value) is not dict
            or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1
        ):
            raise ProbeError("configuration_invalid")
        reject_credential_fields(value)
        records[name] = value
        hashes[name] = hashlib.sha256(raw).hexdigest()
    settings = records["config.json"]
    if (
        settings.get("transcription_provider") != "qwen"
        or settings.get("polishing_provider") != "deepseek"
        or settings.get("sample_rate", 16000) != 16000
    ):
        raise ProbeError("configuration_invalid")
    for identifier, role, adapter, origin, models in (
        (
            "qwen",
            "transcription",
            "qwen",
            previous.ASR_BASE,
            {"qwen3-asr-flash", "qwen3-asr-flash-realtime"},
        ),
        (
            "deepseek",
            "polishing",
            "openai",
            "https://api.deepseek.com",
            {"deepseek-flash"},
        ),
    ):
        provider = records[f"providers/{identifier}.json"]
        if (
            provider.get("id") != identifier
            or provider.get("role") != role
            or provider.get("adapter") != adapter
            or provider.get("base_url") != origin
            or provider.get("model") not in models
            or provider.get("key_ref") != REFS[identifier]
        ):
            raise ProbeError("provider_metadata_mismatch")
    return {
        "hashes": hashes,
        "references": REFS.copy(),
        "selected_models": {
            identifier: records[f"providers/{identifier}.json"]["model"]
            for identifier in REFS
        },
    }


def plan(args):
    basic = previous.make_plan(
        args.appimage,
        args.package_root,
        owned_gtk=(args.live or args.plan_live) and args.node_kind == "host-xwayland",
        xdotool=args.xdotool,
    )
    scripts = [
        Path(__file__),
        previous.__file__,
        ROOT / "scripts/validation/performance_memory_target.py",
        ROOT / "scripts/validation/performance_comparison_fixture.py",
        ROOT / "scripts/validation/performance_host_a13.py",
        ROOT / "scripts/feasibility/owned_memory_text_fixture.py",
    ]
    value = {
        "schema_version": 1,
        "kind": "configuration_A_B_same_a13",
        "public_wave": basic["public_wave"],
        "package": basic["package"],
        "configuration": read_metadata(args.config_root),
        "snapshot": {Path(path).name: previous.digest(Path(path)) for path in scripts},
        "profiles": {
            "A": {"asr_url": ASR_URL, "asr_model": "qwen3-asr-flash", "stream": False},
            "B": {
                "asr_url": previous.ASR_WS,
                "asr_model": "qwen3-asr-flash-realtime",
                "stream": True,
            },
        },
        "polishing": {
            "url": POLISH_URL,
            "model": "deepseek-flash",
            "max_tokens": 128,
            "thinking": {"type": "disabled"},
            "prompt": previous.PROMPT,
        },
        "budget": {"per_arm_asr": 1, "per_arm_polishing": 1, "total": 4},
        "native_controls": basic["local_execution"]["native_controls"],
        "target_node": args.node_kind,
        "ubuntu24_desktop_controls_ready": False,
        "recording": "original_WAV_A_original_PCM_B_177_paced_chunks_17.645125_seconds",
        "fixture_activation": "before_recording_no_focus_reads_during_recording",
        "http_client_condition": "new_cold_client_per_arm_no_warmup",
        "buffer_observation_poll_ms": 20,
        "polishing_fallback": False,
        "timeout_seconds_per_role": 30,
        "discovery_calls": 0,
        "retries": 0,
        "real_microphone": False,
        "separate_human_authorization_required": True,
        "live_approved_by_plan": False,
    }
    return {**value, "plan_sha256": previous.fingerprint(value)}


class Budget:
    """Reserve at outbound boundaries, including failed sends; never retry."""

    def __init__(self, on_reserved=None):
        self.calls = {arm: {"asr": 0, "polishing": 0} for arm in ("A", "B")}
        self.on_reserved = on_reserved

    def reserve(self, arm, role):
        if arm not in self.calls or role not in self.calls[arm]:
            raise ProbeError("request_not_allowed")
        if (
            self.calls[arm][role]
            or sum(sum(row.values()) for row in self.calls.values()) >= 4
        ):
            raise ProbeError("request_budget_exhausted")
        self.calls[arm][role] += 1
        if self.on_reserved:
            self.on_reserved(
                arm, role, {name: row.copy() for name, row in self.calls.items()}
            )

    def http(self, arm, method, url, encoded, wav_sha):
        try:
            body = json.loads(encoded)
        except (ValueError, UnicodeError):
            raise ProbeError("request_not_allowed") from None
        if method != "POST" or type(body) is not dict:
            raise ProbeError("request_not_allowed")
        if type(body.get("messages")) is not list or any(
            type(message) is not dict for message in body["messages"]
        ):
            raise ProbeError("request_not_allowed")
        if url == ASR_URL and arm == "A" and body.get("model") == "qwen3-asr-flash":
            try:
                if (
                    set(body) != {"model", "messages", "stream"}
                    or body["stream"] is not False
                    or len(body["messages"]) != 1
                    or body["messages"][0].get("role") != "user"
                    or set(body["messages"][0]) != {"role", "content"}
                    or len(body["messages"][0]["content"]) != 1
                ):
                    raise ValueError
                item = body["messages"][0]["content"][0]
                if (
                    set(item) != {"type", "input_audio"}
                    or item["type"] != "input_audio"
                    or set(item["input_audio"]) != {"data"}
                ):
                    raise ValueError
                source = body["messages"][0]["content"][0]["input_audio"]["data"]
                prefix, audio = source.split(",", 1)
                if prefix != "data:audio/wav;base64":
                    raise ValueError
                import hashlib

                checksum = hashlib.sha256(
                    base64.b64decode(audio, validate=True)
                ).hexdigest()
                if checksum != wav_sha:
                    raise ValueError
            except (KeyError, IndexError, TypeError, ValueError):
                raise ProbeError("request_not_allowed") from None
            role = "asr"
        elif url == POLISH_URL and body.get("model") == "deepseek-flash":
            if (
                set(body) != {"model", "messages", "stream", "max_tokens", "thinking"}
                or type(body.get("max_tokens")) is not int
                or body.get("max_tokens") != 128
                or body.get("thinking") != {"type": "disabled"}
                or body.get("stream") is not (arm == "B")
                or type(body.get("messages")) is not list
                or len(body["messages"]) != 2
                or body["messages"][0] != {"role": "system", "content": previous.PROMPT}
                or set(body["messages"][1]) != {"role", "content"}
                or body["messages"][1]["role"] != "user"
                or type(body["messages"][1]["content"]) is not str
            ):
                raise ProbeError("request_not_allowed")
            role = "polishing"
        else:
            raise ProbeError("request_not_allowed")
        self.reserve(arm, role)

    def websocket(self, arm, config):
        if (
            arm != "B"
            or config.url != previous.ASR_WS
            or config.model != "qwen3-asr-flash-realtime"
        ):
            raise ProbeError("request_not_allowed")
        self.reserve(arm, "asr")


def guarded_transport(budget, arm, wav_sha, *, local=None):
    import httpx

    class Transport(httpx.AsyncBaseTransport):
        def __init__(self):
            self.inner = httpx.AsyncHTTPTransport(
                verify=local.context if local else True, trust_env=False, retries=0
            )

        async def handle_async_request(self, request):
            payload = await request.aread()
            budget.http(arm, request.method, str(request.url), payload, wav_sha)
            if local:
                # Check original production destination/body before routing fake-key
                # requests exclusively to this owned loopback TLS listener.
                url = httpx.URL(local.base + "/chat/completions")
                request = httpx.Request(
                    request.method,
                    url,
                    headers=[
                        (key, value)
                        for key, value in request.headers.raw
                        if key.lower() != b"host"
                    ],
                    content=payload,
                    extensions=request.extensions,
                )
            return await self.inner.handle_async_request(request)

        async def aclose(self):
            await self.inner.aclose()

    return Transport()


def guarded_realtime(budget, arm, *, local=None):
    from inkecho.realtime import QwenRealtimeSession

    class Connection:
        def __init__(self, config, key, **options):
            self.production_config = config
            actual = replace(config, endpoint=local.realtime_url) if local else config
            self.inner = QwenRealtimeSession(
                actual, key, tls_context=local.context if local else None, **options
            )

        async def start(self):
            budget.websocket(arm, self.production_config)
            await self.inner.start()

        def feed_nowait(self, pcm):
            self.inner.feed_nowait(pcm)

        async def finish(self):
            return await self.inner.finish()

        async def wait_failure(self):
            await self.inner.wait_failure()

        async def aclose(self):
            await self.inner.aclose()

    return Connection


class ExpectedOutput:
    """Only successful production-normalized inserts enter the RAM expectation."""

    def __init__(self, inputs):
        from inkecho.platform.keyboard import _text

        self.parts = []
        self.uncertain = False
        self.original = inputs.insert

        async def insert(text, *args, **options):
            if self.uncertain:
                raise ProbeError("unconfirmed_output")
            try:
                normalized = _text(text)
                count = await self.original(text, *args, **options)
                if type(count) is not int or count != len(normalized):
                    raise ProbeError("unconfirmed_output")
            except BaseException:
                self.uncertain = True
                raise
            self.parts.append(normalized)
            return count

        inputs.insert = insert

    def text(self):
        return "".join(self.parts)


class Credentials:
    def __init__(self, revalidate, *, live=False):
        self.revalidate, self.live, self.backend = revalidate, live, None

    def get(self, reference):
        if reference not in REFS.values():
            raise ProbeError("credential_reference_rejected")
        if not self.live:
            return "local-fixture-not-a-cloud-key"
        self.revalidate()  # Complete static/config fingerprint before backend init.
        if self.backend is None:
            from inkecho.security import SecretStore

            self.backend = SecretStore()
        return self.backend.get(reference)


def recorder(audio, pcm):
    from PySide6.QtCore import QObject, Signal

    class Replay(QObject):
        level = Signal(float)
        pcm_ready = Signal(bytes)
        finished = Signal(bytes, float)
        failed = Signal(str)

        def start(self, *_args, **options):
            self.streaming = options.get("streaming", False)
            self.started_at = time.monotonic()
            self.cancelled = False
            return True

        async def play(self):
            total = 0
            for offset in range(0, len(pcm), 3200):
                chunk = pcm[offset : offset + 3200]
                total += len(chunk)
                await asyncio.sleep(
                    max(0, self.started_at + total / 32000 - time.monotonic())
                )
                if self.cancelled:
                    return
                if self.streaming:
                    self.pcm_ready.emit(chunk)

        def stop(self):
            self.finished.emit(b"" if self.streaming else audio, len(pcm) / 32000)

        def cancel(self):
            self.cancelled = True

    return Replay()


def runtime_store(arm):
    from inkecho.config import Prompt, Provider, Settings

    class Store:
        def load_settings(self):
            return Settings(
                polishing_enabled=True,
                polishing_fallback=False,
                polishing_streaming=arm == "B",
                recording_limit_seconds=30,
            )

        def load_provider(self, identifier):
            if identifier == "qwen":
                return Provider(
                    "qwen",
                    "Fixed comparison",
                    "transcription",
                    "qwen",
                    previous.ASR_BASE,
                    "qwen3-asr-flash-realtime" if arm == "B" else "qwen3-asr-flash",
                    REFS[identifier],
                    {"asr_protocol": "qwen_realtime"} if arm == "B" else {},
                )
            return Provider(
                "deepseek",
                "Fixed comparison",
                "polishing",
                "openai",
                "https://api.deepseek.com",
                "deepseek-flash",
                REFS[identifier],
                {"max_tokens": 128},
            )

        def load_prompt(self, _identifier):
            return Prompt(
                "fixed-comparison", "Fixed public prompt", "", previous.PROMPT
            )

    return Store()


def install_cancel_signals(session):
    """Signals to the worker cancel its task; observer interruption is unrelated."""
    previous_handlers = {}
    cancelled = []

    def cancel(_signum, _frame):
        cancelled.append(True)
        session.cancel()

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, cancel)

    def restore_handlers():
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)

    return cancelled, restore_handlers


async def run_arm(
    arm, budget, audio, pcm, credentials, *, local=None, desktop=None, scenario="normal"
):
    import hashlib

    import httpx

    from inkecho.app import Session
    from inkecho.platform.keyboard import KeyboardInput
    from inkecho.providers import ProviderClient

    replay = recorder(audio, pcm)
    target = guard = None
    driver = previous.MemoryDriver() if desktop is None else None
    inputs = KeyboardInput(driver_factory=lambda: driver) if driver else KeyboardInput()
    await inputs.connect()
    mapping_before = inputs._driver._mapping() if desktop else None
    if desktop:
        target = MemoryTarget(
            desktop["handle"], desktop["xdotool"], **desktop.get("target_options", {})
        )
        try:
            await target.open(os.environ)
            await target.activate()  # Preparation, before the recording clock starts.
        except Exception as error:
            note_failure(desktop["handle"], error)
            await inputs.aclose()
            if hasattr(target, "process"):
                await target.close()
            raise
        guard = DeliveryGuard(inputs, [target])
    expected = ExpectedOutput(inputs)
    transport = guarded_transport(
        budget, arm, hashlib.sha256(audio).hexdigest(), local=local
    )
    async with httpx.AsyncClient(
        transport=transport, trust_env=False, follow_redirects=False
    ) as http:
        session = Session(
            runtime_store(arm),
            inputs=inputs,
            recorder=replay,
            client=ProviderClient(http=http),
            secrets=credentials,
            realtime_factory=guarded_realtime(budget, arm, local=local),
        )
        samples, diagnostics = [], []
        from performance_memory_target import diagnostic_code

        session.performance.connect(samples.append)
        session.diagnostic.connect(
            lambda code: (
                diagnostics.append(diagnostic_code(code))
                if len(diagnostics) < 32
                else None
            )
        )
        cancelled, restore_handlers = install_cancel_signals(session)
        first_buffer = None
        reads = 0
        try:
            await session.toggle()
            if not session.controller.task:
                raise ProbeError("session_not_started")
            task_id = session.controller.task.id
            focus_baseline = guard.focus_reads if guard else driver.focus_reads
            await replay.play()
            no_recording_focus = (
                guard.focus_reads if guard else driver.focus_reads
            ) == focus_baseline
            if not guard:
                driver.window = 21

                def on_press():
                    if len(driver.sent) == 2 and scenario == "cancel":
                        asyncio.get_running_loop().call_soon(session.cancel)
                    elif len(driver.sent) == 2 and scenario == "expire":
                        session.controller.task.deadline = time.monotonic() - 1
                        asyncio.get_running_loop().call_soon(session.controller.tick)

                driver.after_press = on_press
            stopped_at = time.monotonic()
            session.stop_recording()
            if scenario == "late":
                await previous.wait_until(local.requested.is_set)
                session.cancel()
                local.release.set()
            while not (samples and not session.pending):
                observed = (
                    await target.text()
                    if target
                    else "".join(c for _, c, _ in driver.sent)
                )
                reads += 1
                if observed and first_buffer is None:
                    first_buffer = (time.monotonic() - stopped_at) * 1000
                await asyncio.sleep(POLL_SECONDS)
            observed = (
                await target.text() if target else "".join(c for _, c, _ in driver.sent)
            )
            reads += 1
            if observed and first_buffer is None:
                first_buffer = (time.monotonic() - stopped_at) * 1000
            sent_before = guard.presses if guard else len(driver.sent)
            session.controller.transcribed(task_id, "late fixed fixture")
            session.controller.polished(task_id, "late fixed fixture")
            await asyncio.sleep(0.3)
            result = {
                "configuration": arm,
                "performance": samples[0],
                "calls": budget.calls[arm].copy(),
                "output_characters": len(observed),
                "confirmed_characters": len(expected.text()),
                "dispatch_characters": guard.presses if guard else len(driver.sent),
                "matched_releases": (guard.presses == guard.releases)
                if guard
                else len(driver.sent) == driver.releases,
                "exact_readback": observed == expected.text(),
                "unconfirmed_output": expected.uncertain,
                "recording_without_focus_reads": no_recording_focus,
                "no_tail_or_replay": (guard.presses if guard else len(driver.sent))
                == sent_before,
                "session_diagnostics": diagnostics,
                "explicit_signal_cancel": bool(cancelled),
                "first_buffer_observed_ms": round(first_buffer, 3)
                if first_buffer is not None
                else None,
                "first_dispatch_ms": samples[0]["durations_ms"][
                    "stop_to_first_character_ms"
                ],
                "late_response_attempted": local.late_response_attempted
                if local
                else False,
                "buffer_reads": reads,
                "buffer_poll_step_ms": 20,
                "buffer_observation_is_glyph_rendering": False,
                "cold_client_per_arm": True,
            }
            mapping_restored = (
                inputs._driver._mapping() == mapping_before if desktop else True
            )
        except Exception as error:
            if desktop:
                note_failure(desktop["handle"], error)
            raise
        finally:
            try:
                if desktop:
                    await desktop["handle"].observe(session.close(), "session_close")
                else:
                    await session.close()
                if any(not task.done() for task in session.pending | session.ui_tasks):
                    raise ProbeError("producer_not_terminal")
                if target:
                    await target.close()
            finally:
                restore_handlers()
        result["mapping_restored_and_driver_closed"] = (
            mapping_restored and not inputs.connected
        )
        result["target_exit_zero"] = not target or (
            target.item["owner_observed_terminal"] and target.item["exit_code"] == 0
        )
    return result


def accept(result, *, scenario="normal"):
    if not all(
        result[name] is True
        for name in (
            "recording_without_focus_reads",
            "no_tail_or_replay",
            "mapping_restored_and_driver_closed",
            "target_exit_zero",
            "cold_client_per_arm",
            "matched_releases",
        )
    ):
        raise ProbeError("arm_acceptance_failed")
    if scenario == "normal":
        if (
            result["performance"]["outcome"] != "succeeded"
            or not result["exact_readback"]
            or result["unconfirmed_output"]
            or result["confirmed_characters"] == 0
            or result["calls"] != {"asr": 1, "polishing": 1}
            or result["dispatch_characters"] != result["confirmed_characters"]
            or result["output_characters"] != result["confirmed_characters"]
            or result["session_diagnostics"]
        ):
            raise ProbeError("arm_acceptance_failed")
        import math

        first, buffer = result["first_dispatch_ms"], result["first_buffer_observed_ms"]
        completed = result["performance"]["durations_ms"].get(
            "stop_to_output_completed_ms"
        )
        if (
            any(
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 <= value <= 86400000
                for value in (first, buffer, completed)
            )
            or buffer + 0.001 < first
            or completed < first
            or result["performance"]["durations_ms"].get("stop_to_first_character_ms")
            != first
        ):
            raise ProbeError("arm_acceptance_failed")
    elif result["performance"]["outcome"] not in {"failed", "cancelled"}:
        raise ProbeError("cancel_acceptance_failed")
    elif scenario in {"cancel", "expire"}:
        if (
            result["output_characters"] != 2
            or result["dispatch_characters"] != 2
            or not result["unconfirmed_output"]
            or not 0 <= result["confirmed_characters"] < 2
            or result["calls"] != {"asr": 1, "polishing": 1}
        ):
            raise ProbeError("cancel_acceptance_failed")
    elif scenario == "late":
        if (
            result["output_characters"] != 0
            or result["dispatch_characters"] != 0
            or result["confirmed_characters"] != 0
            or result["calls"] != {"asr": 1, "polishing": 0}
            or not result["late_response_attempted"]
        ):
            raise ProbeError("cancel_acceptance_failed")


async def offline(scenario="normal"):
    from performance_comparison_fixture import PCM, Fixture, audio_bytes

    results, budget = [], Budget()
    with tempfile.TemporaryDirectory(prefix="inkecho-live-offline-") as temporary:
        for arm in ("A", "B"):
            folder = Path(temporary) / arm
            folder.mkdir()
            async with Fixture(folder, late=scenario == "late") as local:
                row = await run_arm(
                    arm,
                    budget,
                    audio_bytes(),
                    PCM,
                    Credentials(lambda: None),
                    local=local,
                    scenario=scenario,
                )
                row = safe_result(row)
                accept(row, scenario=scenario)
                if local.errors:
                    raise ProbeError("local_fixture_failed")
                results.append(row)
    return {
        "evidence_kind": "source_protocol_synthetic_display",
        "cloud_validated": False,
        "desktop_validated": False,
        "microphone_used": False,
        "public_wave_uploaded": False,
        "results": results,
    }


def audit_runtime(package_root):
    origins = previous.audit_runtime(package_root)
    path = Path(importlib.import_module("inkecho.security").__file__).resolve()
    if not path.is_relative_to(package_root.resolve()):
        raise ProbeError("runtime_origin_mismatch")
    inventory = json.loads(
        (package_root.parent / "usr/share/doc/inkecho/inventory.json").read_text()
    )
    checksum = previous.digest(path)
    if inventory["files"][str(path.relative_to(package_root.parent))] != checksum:
        raise ProbeError("runtime_origin_mismatch")
    return {**origins, "inkecho.security": checksum}


def safe_result(row):
    from performance_memory_target import diagnostic_code

    from inkecho.performance import validate_snapshot

    keys = {
        "configuration",
        "performance",
        "calls",
        "output_characters",
        "confirmed_characters",
        "dispatch_characters",
        "matched_releases",
        "exact_readback",
        "unconfirmed_output",
        "recording_without_focus_reads",
        "no_tail_or_replay",
        "session_diagnostics",
        "explicit_signal_cancel",
        "first_buffer_observed_ms",
        "first_dispatch_ms",
        "late_response_attempted",
        "buffer_reads",
        "buffer_poll_step_ms",
        "buffer_observation_is_glyph_rendering",
        "cold_client_per_arm",
        "mapping_restored_and_driver_closed",
        "target_exit_zero",
    }
    if (
        type(row) is not dict
        or set(row) != keys
        or row["configuration"] not in {"A", "B"}
    ):
        raise ProbeError("result_metadata_invalid")
    import math

    result = {
        "configuration": row["configuration"],
        "performance": validate_snapshot(row["performance"]),
    }
    for name in keys - {"configuration", "performance", "calls", "session_diagnostics"}:
        value = row[name]
        if name in {
            "output_characters",
            "confirmed_characters",
            "dispatch_characters",
            "buffer_reads",
            "buffer_poll_step_ms",
        }:
            valid = type(value) is int and 0 <= value <= 1000000
        elif name in {"first_buffer_observed_ms", "first_dispatch_ms"}:
            valid = value is None or (
                type(value) in (int, float)
                and math.isfinite(value)
                and 0 <= value <= 86400000
            )
        else:
            valid = type(value) is bool
        if not valid:
            raise ProbeError("result_metadata_invalid")
        result[name] = value
    calls = row["calls"]
    if (
        type(calls) is not dict
        or set(calls) != {"asr", "polishing"}
        or any(type(n) is not int or not 0 <= n <= 1 for n in calls.values())
    ):
        raise ProbeError("result_metadata_invalid")
    result["calls"] = calls.copy()
    result["session_diagnostics"] = [
        diagnostic_code(code) for code in row["session_diagnostics"][:32]
    ]
    return result


async def live_pair(args, reviewed, desktop):
    """Prepared but unexecuted cloud path; no access occurs in default/offline."""
    import hashlib

    audio = previous.WAV.read_bytes()
    if hashlib.sha256(audio).hexdigest() != previous.WAV_SHA:
        raise ProbeError("public_wave_changed")
    with wave.open(io.BytesIO(audio), "rb") as wav:
        pcm = wav.readframes(wav.getnframes())

    def revalidate():
        current = plan(args)
        if current["plan_sha256"] != reviewed["plan_sha256"]:
            raise ProbeError("reviewed_plan_changed")

    credentials = Credentials(revalidate, live=True)

    def checkpoint(arm, role, counts):
        handle = desktop["handle"]
        handle.record["reserved_calls"] = counts
        handle.phase(f"{arm}_{role}_reserved")

    rows, budget = [], Budget(checkpoint)
    for arm in ("A", "B"):
        revalidate()
        row = safe_result(
            await run_arm(arm, budget, audio, pcm, credentials, desktop=desktop)
        )
        desktop["handle"].record.setdefault("live_arm_metadata", []).append(row)
        desktop["handle"].phase("arm_acceptance")
        accept(row)
        if desktop["handle"].timed_out:
            raise ProbeError("observation_timeout")
        rows.append(row)
    return {
        "evidence_kind": "live_cloud_owned_GTK",
        "configuration_comparison_not_version_baseline": True,
        "node_kind": args.node_kind,
        "real_microphone": False,
        "public_wave_uploaded": True,
        "results": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument(
        "--appimage", type=Path, default=ROOT / "dist/InkEcho-0.1.0a13-x86_64.AppImage"
    )
    parser.add_argument(
        "--config-root", type=Path, default=Path.home() / ".config/inkecho"
    )
    parser.add_argument(
        "--node-kind",
        choices=("ubuntu24-xorg", "host-xwayland"),
        default="ubuntu24-xorg",
    )
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--offline", action="store_true")
    choice.add_argument("--live", action="store_true")
    parser.add_argument("--plan-live", action="store_true")
    parser.add_argument("--accept-plan-sha")
    parser.add_argument("--xdotool", type=Path)
    parser.add_argument("--handle", type=Path)
    parser.add_argument("--scenario", choices=SCENARIOS, default="normal")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    desktop = None
    try:
        if args.plan_live and (args.offline or args.live):
            raise ProbeError("plan_only_flag_conflict")
        reviewed = plan(args)
        if not args.offline and not args.live:
            print(json.dumps(reviewed, indent=2))
            return 0
        if args.accept_plan_sha != reviewed["plan_sha256"]:
            raise ProbeError("reviewed_plan_required")
        if args.live and (
            args.scenario != "normal" or args.handle is None or args.xdotool is None
        ):
            raise ProbeError("live_controls_required")
        if args.live and args.node_kind == "ubuntu24-xorg":
            # Core Session/WAV/egress code is portable. The separately reviewed
            # Noble native-controls/preflight route is still necessary, and must
            # never silently fall back to a different desktop or key source.
            raise ProbeError("noble_desktop_controls_not_prepared")
        if not args.worker:
            import subprocess

            appdir = args.package_root.resolve().parent
            command = [
                str(appdir / "usr/bin/python3"),
                str(Path(__file__).resolve()),
                "--package-root",
                str(args.package_root.resolve()),
                "--appimage",
                str(args.appimage.resolve()),
                "--config-root",
                str(args.config_root.resolve()),
                "--node-kind",
                args.node_kind,
                "--live" if args.live else "--offline",
                "--scenario",
                args.scenario,
                "--accept-plan-sha",
                args.accept_plan_sha,
                "--worker",
            ]
            if args.live:
                command += [
                    "--xdotool",
                    str(args.xdotool.resolve()),
                    "--handle",
                    str(args.handle.resolve()),
                ]
            if args.live:
                profile = persistent_profile(args.handle.resolve())
                environment = previous.worker_environment(
                    args.package_root.resolve(), profile, owned_gtk=True
                )
                return previous.launch_owned_worker(
                    command, environment, args.handle.resolve()
                )
            with tempfile.TemporaryDirectory(
                prefix="inkecho-cloud-worker-"
            ) as temporary:
                environment = previous.worker_environment(
                    args.package_root.resolve(), Path(temporary)
                )
                return subprocess.run(command, env=environment, check=False).returncode
        origins = audit_runtime(args.package_root.resolve())
        previous.verify_production_profiles()
        desktop = previous.owned_worker(args) if args.live else None
        from PySide6.QtWidgets import QApplication

        application = QApplication.instance() or QApplication([])
        application.setQuitOnLastWindowClosed(False)
        if args.live:
            from inkecho.runtime import ManagedQtEventLoop

            with ManagedQtEventLoop(application) as loop:
                asyncio.set_event_loop(loop)
                report = loop.run_until_complete(live_pair(args, reviewed, desktop))
        else:
            report = asyncio.run(offline(args.scenario))
            report["evidence_kind"] = "package_protocol_synthetic_display"
        report["runtime_origins"] = origins
        report["plan_sha256"] = reviewed["plan_sha256"]
        print(json.dumps(report, indent=2, allow_nan=False))
        return 0
    except Exception as error:
        code = error_code(error)
        if args.worker and args.live and args.handle and args.handle.exists():
            handle = desktop["handle"] if desktop else RunHandle(args.handle)
            if (
                handle.record["producer"]
                and handle.record["producer"]["pid"] == os.getpid()
            ):
                note_failure(handle, error)
        print(json.dumps({"status": "failed", "code": code}))
        return 1


def persistent_profile(handle):
    """Live worker resources outlive an interrupted observer; never auto-delete."""
    if handle.exists():
        raise ProbeError("live_controls_required")
    handle.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    profile = handle.parent / "worker-profile"
    profile.mkdir(mode=0o700, exist_ok=False)
    return profile


if __name__ == "__main__":
    raise SystemExit(main())
