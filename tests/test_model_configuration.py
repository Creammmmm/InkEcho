"""Fresh model onboarding keeps explicit user choices and legacy records."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest
from synthetic_providers import SYNTHETIC_PROVIDERS

from inkecho.config import BUILTIN_PROMPTS, ConfigError, ConfigStore, Settings
from inkecho.realtime import PROTOCOL
from inkecho.ui.providers import ProviderPage


def test_empty_first_run_and_legacy_records_remain_distinct(tmp_path):
    store = ConfigStore(tmp_path)
    store.initialize()
    assert store.providers() == []
    assert store.load_settings().transcription_provider == ""
    assert store.load_settings().polishing_provider == ""
    old = replace(Settings(), transcription_provider="qwen", overlay_style="waveform")
    store.save_settings(old)
    store.save_provider(SYNTHETIC_PROVIDERS[0])
    store.initialize()
    assert store.load_settings() == old
    assert store.providers() == [SYNTHETIC_PROVIDERS[0]]


def test_builtin_styles_are_read_only_and_copyable(tmp_path):
    store = ConfigStore(tmp_path)
    assert len(BUILTIN_PROMPTS) >= 4
    for template in BUILTIN_PROMPTS:
        assert store.load_prompt(template.id) == template
        with pytest.raises(ConfigError):
            store.delete_prompt(template.id)
        saved = store.save_prompt(replace(template, body="User edited content"))
        assert saved.id != template.id
        assert store.load_prompt(template.id) == template
        assert store.load_prompt(saved.id).body == "User edited content"


def test_explicit_platform_name_and_supported_protocols(tmp_path, qt_app):
    store = ConfigStore(tmp_path)
    store.initialize()
    page = ProviderPage(SimpleNamespace(store=store), "transcription")
    try:
        assert page.preset.currentIndex() == -1
        assert page.name.text() == page.url.text() == ""
        assert page.parameters.isHidden()
        assert page.realtime_url.isHidden()
        assert not page.protocol.isEnabled()
        assert page.protocol.currentIndex() == -1
        assert "请选择服务平台" in page.model_hint.text()
        page.apply_preset(page.preset.findData("qwen"))
        assert page.name.text() == ""
        assert {page.protocol.itemData(i) for i in range(page.protocol.count())} == {
            "http",
            PROTOCOL,
        }
        page.apply_preset(page.preset.findData("xfyun"))
        assert [page.protocol.itemData(i) for i in range(page.protocol.count())] == [
            "xfyun_iat"
        ]
        with pytest.raises(ConfigError):
            asyncio.run(page.save())
        assert store.providers() == []
    finally:
        page.close()


def test_new_save_requires_credentials_and_retains_timeout_on_existing_save(
    tmp_path, qt_app
):
    store = ConfigStore(tmp_path)
    store.initialize()
    page = ProviderPage(SimpleNamespace(store=store), "transcription")
    try:
        page.apply_preset(page.preset.findData("qwen"))
        page.name.setText("My speech model")
        with pytest.raises(ConfigError, match="完整凭据"):
            asyncio.run(page.save())
        assert store.providers() == []
        legacy = replace(
            SYNTHETIC_PROVIDERS[0],
            model="qwen3-asr-flash",
            parameters={"temperature": 0},
        )
        store.save_provider(legacy)
        page.refresh(legacy.id)
        assert page.parameters.isHidden()
        store.save_settings(
            replace(store.load_settings(), transcription_timeout_seconds=75)
        )
        asyncio.run(page.save())
        assert store.load_settings().transcription_timeout_seconds == 75
        assert store.load_provider(legacy.id).parameters == {"temperature": 0}
    finally:
        page.close()
