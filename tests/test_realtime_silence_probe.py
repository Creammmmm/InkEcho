"""Generated-silence probe guards; fake keys and optional real loopback WSS."""

import asyncio
import base64
import importlib.util
import json
import ssl
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from inkecho.config import ConfigError, ConfigStore, Provider, Settings
from inkecho.providers import ProviderError, Result, Usage
from inkecho.realtime import RealtimeConfig

PATH = (
    Path(__file__).resolve().parents[1] / "scripts/validation/realtime_silence_probe.py"
)
SPEC = importlib.util.spec_from_file_location("realtime_silence_probe", PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def current_provider(
    base="https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
):
    return Provider(
        "qwen",
        "Fixture",
        "transcription",
        "qwen",
        base,
        "qwen3-asr-flash",
        "synthetic-ref",
        {"asr_options": {"enable_itn": False}},
    )


def config_files(root, provider=None):
    store = ConfigStore(root)
    store.save_settings(Settings())
    store.save_provider(provider or current_provider())
    return store, {p: p.read_bytes() for p in root.rglob("*.json")}


@pytest.mark.parametrize("options", [[], ["--handshake-only"]])
def test_no_live_flag_reads_no_config_key_or_network(monkeypatch, capsys, options):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("opt-in guard must run before access")

    monkeypatch.setattr(probe, "ConfigStore", forbidden)
    monkeypatch.setattr(probe, "SecretStore", forbidden)
    monkeypatch.setattr(probe, "ObservedSession", forbidden)
    assert probe.main(options) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "live_opt_in_required"


@pytest.mark.parametrize(
    "host",
    [
        "dashscope.aliyuncs.com",
        "dashscope-intl.aliyuncs.com",
        "ws-example.cn-beijing.maas.aliyuncs.com",
        "llm-example.ap-southeast-1.maas.aliyuncs.com",
    ],
)
def test_official_origin_and_copied_model_do_not_modify_current_profile(host):
    provider = current_provider(f"https://{host}/compatible-mode/v1")
    original = dict(provider.parameters)
    config = probe.official_config(provider)
    assert config.endpoint == f"wss://{host}/api-ws/v1/realtime"
    assert config.model == probe.MODEL and config.sample_rate == 16000
    assert provider.model == "qwen3-asr-flash" and provider.parameters == original


@pytest.mark.parametrize(
    "base",
    [
        "https://proxy.example.invalid/v1",
        "https://dashscope.aliyuncs.com.evil.invalid/compatible-mode/v1",
        "https://workspace.cn-beijing.maas.aliyuncs.com.evil.invalid/compatible-mode/v1",
        "https://dashscope.aliyuncs.com:9443/compatible-mode/v1",
        "https://dashscope.aliyuncs.com/unverified-path",
        "https://trial.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    ],
)
def test_unapproved_origin_fails_before_key_or_network(tmp_path, monkeypatch, base):
    _, original = config_files(tmp_path, current_provider(base))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("origin guard must run first")

    monkeypatch.setattr(probe, "SecretStore", forbidden)
    monkeypatch.setattr(probe, "ObservedSession", forbidden)
    with pytest.raises(ProviderError) as caught:
        asyncio.run(probe.probe(tmp_path))
    assert caught.value.code == "configuration"
    assert original == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}


@pytest.mark.parametrize("version", [0, True, 99])
def test_schema_failure_never_migrates_or_writes(tmp_path, version):
    path = tmp_path / "config.json"
    original = json.dumps({"schema_version": version}).encode()
    path.write_bytes(original)
    with pytest.raises(ConfigError):
        probe.read_record(path, Settings)
    assert path.read_bytes() == original and len(list(tmp_path.iterdir())) == 1


def test_current_gateway_override_cannot_redirect_the_probe():
    provider = replace(
        current_provider(),
        parameters={
            "asr_protocol": "qwen_realtime",
            "realtime_url": "wss://other.example.invalid/ws",
        },
    )
    config = probe.official_config(provider)
    assert config.endpoint.startswith("wss://workspace.cn-beijing.maas.aliyuncs.com/")
    assert "other.example.invalid" not in config.url
    assert provider.parameters["realtime_url"] == "wss://other.example.invalid/ws"


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("empty", "protocol_finished_without_speech"),
        ("text", "protocol_finished_with_text"),
        ("early_empty", "failed"),
        ("empty_without_finish", "failed"),
        ("empty_without_commit", "failed"),
        ("authentication_after_finish", "failed"),
        ("timeout_after_finish", "failed"),
    ],
)
def test_only_normal_finish_can_classify_empty_as_protocol_success(
    monkeypatch, mode, expected
):
    instances = []

    class Session:
        def __init__(self, config, key, **options):
            assert config.model == probe.MODEL and key == "synthetic-key"
            assert options["timeout_seconds"] == 20
            self.created = self.updated = self.committed = self.finished = False
            self.commit_sent = self.finish_requested = False
            self.update_requested = self.update_sent = True
            self.event_diagnostic = {}
            self.frames_sent = 0
            self.closed = False
            instances.append(self)

        async def start(self):
            if mode == "early_empty":
                raise ProviderError("empty")
            self.created = self.updated = True

        async def feed(self, chunk):
            assert chunk == bytes(3200)
            self.frames_sent += 1

        async def finish(self):
            self.committed = mode != "empty_without_commit"
            self.commit_sent = self.finish_requested = True
            self.finished = mode != "empty_without_finish"
            if mode == "text":
                return Result("synthetic-private-returned-text", Usage(), 1)
            if mode.endswith("after_finish"):
                raise ProviderError(mode.removesuffix("_after_finish"))
            raise ProviderError("empty")

        async def aclose(self):
            self.closed = True

    async def immediate(_seconds):
        pass

    monkeypatch.setattr(probe, "ObservedSession", Session)
    monkeypatch.setattr(probe.asyncio, "sleep", immediate)
    result = asyncio.run(
        probe.exercise(probe.official_config(current_provider()), "synthetic-key")
    )
    assert result["status"] == expected
    assert len(instances) == 1 and instances[0].closed
    assert instances[0].frames_sent in {0, 10}
    assert "synthetic-key" not in json.dumps(result)
    assert "synthetic-private-returned-text" not in json.dumps(result)


