"""Actual widget filtering used by packaged UI validation, without cloud access."""

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from inkecho.config import ConfigStore
from inkecho.ui.providers import ProviderPage


def test_packaged_widget_gate_checks_filtering_and_private_save(
    tmp_path, qt_app, monkeypatch
):
    root = Path(__file__).resolve().parents[1] / "scripts/validation"
    monkeypatch.syspath_prepend(str(root))
    spec = importlib.util.spec_from_file_location(
        "ui_protocol_gate", root / "ui_protocol_acceptance.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    store = ConfigStore(tmp_path / "config")
    store.initialize()
    calls = []

    class Client:
        async def models(self, _provider, key):
            assert key == "synthetic"
            calls.append("discover")
            return [
                "qwen3-asr-flash",
                "qwen3-asr-flash-realtime",
                "qwen-plus",
                "qwen3-tts-flash",
            ]

    async def key(_ref):
        return "synthetic"

    async def no_write(*_args):
        raise AssertionError("credential_write_forbidden")

    page = ProviderPage(
        SimpleNamespace(
            store=store,
            key=key,
            save_key=no_write,
            provider_client=lambda _role: Client(),
        ),
        "transcription",
    )
    try:
        checks = asyncio.run(module.exercise(page, store))
        assert all(checks.values()), checks
        assert calls == ["discover"]
    finally:
        page.close()
