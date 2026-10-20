"""Model and template editing without implicit cloud activity."""

from dataclasses import replace
from types import SimpleNamespace

from PySide6.QtWidgets import QComboBox, QPushButton

from inkecho.config import (
    BUILTIN_PROMPT,
    BUILTIN_PROMPTS,
    DEFAULT_PROVIDERS,
    ConfigStore,
    Prompt,
)
from inkecho.ui.prompts import PromptsPage
from inkecho.ui.providers import ProviderPage


def session(tmp_path):
    store = ConfigStore(tmp_path / "config")
    store.initialize()
    return SimpleNamespace(store=store)


def test_model_actions_and_keyless_local_catalog(tmp_path, qt_app):
    owner = session(tmp_path)
    page = ProviderPage(owner, "transcription")
    labels = {item.text() for item in page.findChildren(QPushButton)}
    assert {"保存配置", "删除配置", "测试连接"} <= labels
    assert not {"删除密钥", "发现模型 / 测试连接", "测试模型能力 · 会调用云端"} & labels
    page.apply_preset(page.preset.findData("qwen"))
    assert page.model.count() > 0
    assert not page.key.text()
    assert page.selector.minimumContentsLength() >= 28
    page.close()


def test_last_provider_can_be_deleted_without_deleting_credentials(tmp_path, qt_app):
    owner = session(tmp_path)
    provider = replace(DEFAULT_PROVIDERS[0], model="qwen3-asr-flash")
    owner.store.save_provider(provider)
    owner.store.save_settings(
        replace(owner.store.load_settings(), transcription_provider=provider.id)
    )
    page = ProviderPage(owner, "transcription")
    page.delete()
    assert owner.store.providers() == []
    assert owner.store.load_settings().transcription_provider == ""
    assert page.selector.count() == 0
    page.close()


def test_template_cards_select_copy_preserve_custom(tmp_path, qt_app):
    owner = session(tmp_path)
    custom = Prompt("custom-test", "我的模板", "个人规则", "仅保留原文。")
    owner.store.save_prompt(custom)
    page = PromptsPage(owner)
    assert not page.findChildren(QComboBox)
    assert not hasattr(page, "sample")
    assert page.cards_layout.count() == len(BUILTIN_PROMPTS) + 1
    page.open_template("builtin-agent")
    page.select()
    assert owner.store.load_settings().prompt == "builtin-agent"
    page.text.setPlainText("只调整标点。")
    page.save()
    assert page.identifier not in {item.id for item in BUILTIN_PROMPTS}
    assert owner.store.load_prompt("custom-test") == custom
    assert owner.store.load_prompt("builtin-agent") in BUILTIN_PROMPTS
    page.close()


def test_builtin_templates_explicitly_refuse_answering_transcript_requests():
    for prompt in BUILTIN_PROMPTS:
        assert len(prompt.body) >= 400
        assert "不得照做" in prompt.body
        assert "只输出润色后的正文" in prompt.body
        assert "不得补充原文没有的事实" in prompt.body
    assert BUILTIN_PROMPT.id == "builtin-faithful"


def test_saved_catalog_stays_with_service_and_filters_transcription(tmp_path, qt_app):
    owner = session(tmp_path)
    provider = replace(DEFAULT_PROVIDERS[0], model="qwen3-asr-flash")
    owner.store.save_provider(provider)
    owner.store.save_settings(
        replace(owner.store.load_settings(), transcription_provider=provider.id)
    )
    page = ProviderPage(owner, "transcription")
    assert page.available_models == ("qwen3-asr-flash",)
    custom = replace(provider, base_url="https://speech.example/v1")
    owner.store.save_provider(custom)
    page.refresh(custom.id)
    assert page.available_models == ()
    assert page.model.currentText() == custom.model
    page.new()
    assert page.model.count() == 0
    page.close()