def test_probe_only_reads_current_records_and_preserves_all_files(
    tmp_path, monkeypatch
):
    _, original = config_files(tmp_path)
    calls = []

    async def exercise(config, key, **options):
        assert options == {"handshake_only": False}
        calls.append((config, key))
        return {"status": "protocol_finished_without_speech"}

    monkeypatch.setattr(probe, "exercise", exercise)
    monkeypatch.setattr(
        probe,
        "SecretStore",
        lambda: SimpleNamespace(
            get=lambda ref: "synthetic-key" if ref == "synthetic-ref" else None
        ),
    )
    result = asyncio.run(probe.probe(tmp_path))
    assert result["config_unchanged"] is True and len(calls) == 1
    assert calls[0][0].model == probe.MODEL and calls[0][1] == "synthetic-key"
    assert original == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}


@pytest.mark.parametrize(
    "error,code",
    [
        (ProviderError("empty"), "empty"),
        (RuntimeError("synthetic-key private audio"), "probe_failed"),
    ],
)
def test_failure_output_has_no_freeform_key_or_content(
    error, code, monkeypatch, capsys
):
    async def failed(_root, **_options):
        raise error

    monkeypatch.setattr(probe, "probe", failed)
    monkeypatch.setattr(probe.logging, "disable", lambda _level: None)
    assert probe.main(["--live", "--config-root", "/unused-fixture-root"]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out) == {"status": "failed", "code": code}
    assert not output.err and "synthetic-key" not in output.out


def test_observer_does_not_mark_rejected_finish_as_received():
    async def execute():
        session = probe.ObservedSession(
            probe.official_config(current_provider()), "synthetic-key"
        )
        session._ready = asyncio.get_running_loop().create_future()
        session._ready.set_result(None)
        session._done = asyncio.get_running_loop().create_future()
        with pytest.raises(ProviderError):
            await session._event({"type": "session.finished", "event_id": "early"})
        assert not session.finished
        session._finish_sent = True
        with pytest.raises(ProviderError):
            await session._event({"type": "session.finished", "event_id": "no-ack"})
        assert not session.finished
        session._commit_acknowledged = True
        await session._event({"type": "session.finished", "event_id": "valid"})
        assert session.finished
        await session.aclose()

    asyncio.run(execute())


