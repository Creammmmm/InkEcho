"""No cloud/GUI/keyring: plan, outbound budgets and local Session pipelines."""

import asyncio
import base64
import hashlib
import importlib.util
import json
import signal
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts/validation/performance_live_comparison.py"
)
SPEC = importlib.util.spec_from_file_location("performance_live_comparison", PATH)


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.syspath_prepend(str(PATH.parent))
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    return module


@pytest.fixture
def config(tmp_path, probe):
    (tmp_path / "providers").mkdir()
    records = {
        "config.json": {
            "schema_version": 1,
            "transcription_provider": "qwen",
            "polishing_provider": "deepseek",
            "sample_rate": 16000,
        },
        "providers/qwen.json": {
            "schema_version": 1,
            "id": "qwen",
            "role": "transcription",
            "adapter": "qwen",
            "base_url": probe.previous.ASR_BASE,
            "model": "qwen3-asr-flash",
            "key_ref": "provider/qwen",
            "name": "PRIVATE LABEL",
            "parameters": {},
        },
        "providers/deepseek.json": {
            "schema_version": 1,
            "id": "deepseek",
            "role": "polishing",
            "adapter": "openai",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-flash",
            "key_ref": "provider/deepseek",
            "parameters": {},
        },
    }
    for name, value in records.items():
        (tmp_path / name).write_text(json.dumps(value))
    return tmp_path


def test_plan_only_metadata_is_read_only_and_contains_no_private_labels(
    config, probe, monkeypatch
):
    before = {p: p.read_bytes() for p in config.rglob("*.json")}
    monkeypatch.setattr(
        probe.previous,
        "make_plan",
        lambda *_a, **_k: {
            "public_wave": {"sha256": probe.previous.WAV_SHA},
            "package": {"version": "a13"},
            "local_execution": {"native_controls": None},
        },
    )
    args = SimpleNamespace(
        appimage=Path("/not-read"),
        package_root=Path("/not-read"),
        live=False,
        plan_live=False,
        xdotool=None,
        node_kind="ubuntu24-xorg",
        config_root=config,
    )
    value = probe.plan(args)
    assert value["configuration"]["references"] == probe.REFS
    assert value["budget"]["total"] == 4 and value["live_approved_by_plan"] is False
    assert "PRIVATE LABEL" not in json.dumps(value)
    assert before == {p: p.read_bytes() for p in config.rglob("*.json")}
    assert value["ubuntu24_desktop_controls_ready"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("base_url", "https://unknown.invalid"),
        ("model", "other"),
        ("key_ref", "sk-MISFILLED-KEY"),
        ("role", "polishing"),
    ],
)
def test_unknown_provider_metadata_fails_without_echo(config, probe, field, value):
    path = config / "providers/qwen.json"
    body = json.loads(path.read_text())
    body[field] = value
    path.write_text(json.dumps(body))
    with pytest.raises(probe.ProbeError, match="provider_metadata_mismatch"):
        probe.read_metadata(config)


def asr_request(audio):
    return {
        "model": "qwen3-asr-flash",
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": "data:audio/wav;base64,"
                            + base64.b64encode(audio).decode()
                        },
                    }
                ],
            }
        ],
    }


def polish_request(probe, arm):
    from inkecho.providers import polishing_request_body

    return polishing_request_body(
        probe.runtime_store(arm).load_provider("deepseek"),
        "RAM ONLY TRANSCRIPT",
        probe.previous.PROMPT,
        stream=arm == "B",
    )


