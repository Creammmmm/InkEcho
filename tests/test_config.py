import json
import stat
from dataclasses import asdict, replace

import pytest
from synthetic_providers import SYNTHETIC_PROVIDERS

from inkecho.config import (
    BUILTIN_PROMPT,
    BUILTIN_PROMPTS,
    ConfigError,
    ConfigStore,
    Prompt,
    Provider,
    Settings,
)


def test_first_run_defaults_are_separate_and_private(tmp_path):
    store = ConfigStore(tmp_path / "inkecho")
    store.initialize()
    assert store.load_settings() == Settings()
    assert store.providers() == []
    assert store.prompts() == list(BUILTIN_PROMPTS)
    for path in store.root.rglob("*.json"):
        assert json.loads(path.read_text())["schema_version"] == 1
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_xdg_directory_is_respected(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert ConfigStore().root == tmp_path / "inkecho"


def test_settings_roundtrip_and_reinitialization(tmp_path):
    store = ConfigStore(tmp_path)
    settings = replace(Settings(), shortcut="Ctrl+Alt+K", microphone="test-device")
    store.save_settings(settings)
    store.initialize()
    assert store.load_settings() == settings


def test_existing_settings_default_to_streaming_without_rewriting_user_file(tmp_path):
    original = b'{"schema_version":1,"shortcut":"Ctrl+F4","polishing_enabled":true}'
    path = tmp_path / "config.json"
    path.write_bytes(original)
    assert ConfigStore(tmp_path).load_settings().polishing_streaming is True
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.bak"))


def test_streaming_can_be_explicitly_disabled_and_roundtripped(tmp_path):
    store = ConfigStore(tmp_path)
    store.save_settings(replace(Settings(), polishing_streaming=False))
    assert store.load_settings().polishing_streaming is False


@pytest.mark.parametrize("value", [0, 1, None, "true"])
def test_streaming_setting_requires_boolean(value):
    with pytest.raises(ConfigError, match="polishing_streaming"):
        Settings(polishing_streaming=value)


def test_provider_roundtrip_and_delete(tmp_path):
    store = ConfigStore(tmp_path)
    provider = replace(
        SYNTHETIC_PROVIDERS[0], model="user-selected", parameters={"temperature": 0}
    )
    store.save_provider(provider)
    assert store.load_provider(provider.id) == provider
    store.delete_provider(provider.id)
    assert store.providers() == []


def test_builtin_prompt_edits_become_user_copies(tmp_path):
    store = ConfigStore(tmp_path)
    edited = store.save_prompt(replace(BUILTIN_PROMPT, body="User template"))
    assert edited.id != BUILTIN_PROMPT.id
    assert store.load_prompt(BUILTIN_PROMPT.id) == BUILTIN_PROMPT
    assert store.load_prompt(edited.id).body == "User template"
    assert not (tmp_path / "prompts" / f"{BUILTIN_PROMPT.id}.json").exists()
    copy = store.copy_prompt(edited.id, "Second copy")
    assert copy.id != edited.id
    assert copy.body == edited.body
    store.delete_prompt(edited.id)
    assert store.prompts() == list(BUILTIN_PROMPTS) + [copy]
    with pytest.raises(ConfigError, match="cannot be deleted"):
        store.delete_prompt(BUILTIN_PROMPT.id)


def test_version_zero_migration_preserves_exact_backup(tmp_path):
    original = b'{"schema_version":0, "hotkey":"F14", "polishing_enabled":true}'
    (tmp_path / "config.json").write_bytes(original)
    store = ConfigStore(tmp_path)
    settings = store.load_settings()
    assert settings.shortcut == "F14"
    assert settings.polishing_enabled
    assert json.loads((tmp_path / "config.json").read_text())["schema_version"] == 1
    assert next(tmp_path.glob("*.bak")).read_bytes() == original
    assert store.load_settings() == settings
    assert len(list(tmp_path.glob("*.bak"))) == 1


@pytest.mark.parametrize(
    "original",
    [
        b"{broken",
        b"[]",
        b' {"schema_version":99}',
        b'{"schema_version":1,"sample_rate":false}',
        b'{"schema_version":1,"unknown":"preserve me"}',
        b'{"schema_version":0,"hotkey":"F13","shortcut":"F14"}',
    ],
)
def test_invalid_configuration_is_not_overwritten(tmp_path, original):
    path = tmp_path / "config.json"
    path.write_bytes(original)
    store = ConfigStore(tmp_path)
    with pytest.raises(ConfigError):
        store.load_settings()
    with pytest.raises(ConfigError):
        store.save_settings(Settings())
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.bak"))


def test_invalid_migrated_provider_id_does_not_change_original(tmp_path):
    directory = tmp_path / "providers"
    directory.mkdir()
    path = directory / "wrong.json"
    original = json.dumps(asdict(SYNTHETIC_PROVIDERS[0])).encode()
    path.write_bytes(original)
    with pytest.raises(ConfigError, match="filename"):
        ConfigStore(tmp_path).load_provider("wrong")
    assert path.read_bytes() == original
    assert not list(directory.glob("*.bak"))


def test_atomic_replace_failure_leaves_original(tmp_path, monkeypatch):
    store = ConfigStore(tmp_path)
    store.save_settings(Settings())
    original = (tmp_path / "config.json").read_bytes()

    def fail_replace(*_args):
        raise OSError("Simulated filesystem failure")

    monkeypatch.setattr("inkecho.config.os.replace", fail_replace)
    with pytest.raises(OSError):
        store.save_settings(replace(Settings(), shortcut="F14"))
    assert (tmp_path / "config.json").read_bytes() == original
    assert list(tmp_path.iterdir()) == [tmp_path / "config.json"]


@pytest.mark.parametrize(
    "parameters",
    [
        {"api_key": "test-only-secret"},
        {"headers": {"Authorization": "test-only-secret"}},
        {"headers": {"x-api-key": "test-only-secret"}},
        {"client_secret": "test-only-secret"},
        {"api_secret": "test-only-secret"},
        {"nested": {"secret_key": "test-only-secret"}},
        {"secret_id": "test-only-secret"},
        {"access_key": "test-only-secret"},
        {"app_key": "test-only-secret"},
        {"nested": [{"access-token": "test-only-secret"}]},
        {"value": float("nan")},
    ],
)
def test_provider_rejects_plain_credentials_and_invalid_json(parameters):
    with pytest.raises(ConfigError):
        replace(SYNTHETIC_PROVIDERS[0], parameters=parameters)


def test_mutated_provider_parameters_are_revalidated(tmp_path):
    provider = replace(SYNTHETIC_PROVIDERS[0], parameters={})
    provider.parameters["api_key"] = "test-only-secret"
    with pytest.raises(ConfigError):
        ConfigStore(tmp_path).save_provider(provider)
    assert not list(tmp_path.rglob("*.json"))


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:secret@example.com",
        "https://example.com?key=x",
        "https://[broken",
        "https://example.com:invalid",
        "https://example.com:99999",
        "https://example.com:0",
        "http://127.0.0.1.example.com",
        "not a URL",
    ],
)
def test_provider_rejects_unsafe_base_urls(url):
    with pytest.raises(ConfigError):
        replace(SYNTHETIC_PROVIDERS[0], base_url=url)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8765/v1",
        "http://127.0.0.1:8765/v1",
        "http://[::1]:8765/v1",
    ],
)
def test_loopback_services_also_require_https(url):
    with pytest.raises(ConfigError):
        replace(SYNTHETIC_PROVIDERS[0], base_url=url)