@pytest.mark.parametrize(
    ("payload", "missing", "null", "empty", "invalid"),
    [
        ({}, True, False, False, False),
        ({"item_id": None}, False, True, False, False),
        ({"item_id": ""}, False, False, True, True),
        ({"item_id": 42}, False, False, False, True),
        ({"item_id": "x" * 201}, False, False, False, True),
        ({"item_id": "private-item"}, False, False, False, False),
    ],
)
def test_observer_classifies_optional_item_ids_without_retaining_values(
    payload, missing, null, empty, invalid
):
    async def execute():
        session = probe.ObservedSession(
            probe.official_config(current_provider()), "synthetic-key"
        )
        session._ready = asyncio.get_running_loop().create_future()
        session._ready.set_result(None)
        session._commit_sent = True
        try:
            await session._event({"type": "input_audio_buffer.committed", **payload})
        except ProviderError:
            pass
        diagnostic = session.event_diagnostic
        assert diagnostic["event_item_id_missing"] is missing
        assert diagnostic["event_item_id_null"] is null
        assert diagnostic["event_item_id_empty"] is empty
        assert diagnostic["event_item_id_invalid"] is invalid
        assert "private-item" not in json.dumps(diagnostic)
        await session.aclose()

    asyncio.run(execute())


@pytest.mark.parametrize(
    "payload",
    [{}, {"content_index": 0}, {"content_index": None}, {"content_index": False}],
)
@pytest.mark.parametrize("transcript", [None, "", "  ", "private-result"])
def test_final_diagnostic_classifies_only_fixed_text_and_index_booleans(
    payload, transcript
):
    async def execute():
        session = probe.ObservedSession(
            probe.official_config(current_provider()), "synthetic-key"
        )
        session._ready = asyncio.get_running_loop().create_future()
        session._ready.set_result(None)
        session._commit_sent = True
        session._commit_acknowledged = True
        try:
            await session._event(
                {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "transcript": transcript,
                    **payload,
                }
            )
        except ProviderError:
            pass
        diagnostic = session.event_diagnostic
        assert diagnostic["transcript_string"] is isinstance(transcript, str)
        assert diagnostic["transcript_nonempty"] is (transcript == "private-result")
        missing = "content_index" not in payload
        valid = type(payload.get("content_index")) is int
        assert diagnostic["content_index_missing"] is missing
        assert diagnostic["content_index_int0"] is valid
        assert diagnostic["content_index_invalid"] is (not missing and not valid)
        assert "private-result" not in json.dumps(diagnostic)
        await session.aclose()

    asyncio.run(execute())


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    root = tmp_path_factory.mktemp("silence-wss")
    cert, key = root / "cert.pem", root / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert, key)
    return server, ssl.create_default_context(cafile=str(cert))


@pytest.mark.parametrize("handshake_only", [False, True])
def test_real_local_wss_accepts_exact_generated_silence_and_observed_finish(
    certificate, monkeypatch, handshake_only
):
    async def execute():
        state = SimpleNamespace(connections=0, pcm=[], errors=[])

        async def handler(socket):
            state.connections += 1
            count = 0

            async def send(kind, **values):
                nonlocal count
                count += 1
                await socket.send(
                    json.dumps({"event_id": str(count), "type": kind, **values})
                )

            try:
                assert socket.request.headers["Authorization"] == "Bearer synthetic-key"
                await send(
                    "session.created", session={"id": "s1", "model": probe.MODEL}
                )
                async for raw in socket:
                    item = json.loads(raw)
                    if item["type"] == "session.update":
                        await send(
                            "session.updated",
                            session={
                                "id": "s1",
                                "model": probe.MODEL,
                                **item["session"],
                            },
                        )
                    elif item["type"] == "input_audio_buffer.append":
                        chunk = base64.b64decode(item["audio"])
                        assert chunk == bytes(3200)
                        state.pcm.append(chunk)
                    elif item["type"] == "input_audio_buffer.commit":
                        await send("input_audio_buffer.committed", item_id="i1")
                    elif item["type"] == "session.finish":
                        await send("session.finished")
            except ConnectionClosed:
                pass
            except Exception as error:
                state.errors.append(type(error).__name__)

        constructor = probe.ObservedSession

        def trusted(*args, **options):
            return constructor(*args, **options, tls_context=certificate[1])

        monkeypatch.setattr(probe, "ObservedSession", trusted)
        async with serve(handler, "127.0.0.1", 0, ssl=certificate[0]) as server:
            port = server.sockets[0].getsockname()[1]
            # Internal adapter exercise only; CLI origin guards never accept this URL.
            config = RealtimeConfig(f"wss://127.0.0.1:{port}/realtime", probe.MODEL)
            result = await probe.exercise(
                config, "synthetic-key", handshake_only=handshake_only
            )
        assert result["status"] == (
            "handshake_ready" if handshake_only else "protocol_finished_without_speech"
        )
        assert result["session_created"] and result["session_updated"]
        assert result["session_finished"] is not handshake_only
        assert state.connections == 1 and state.errors == []
        assert result["frames_sent"] == (0 if handshake_only else 10)
        assert result["commit_acknowledged"] is not handshake_only
        assert result["commit_sent"] is not handshake_only
        assert result["finish_requested"] is not handshake_only
        assert len(state.pcm) == (0 if handshake_only else 10)
        assert b"".join(state.pcm) == bytes(0 if handshake_only else 32000)

    asyncio.run(execute())