def test_exact_four_reservations_and_no_retries(probe):
    from inkecho.realtime import RealtimeConfig

    budget, audio = probe.Budget(), b"public fixture bytes"
    checksum = hashlib.sha256(audio).hexdigest()
    budget.http("A", "POST", probe.ASR_URL, json.dumps(asr_request(audio)), checksum)
    budget.http(
        "A", "POST", probe.POLISH_URL, json.dumps(polish_request(probe, "A")), checksum
    )
    budget.websocket(
        "B",
        RealtimeConfig.from_provider(probe.runtime_store("B").load_provider("qwen")),
    )
    budget.http(
        "B", "POST", probe.POLISH_URL, json.dumps(polish_request(probe, "B")), checksum
    )
    assert budget.calls == {
        "A": {"asr": 1, "polishing": 1},
        "B": {"asr": 1, "polishing": 1},
    }
    with pytest.raises(probe.ProbeError, match="request_budget_exhausted"):
        budget.http(
            "B",
            "POST",
            probe.POLISH_URL,
            json.dumps(polish_request(probe, "B")),
            checksum,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "get",
        "url",
        "model",
        "audio",
        "extra_message",
        "thinking",
        "tokens",
        "stream",
        "extra_field",
    ],
)
def test_wrong_outbound_request_is_rejected_before_reservation(probe, mutation):
    budget, audio = probe.Budget(), b"fixed"
    body, url, method = polish_request(probe, "A"), probe.POLISH_URL, "POST"
    if mutation == "get":
        method = "GET"
    elif mutation == "url":
        url += "?private=never-send"
    elif mutation == "model":
        body["model"] = "other"
    elif mutation in {"audio", "extra_message"}:
        body, url = asr_request(audio), probe.ASR_URL
        if mutation == "audio":
            audio = b"different"
        else:
            body["messages"].append({"role": "user", "content": "PRIVATE"})
    elif mutation == "thinking":
        body["thinking"] = {"type": "enabled"}
    elif mutation == "tokens":
        body["max_tokens"] = 129
    elif mutation == "stream":
        body["stream"] = True
    else:
        body["tools"] = ["PRIVATE"]
    with pytest.raises(probe.ProbeError, match="request_not_allowed"):
        budget.http(
            "A", method, url, json.dumps(body), hashlib.sha256(audio).hexdigest()
        )
    assert all(n == 0 for row in budget.calls.values() for n in row.values())


def test_transport_consumes_budget_before_even_failed_send(probe):
    import httpx

    async def run():
        budget, audio = probe.Budget(), b"fixed"
        transport = probe.guarded_transport(
            budget, "A", hashlib.sha256(audio).hexdigest()
        )
        await transport.inner.aclose()
        sent = []

        class NeverNetwork:
            async def handle_async_request(self, request):
                assert budget.calls["A"]["asr"] == 1
                sent.append(str(request.url))
                raise RuntimeError("PRIVATE ERROR")

            async def aclose(self):
                pass

        transport.inner = NeverNetwork()
        request = httpx.Request("POST", probe.ASR_URL, json=asr_request(audio))
        with pytest.raises(RuntimeError):
            await transport.handle_async_request(request)
        with pytest.raises(probe.ProbeError, match="request_budget_exhausted"):
            await transport.handle_async_request(request)
        assert sent == [probe.ASR_URL]
        await transport.aclose()

    asyncio.run(run())


def test_wss_reserve_precedes_start_and_failure_does_not_reconnect(probe, monkeypatch):
    from inkecho import realtime

    budget, starts = probe.Budget(), []

    class Fake:
        def __init__(self, *_a, **_k):
            pass

        async def start(self):
            assert budget.calls["B"]["asr"] == 1
            starts.append(True)
            raise RuntimeError("PRIVATE ERROR")

    monkeypatch.setattr(realtime, "QwenRealtimeSession", Fake)
    config = realtime.RealtimeConfig.from_provider(
        probe.runtime_store("B").load_provider("qwen")
    )
    connection = probe.guarded_realtime(budget, "B")(config, "fake-key")

    async def run():
        with pytest.raises(RuntimeError):
            await connection.start()
        with pytest.raises(probe.ProbeError, match="request_budget_exhausted"):
            await connection.start()

    asyncio.run(run())
    assert starts == [True]


def test_credentials_fake_offline_and_revalidate_before_lazy_backend(
    probe, monkeypatch, tmp_path
):
    from inkecho import security

    events = []
    monkeypatch.setattr(
        security, "FileCredentialStore", lambda: pytest.fail("no actual keyring")
    )
    assert (
        probe.Credentials(lambda: pytest.fail("offline no live validation")).get(
            "provider/qwen"
        )
        == "local-fixture-not-a-cloud-key"
    )
    with pytest.raises(probe.ProbeError):
        probe.Credentials(lambda: None).get("misfilled-ref")

    def fake_backend(root):
        assert root == tmp_path
        events.append("backend")
        return SimpleNamespace(get=lambda ref: events.append(ref) or "fake-key")

    monkeypatch.setattr(security, "FileCredentialStore", fake_backend)
    credentials = probe.Credentials(
        lambda: events.append("validated"), live=True, config_root=tmp_path
    )
    assert credentials.backend is None
    assert credentials.get("provider/qwen") == "fake-key"
    assert events == ["validated", "backend", "provider/qwen"]
    assert credentials.get("provider/deepseek") == "fake-key"
    assert events[-2:] == ["validated", "provider/deepseek"]