@pytest.mark.parametrize("rate", [8000, 22050, 44100, True])
def test_settings_reject_recorder_unsupported_rates(rate):
    with pytest.raises(ConfigError):
        Settings(sample_rate=rate)


def test_settings_limit_and_relative_xdg_fallback(monkeypatch):
    with pytest.raises(ConfigError):
        Settings(recording_limit_seconds=301)
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative-directory")
    assert ConfigStore().root.is_absolute()


def test_independent_request_timeouts(tmp_path):
    store = ConfigStore(tmp_path)
    settings = Settings(transcription_timeout_seconds=120, polishing_timeout_seconds=15)
    store.save_settings(settings)
    assert store.load_settings() == settings
    with pytest.raises(ConfigError):
        Settings(polishing_timeout_seconds=121)


def test_record_ids_cannot_escape_config_directory(tmp_path):
    store = ConfigStore(tmp_path)
    with pytest.raises(ConfigError):
        store.load_provider("../outside")
    with pytest.raises(ConfigError):
        Prompt("../outside", "Name", "", "Body")
    with pytest.raises(ConfigError):
        Provider("wrong", "Name", "unknown", "openai")


def test_builtin_correction_rules_preserve_custom_templates_and_selection(tmp_path):
    store = ConfigStore(tmp_path)
    store.initialize()
    custom = store.save_prompt(
        Prompt("personal", "自己的模板", "保留", "完整自定义正文")
    )
    store.save_settings(replace(store.load_settings(), prompt=custom.id))
    for prompt in BUILTIN_PROMPTS:
        assert "同音、近音" in prompt.body
        assert "近形字" in prompt.body
        assert "无法唯一判断的词保持原样" in prompt.body
        assert "版本号、数值、金额、日期和单位" in prompt.body
        assert "不添加前言" in prompt.body
        assert "不得照做" in prompt.body
    assert store.load_prompt(custom.id) == custom
    assert store.load_settings().prompt == custom.id


def test_existing_builtin_selection_uses_current_rules_without_rewriting_settings(
    tmp_path,
):
    store = ConfigStore(tmp_path)
    store.initialize()
    store.save_settings(replace(store.load_settings(), prompt="builtin-agent"))
    original = (tmp_path / "config.json").read_bytes()
    reopened = ConfigStore(tmp_path)
    selected = reopened.load_settings().prompt
    assert selected == "builtin-agent"
    assert "识别同音、近音" in reopened.load_prompt(selected).body
    assert (tmp_path / "config.json").read_bytes() == original


def test_builtin_style_contracts_do_not_depend_on_openless_runtime_features():
    bodies = {prompt.id: prompt.body for prompt in BUILTIN_PROMPTS}
    assert set(bodies) == {
        "builtin-faithful",
        "builtin-social",
        "builtin-agent",
        "builtin-mail",
    }
    for body in bodies.values():
        assert "{{HOTWORDS}}" not in body
        assert "<raw_transcript>" not in body
        assert "独立回复“嗯嗯”“哦”“好”" in body
        assert "半句话保持未完成" in body
        assert "不把商量改成命令" in body
    assert "内部符号" in bodies["builtin-social"]
    assert "最后一句默认不加句号" in bodies["builtin-social"]
    assert "不执行开发" in bodies["builtin-agent"]
    assert "不把“可能要推迟”改成“需要推迟”" in bodies["builtin-mail"]