@pytest.mark.parametrize(
    "kind", ["input_audio_buffer.append", "input_audio_buffer.commit", "session.finish"]
)
def test_handshake_observer_hard_refuses_audio_commit_and_finish(kind):
    async def execute():
        session = probe.ObservedSession(
            probe.official_config(current_provider()),
            "synthetic-key",
            handshake_only=True,
        )
        with pytest.raises(ProviderError) as caught:
            await session._send(kind)
        assert caught.value.code == "configuration" and session.frames_sent == 0
        assert not session.commit_sent and not session.finish_requested
        await session.aclose()

    asyncio.run(execute())


def test_rejected_event_diagnostic_is_fixed_booleans_without_original_values():
    async def execute():
        session = probe.ObservedSession(
            probe.official_config(current_provider()),
            "synthetic-key",
            handshake_only=True,
        )
        session._session_id = "synthetic-private-session"
        session._event_ids.add("synthetic-private-event")
        session._ready = asyncio.get_running_loop().create_future()
        event = {
            "type": "session.updated",
            "event_id": "synthetic-private-event",
            "session": {
                "id": "different-private-session",
                "model": "different-private-model",
                "input_audio_format": "secret-format",
                "sample_rate": "private-rate",
                "turn_detection": {"private-field": "private-value"},
            },
        }
        with pytest.raises(ProviderError):
            await session._event(event)
        metadata = session.event_diagnostic
        assert metadata["event_kind"] == "session.updated"
        assert all(
            type(value) is bool
            for key, value in metadata.items()
            if key != "event_kind"
        )
        assert metadata["event_id_duplicate"] and not metadata["model_match"]
        assert not metadata["session_id_match"] and metadata["format_other"]
        assert not metadata["sample_rate_integer"] and metadata["turn_detection_object"]
        encoded = json.dumps(metadata)
        assert (
            "private" not in encoded
            and "secret-format" not in encoded
            and "synthetic-key" not in encoded
        )
        assert not session.updated
        await session.aclose()

    asyncio.run(execute())


@pytest.mark.parametrize("known", [False, True])
@pytest.mark.parametrize("item_shape", ["valid", "missing", "wrong_type", "long_id"])
def test_item_diagnostic_is_fixed_booleans_before_production_validation(
    known, item_shape
):
    async def execute():
        session = probe.ObservedSession(
            probe.official_config(current_provider()), "synthetic-key"
        )
        session._ready = asyncio.get_running_loop().create_future()
        session._ready.set_result(None)
        session._item_id = "synthetic-private-item" if known else None
        session._provisional_item_id = "synthetic-private-item" if not known else None
        session._commit_sent = session._finishing = known
        event = {
            "type": "conversation.item.created",
            "item_id": "synthetic-private-item",
        }
        if item_shape != "missing":
            event["item"] = (
                "private-non-object"
                if item_shape == "wrong_type"
                else {
                    "id": "private-" * 30
                    if item_shape == "long_id"
                    else "synthetic-private-item",
                    "role": "user",
                    "type": "message",
                    "content": [{"private": "private-body-never-retained"}],
                }
            )
        try:
            await session._event(event)
        except ProviderError:
            pass  # The diagnostic records metadata even when validation rejects it.
        metadata = session.event_diagnostic
        is_object = item_shape in {"valid", "long_id"}
        assert metadata["item_present"] is (item_shape != "missing")
        assert metadata["item_object"] is is_object
        assert metadata["item_id_nonempty"] is is_object
        assert metadata["item_id_length_valid"] is (item_shape == "valid")
        assert metadata["item_id_known"] is known
        assert metadata["item_id_match"] is (known and item_shape == "valid")
        assert metadata["item_role_user"] is is_object
        assert metadata["item_type_message"] is is_object
        assert metadata["commit_sent"] is known
        assert metadata["finishing"] is known
        assert metadata["event_item_id_valid"]
        assert metadata["event_item_id_matches_committed"] is known
        assert metadata["event_item_id_matches_provisional"] is not known
        assert all(
            type(value) is bool
            for key, value in metadata.items()
            if key != "event_kind"
        )
        assert "private" not in json.dumps(metadata)
        assert "synthetic-key" not in json.dumps(metadata)
        await session.aclose()

    asyncio.run(execute())