def test_revalidation_failure_never_initializes_credentials(
    probe, monkeypatch, tmp_path
):
    from inkecho import security

    monkeypatch.setattr(
        security, "FileCredentialStore", lambda: pytest.fail("must not initialize")
    )

    def changed():
        raise probe.ProbeError("reviewed_plan_changed")

    with pytest.raises(probe.ProbeError, match="reviewed_plan_changed"):
        probe.Credentials(changed, live=True, config_root=tmp_path).get("provider/qwen")


def test_original_wav_not_reencoded_and_pcm_tail_has_full_timeline(probe, monkeypatch):
    clock, sleeps = [100.0], []

    async def sleep(delay):
        sleeps.append(delay)
        clock[0] += delay

    monkeypatch.setattr(probe, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(probe, "asyncio", SimpleNamespace(sleep=sleep))
    original = b"original pinned WAV bytes including metadata"
    pcm = bytes(564644)
    for streaming in (False, True):
        replay = probe.recorder(original, pcm)
        chunks, outputs = [], []
        replay.pcm_ready.connect(chunks.append)
        replay.finished.connect(
            lambda data, duration, outputs=outputs: outputs.append((data, duration))
        )
        replay.start(streaming=streaming)
        started = clock[0]
        asyncio.run(replay.play())
        replay.stop()
        assert clock[0] - started == pytest.approx(17.645125)
        assert outputs == [(b"" if streaming else original, 17.645125)]
        if streaming:
            assert len(chunks) == 177 and len(chunks[-1]) == 1444
            assert b"".join(chunks) == pcm
    assert len(sleeps) == 354


def test_expected_only_normalized_confirmed_counts_and_partial_never_replayed(probe):
    class Inputs:
        async def insert(self, _text, *_a, **_k):
            return 3

    inputs = Inputs()
    expected = probe.ExpectedOutput(inputs)

    async def run():
        assert await inputs.insert("中\r\nΩ") == 3
        assert expected.text() == "中\nΩ"
        with pytest.raises(probe.ProbeError, match="unconfirmed_output"):
            await inputs.insert("longer text")
        with pytest.raises(probe.ProbeError, match="unconfirmed_output"):
            await inputs.insert("中\r\nΩ")
        assert expected.text() == "中\nΩ"

    asyncio.run(run())


def test_worker_signal_calls_cancel_and_restores_handlers(probe, monkeypatch):
    handlers, cancelled = {}, []

    def install(signum, callback):
        old = handlers.get(signum, "original")
        handlers[signum] = callback
        return old

    monkeypatch.setattr(probe.signal, "signal", install)
    marks, restore = probe.install_cancel_signals(
        SimpleNamespace(cancel=lambda: cancelled.append(True))
    )
    handlers[signal.SIGTERM](signal.SIGTERM, None)
    assert marks and cancelled == [True]
    restore()
    assert set(handlers.values()) == {"original"}


@pytest.mark.parametrize("scenario", ["normal", "cancel", "expire", "late"])
def test_real_local_tls_session_pipelines_never_initialize_keyring(
    probe, scenario, monkeypatch
):
    from inkecho import security

    monkeypatch.setattr(
        security,
        "FileCredentialStore",
        lambda: pytest.fail("offline must never initialize keyring"),
    )
    report = asyncio.run(probe.offline(scenario))
    assert report["evidence_kind"] == "source_protocol_synthetic_display"
    assert not report["cloud_validated"] and not report["desktop_validated"]
    assert len(report["results"]) == 2
    serialized = json.dumps(report, ensure_ascii=False)
    assert (
        "固定转写" not in serialized
        and "中Ω" not in serialized
        and "local-fixture-not-a-cloud-key" not in serialized
    )
    for row in report["results"]:
        probe.safe_result(row)
        probe.accept(row, scenario=scenario)
        if scenario == "normal":
            assert row["exact_readback"] and row["output_characters"] == 6
            assert row["first_buffer_observed_ms"] > 0
        elif scenario == "late":
            assert row["output_characters"] == 0


def test_default_cli_and_bad_live_plan_are_before_runtime_and_credentials(
    probe, monkeypatch, capsys
):
    monkeypatch.setattr(probe, "plan", lambda _args: {"plan_sha256": "reviewed"})
    monkeypatch.setattr(probe, "audit_runtime", lambda *_a: pytest.fail("no runtime"))
    assert probe.main(["--package-root", "/not-read"]) == 0
    assert json.loads(capsys.readouterr().out)["plan_sha256"] == "reviewed"
    assert (
        probe.main(
            ["--package-root", "/not-read", "--live", "--accept-plan-sha", "wrong"]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["code"] == "reviewed_plan_required"
    assert (
        probe.main(
            [
                "--package-root",
                "/not-read",
                "--live",
                "--accept-plan-sha",
                "reviewed",
                "--handle",
                "/not-created",
                "--xdotool",
                "/not-read",
            ]
        )
        == 1
    )
    assert (
        json.loads(capsys.readouterr().out)["code"]
        == "noble_desktop_controls_not_prepared"
    )


def test_unknown_exception_never_prints_message_or_traceback(
    probe, monkeypatch, capsys
):
    def failed(_args):
        raise RuntimeError("PRIVATE KEY TRANSCRIPT")

    monkeypatch.setattr(probe, "plan", failed)
    assert probe.main(["--package-root", "/not-read"]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out) == {"status": "failed", "code": "comparison_failed"}
    assert output.err == "" and "PRIVATE" not in output.out


def fixture_row():
    return {
        "configuration": "A",
        "performance": {
            "outcome": "succeeded",
            "durations_ms": {
                "stop_to_first_character_ms": 20.0,
                "stop_to_output_completed_ms": 40.0,
            },
        },
        "calls": {"asr": 1, "polishing": 1},
        "output_characters": 6,
        "confirmed_characters": 6,
        "dispatch_characters": 6,
        "matched_releases": True,
        "exact_readback": True,
        "unconfirmed_output": False,
        "recording_without_focus_reads": True,
        "no_tail_or_replay": True,
        "session_diagnostics": [],
        "explicit_signal_cancel": False,
        "first_buffer_observed_ms": 30.0,
        "first_dispatch_ms": 20.0,
        "late_response_attempted": True,
        "buffer_reads": 5,
        "buffer_poll_step_ms": 20,
        "buffer_observation_is_glyph_rendering": False,
        "cold_client_per_arm": True,
        "mapping_restored_and_driver_closed": True,
        "target_exit_zero": True,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("first_dispatch_ms", None),
        ("first_dispatch_ms", float("nan")),
        ("first_buffer_observed_ms", None),
        ("first_buffer_observed_ms", 1),
        ("session_diagnostics", ["injection_failed"]),
        ("dispatch_characters", 7),
        ("output_characters", 7),
    ],
)
def test_normal_cli_acceptance_rejects_missing_or_invalid_measurement(
    probe, field, value
):
    row = fixture_row()
    probe.accept(row)
    row[field] = value
    with pytest.raises(probe.ProbeError, match="arm_acceptance_failed"):
        probe.accept(row)


@pytest.mark.parametrize("value", [None, 21.0])
def test_normal_acceptance_requires_authoritative_dispatch_measurement(probe, value):
    row = fixture_row()
    row["performance"]["durations_ms"]["stop_to_first_character_ms"] = value
    with pytest.raises(probe.ProbeError, match="arm_acceptance_failed"):
        probe.accept(row)


@pytest.mark.parametrize("value", [None, 19.0, float("nan")])
def test_normal_acceptance_requires_output_completion_measurement(probe, value):
    row = fixture_row()
    row["performance"]["durations_ms"]["stop_to_output_completed_ms"] = value
    with pytest.raises(probe.ProbeError, match="arm_acceptance_failed"):
        probe.accept(row)


@pytest.mark.parametrize("execution_flag", ["--offline", "--live"])
def test_plan_live_flag_is_only_accepted_for_pure_planning(
    probe, monkeypatch, capsys, execution_flag
):
    monkeypatch.setattr(probe, "plan", lambda *_a: pytest.fail("conflicting flags"))
    assert (
        probe.main(["--package-root", "/not-read", "--plan-live", execution_flag]) == 1
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "failed",
        "code": "plan_only_flag_conflict",
    }


@pytest.mark.parametrize("scenario", ["cancel", "expire", "late"])
@pytest.mark.parametrize("mutation", ["full_replay", "late_polish", "no_tail_false"])
def test_cli_negative_acceptance_itself_rejects_false_pass(probe, scenario, mutation):
    row = fixture_row()
    row["performance"]["outcome"] = "cancelled" if scenario != "expire" else "failed"
    row.update(
        output_characters=0 if scenario == "late" else 2,
        dispatch_characters=0 if scenario == "late" else 2,
        confirmed_characters=0,
        unconfirmed_output=scenario != "late",
    )
    if scenario == "late":
        row["calls"]["polishing"] = 0
    probe.accept(row, scenario=scenario)
    if mutation == "full_replay":
        row.update(output_characters=6, dispatch_characters=6)
    elif mutation == "late_polish":
        row["calls"]["polishing"] = 1 if scenario == "late" else 0
    else:
        row["no_tail_or_replay"] = False
    with pytest.raises(probe.ProbeError):
        probe.accept(row, scenario=scenario)


def test_reservation_callback_is_before_send_and_detached(probe):
    events = []
    budget = probe.Budget(lambda arm, role, counts: events.append((arm, role, counts)))
    budget.reserve("A", "asr")
    assert events == [
        ("A", "asr", {"A": {"asr": 1, "polishing": 0}, "B": {"asr": 0, "polishing": 0}})
    ]
    events[0][2]["A"]["asr"] = 99
    assert budget.calls["A"]["asr"] == 1


def test_live_profile_persists_and_existing_run_is_never_overwritten(probe, tmp_path):
    handle = tmp_path / "exclusive/handle.json"
    profile = probe.persistent_profile(handle)
    (profile / "retained-marker").write_text("fixed synthetic metadata")
    assert profile.stat().st_mode & 0o777 == 0o700
    assert (profile / "retained-marker").exists()
    with pytest.raises(FileExistsError):
        probe.persistent_profile(handle)
    handle.write_text("{}")
    with pytest.raises(probe.ProbeError, match="live_controls_required"):
        probe.persistent_profile(handle)


def test_fixed_failure_phase_and_reservations_survive_cleanup(probe, tmp_path):
    handle = probe.RunHandle.create(tmp_path / "handle.json")
    budget = probe.Budget(
        lambda arm, role, counts: (
            handle.record.update(reserved_calls=counts),
            handle.phase(f"{arm}_{role}_reserved"),
        )
    )
    budget.reserve("A", "asr")
    probe.note_failure(handle, probe.ProbeError("request_not_allowed"))
    handle.phase("target_exit")
    probe.note_failure(handle, RuntimeError("PRIVATE KEY AND TRANSCRIPT"))
    record = json.loads(handle.path.read_text())
    assert record["failed_phase"] == "A_asr_reserved"
    assert record["live_failure_code"] == "request_not_allowed"
    assert record["reserved_calls"]["A"]["asr"] == 1
    assert "PRIVATE" not in handle.path.read_text()


def test_safe_result_rejects_extra_body_field(probe):
    from inkecho.performance import TaskTiming

    row = fixture_row()
    row["performance"] = TaskTiming().finish("succeeded")
    assert probe.safe_result(row)["configuration"] == "A"
    row["text"] = "PRIVATE"
    with pytest.raises(probe.ProbeError, match="result_metadata_invalid"):
        probe.safe_result(row)


def test_credential_shaped_saved_field_is_not_promoted_to_metadata(probe, config):
    path = config / "providers/qwen.json"
    record = json.loads(path.read_text())
    record["parameters"]["api_key"] = "PRIVATE"
    path.write_text(json.dumps(record))
    with pytest.raises(probe.ProbeError, match="configuration_invalid"):
        probe.read_metadata(config)


def test_clean_import_has_no_application_qt_network_or_keyring_runtime(probe):
    import subprocess
    import sys

    program = (
        "import sys,runpy; "
        f"sys.path.insert(0,{str(PATH.parent)!r}); "
        f"runpy.run_path({str(PATH)!r},run_name='not_main'); "
        "names=('inkecho','PySide6','httpx','websockets','keyring'); "
        "assert not any(name.startswith(names) for name in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", program], capture_output=True)
    assert result.returncode == 0
