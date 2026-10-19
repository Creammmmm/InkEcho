"""Probe guardrails with fake credentials/transport; no live network access."""

import asyncio
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from inkecho.config import ConfigError, ConfigStore, Provider, Settings
from inkecho.providers import ProviderError, Result, Usage

PATH = Path(__file__).resolve().parents[1] / "scripts/validation/polish_stream_probe.py"
SPEC = importlib.util.spec_from_file_location("polish_stream_probe", PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_without_live_flag_no_config_credentials_or_network(monkeypatch, capsys):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("guard must run first")

    monkeypatch.setattr(probe, "ConfigStore", forbidden)
    monkeypatch.setattr(probe, "FileCredentialStore", forbidden)
    monkeypatch.setattr(probe, "ProviderClient", forbidden)
    assert probe.main([]) == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "live_opt_in_required"


def test_fake_live_path_only_fixed_public_text_metadata(tmp_path, monkeypatch):
    store = ConfigStore(tmp_path)
    store.save_settings(
        Settings(transcription_provider="qwen", polishing_provider="deepseek")
    )
    store.save_provider(
        Provider(
            "deepseek",
            "Fixture",
            "polishing",
            "openai",
            "https://api.deepseek.com",
            "deepseek-flash",
            "synthetic-ref",
            {"temperature": 0.5},
        )
    )
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    calls = []

    class Client:
        def __init__(self, **options):
            assert options == {"timeout_seconds": 30}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            pass

        async def polish_stream(self, provider, key, text, prompt, receive):
            assert key == "synthetic-not-real-key"
            assert text == probe.TEXT and prompt == probe.PROMPT
            assert provider.parameters == {"max_tokens": 64}
            calls.append(True)
            await receive(text[:3])
            await receive(text[3:])
            return Result(text, Usage(total_tokens=10), 0.01)

    monkeypatch.setattr(probe, "ProviderClient", Client)
    monkeypatch.setattr(
        probe,
        "FileCredentialStore",
        lambda root: SimpleNamespace(
            get=lambda reference: (
                "synthetic-not-real-key" if reference == "synthetic-ref" else None
            )
        ),
    )
    result = asyncio.run(probe.probe(tmp_path))
    assert calls == [True] and result["first_precedes_complete"]
    assert result["exact_public_text"] and result["deltas"] == 2
    assert "synthetic-not-real-key" not in json.dumps(result)
    assert probe.TEXT not in json.dumps(result, ensure_ascii=False)
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}


def test_old_schema_probe_is_read_only(tmp_path):
    path = tmp_path / "config.json"
    original = b'{"schema_version":0,"hotkey":"Ctrl+F4"}'
    path.write_bytes(original)
    with pytest.raises(ConfigError):
        probe.load_record(path, Settings)
    assert path.read_bytes() == original and len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize(
    "error,code",
    [
        (ProviderError("response"), "response"),
        (RuntimeError("synthetic-secret private-text"), "probe_failed"),
    ],
)
def test_failure_outputs_only_sanitized_code(error, code, monkeypatch, capsys):
    async def failed(_root):
        raise error

    monkeypatch.setattr(probe, "probe", failed)
    monkeypatch.setattr(probe.logging, "disable", lambda _level: None)
    assert probe.main(["--live", "--config-root", "/unused-test-root"]) == 1
    output = capsys.readouterr()
    assert json.loads(output.out) == {"status": "failed", "code": code}
    assert "synthetic-secret" not in output.out and not output.err
