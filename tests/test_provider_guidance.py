"""Offline onboarding and actual Qt widgets, with synthetic configuration only."""

from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from inkecho.config import ConfigStore, Provider
from inkecho.provider_catalog import PRESETS
from inkecho.provider_guidance import PLATFORMS, PRESET_PLATFORMS, setup_guidance
from inkecho.ui.providers import ProviderPage


@pytest.mark.parametrize("preset", PRESETS, ids=lambda p: p.id)
def test_catalog_guides_cover_presets_without_inventing_custom_links(preset):
    summary, details = setup_guidance(
        preset.id,
        preset.base_url,
        preset.credential_fields,
        role=preset.role,
        protocol=preset.protocol,
        adapter=preset.adapter,
    )
    assert summary and "保存配置" in details
    assert details.count("<li>") == 3
    if preset.id.startswith("custom-"):
        assert "href=" not in details
    else:
        assert preset.id in PRESET_PLATFORMS
        platform = PLATFORMS[PRESET_PLATFORMS[preset.id]]
        assert platform.name in summary
        for url in (platform.console, platform.docs):
            if url:
                parsed = urlsplit(url)
                assert parsed.scheme == "https"
                assert parsed.hostname and not parsed.username
                assert not parsed.fragment


@pytest.mark.parametrize(
    "url",
    [
        "https://gateway.invalid/v1",
        "https://dashscope.aliyuncs.com.evil.invalid/compatible-mode/v1",
        "https://user:secret@dashscope.aliyuncs.com/compatible-mode/v1",
        "https://dashscope.aliyuncs.com/compatible-mode/v1?api_key=private",
        '<a href="https://evil.invalid">private</a>',
    ],
)
def test_edited_endpoint_removes_official_links_and_never_echoes_url(url):
    summary, details = setup_guidance(
        "qwen",
        url,
        ("api_key",),
        role="transcription",
        adapter="qwen",
    )
    assert "自定义服务" in summary
    assert "href=" not in details
    assert "private" not in details
    assert "aliyun.com" not in details


def test_unknown_saved_model_uses_only_matching_endpoint_protocol_and_adapter():
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    _, details = setup_guidance(
        None,
        url,
        ("api_key",),
        role="transcription",
        adapter="qwen",
        protocol="qwen_realtime",
    )
    assert "bailian.console.aliyun.com" in details
    for adapter, protocol in [("multipart", "http"), ("qwen", "xfyun_iat")]:
        _, details = setup_guidance(
            None,
            url,
            ("api_key",),
            role="transcription",
            adapter=adapter,
            protocol=protocol,
        )
        assert "href=" not in details


def test_widget_guide_updates_without_cloud_credentials_or_writes(tmp_path, qt_app):
    store = ConfigStore(tmp_path / "config")
    store.initialize()
    before = {p.name: p.read_bytes() for p in store.root.glob("*.json")}
    page = ProviderPage(SimpleNamespace(store=store), "transcription")
    try:
        assert "先选择服务平台" in page.guide_summary.text()
        assert page.guide_details.isHidden()
        page.guide_toggle.click()
        assert not page.guide_details.isHidden()
        page.apply_preset(page.preset.findData("xfyun"))
        assert "讯飞" in page.guide_summary.text()
        assert "APISecret" in (page.guide_details.text() + page.guide_links.text())
        assert "console.xfyun.cn" in (
            page.guide_details.text() + page.guide_links.text()
        )
        page.apply_preset(page.preset.findData("qwen"))
        assert "阿里云百炼" in page.guide_summary.text()
        assert "北京地域" in (page.guide_details.text() + page.guide_links.text())
        page.url.setText("https://custom.invalid/v1")
        assert "自定义服务" in page.guide_summary.text()
        assert "href=" not in (page.guide_details.text() + page.guide_links.text())
        page.new()
        assert "先选择服务平台" in page.guide_summary.text()
        assert before == {p.name: p.read_bytes() for p in store.root.glob("*.json")}
    finally:
        page.close()


def test_saved_unknown_model_retains_official_guidance(tmp_path, qt_app):
    store = ConfigStore(tmp_path / "config")
    store.initialize()
    store.save_provider(
        Provider(
            "synthetic",
            "unknown",
            "polishing",
            "openai",
            "https://api.deepseek.com/v1",
            "future-model",
            "provider/synthetic",
            {},
        )
    )
    page = ProviderPage(SimpleNamespace(store=store), "polishing")
    try:
        page.refresh("synthetic")
        assert "DeepSeek" in page.guide_summary.text()
        assert "platform.deepseek.com" in (
            page.guide_details.text() + page.guide_links.text()
        )
    finally:
        page.close()


@pytest.mark.parametrize("protocol", [None, "invalid"])
def test_empty_guidance_does_not_claim_realtime(protocol):
    _, details = setup_guidance(
        None,
        "",
        ("api_key",),
        role="transcription",
        protocol=protocol,
    )
    assert "当前为实时识别" not in details
    assert "16 kHz" not in details
