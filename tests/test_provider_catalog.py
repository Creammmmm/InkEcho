"""Protocol classification and secret bundles, without discovery or real keys."""

import pytest

from inkecho.provider_catalog import PRESETS, asr_capability
from inkecho.provider_credentials import decode_credentials, encode_credentials
from inkecho.security import CredentialError


@pytest.mark.parametrize(
    "model",
    [
        "deepseek-chat",
        "openai/gpt-4o",
        "deepseek/deepseek-chat",
        "anthropic/claude-sonnet-4",
        "gpt-4o",
        "qwen-plus",
        "text-embedding-3-small",
        "tts-asr-voice",
        "flux-image",
        "gemini-2.5-flash",
        "rerank-v3",
    ],
)
def test_non_asr_is_rejected_even_if_name_mentions_audio(model):
    assert asr_capability(model, "multipart", {}) == "unsupported"


@pytest.mark.parametrize(
    "adapter,model",
    [
        ("multipart", "whisper-1"),
        ("multipart", "gpt-4o-mini-transcribe-2025-12-15"),
        ("multipart", "FunAudioLLM/SenseVoiceSmall"),
        ("multipart", "TeleAI/TeleSpeechASR"),
        ("elevenlabs", "scribe_v2"),
        ("mimo-asr", "mimo-v2.5-asr"),
        ("openrouter-asr", "openai/whisper-large-v3-turbo"),
        ("qwen", "qwen3-asr-flash"),
    ],
)
def test_known_protocol_candidate_is_not_a_cloud_verification(adapter, model):
    assert asr_capability(model, adapter, {}) == "supported"
    assert asr_capability(model, "unimplemented", {}) != "supported"


def test_realtime_protocol_and_unknown_manual_model():
    model = "qwen3-asr-flash-realtime"
    assert asr_capability(model, "qwen", {}) == "unsupported"
    assert (
        asr_capability(model, "qwen", {"asr_protocol": "qwen_realtime"}) == "supported"
    )
    assert asr_capability("future-vendor-audio-v7", "multipart", {}) == "unknown"
    assert len({p.id for p in PRESETS}) == len(PRESETS)


def test_bundle_is_exact_and_legacy_api_key_remains_compatible():
    fields = ("app_id", "api_key", "api_secret")
    values = dict.fromkeys(fields, "synthetic-only")
    assert decode_credentials(encode_credentials(values, fields), fields) == values
    assert decode_credentials("legacy-fixture", ("api_key",)) == {
        "api_key": "legacy-fixture"
    }
    for bad in [
        {},
        {**values, "extra": "sensitive"},
        {**values, "api_key": "secret\nheader"},
    ]:
        with pytest.raises(CredentialError) as caught:
            encode_credentials(bad, fields)
        assert "sensitive" not in str(caught.value) and "secret" not in str(
            caught.value
        )
    with pytest.raises(CredentialError):
        decode_credentials('{"api_key":"only-one"}', fields)
