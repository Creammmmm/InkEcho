"""Independent protocol catalog; a catalog entry is never cloud verification."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    role: str
    adapter: str
    base_url: str
    models: tuple[str, ...] = ()
    credential_fields: tuple[str, ...] = ("api_key",)


PRESETS = (
    Preset(
        "qwen",
        "阿里云百炼 · HTTP / Qwen 实时",
        "transcription",
        "qwen",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ("qwen3-asr-flash", "qwen3-asr-flash-realtime"),
    ),
    Preset(
        "openai-asr",
        "OpenAI · 录音转写",
        "transcription",
        "multipart",
        "https://api.openai.com/v1",
        ("whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"),
    ),
    Preset(
        "groq",
        "Groq · 录音转写",
        "transcription",
        "multipart",
        "https://api.groq.com/openai/v1",
        ("whisper-large-v3-turbo", "whisper-large-v3"),
    ),
    Preset(
        "siliconflow",
        "硅基流动 · 录音转写",
        "transcription",
        "multipart",
        "https://api.siliconflow.cn/v1",
        ("FunAudioLLM/SenseVoiceSmall",),
    ),
    Preset(
        "openrouter-asr",
        "OpenRouter · 录音转写",
        "transcription",
        "openrouter-asr",
        "https://openrouter.ai/api/v1",
        ("openai/whisper-large-v3-turbo",),
    ),
    Preset(
        "elevenlabs",
        "ElevenLabs · Scribe",
        "transcription",
        "elevenlabs",
        "https://api.elevenlabs.io/v1",
        ("scribe_v2", "scribe_v1"),
    ),
    Preset(
        "mimo-asr",
        "小米 MiMo · 语音识别",
        "transcription",
        "mimo-asr",
        "https://api.xiaomimimo.com/v1",
        ("mimo-v2.5-asr",),
    ),
    Preset(
        "custom-asr", "自定义 · multipart 录音转写", "transcription", "multipart", ""
    ),
    Preset(
        "custom-chat",
        "自定义 · Chat Completions 润色",
        "polishing",
        "openai",
        "https://api.deepseek.com",
        (),
    ),
)


def asr_capability(model: str, adapter: str, parameters: dict) -> str:
    """Return supported/unsupported/unknown, never a verified capability claim."""
    value = model.strip().lower()
    realtime = parameters.get("asr_protocol") == "qwen_realtime"
    if re.search(
        r"(?:tts|text-to-speech|embedding|rerank|image|dall-e|stable-diffusion|flux|vision)",
        value,
    ):
        return "unsupported"
    qwen_live = bool(
        re.fullmatch(r"qwen3-asr-flash-realtime(?:-\d{4}-\d{2}-\d{2})?", value)
    )
    qwen_http = bool(
        re.fullmatch(
            r"(?:qwen3-asr-flash|qwen-audio-3\.\d+-asr-flash|fun-asr-flash)(?:-\d{4}-\d{2}-\d{2})?",
            value,
        )
    )
    multipart = bool(
        re.fullmatch(
            r"(?:[a-z0-9_-]+/)?(?:whisper-[a-z0-9.-]+|gpt-4o(?:-mini)?-transcribe(?:-\d{4}-\d{2}-\d{2})?|sensevoicesmall|telespeechasr|glm-asr-[a-z0-9.-]+|asr-1\.0)",
            value,
        )
    )
    known = (
        qwen_live
        or qwen_http
        or multipart
        or value in {"scribe_v1", "scribe_v2", "mimo-v2.5-asr"}
    )
    match = {
        "qwen": qwen_live if realtime else qwen_http,
        "multipart": multipart and not realtime,
        "openrouter-asr": multipart and not realtime,
        "elevenlabs": value in {"scribe_v1", "scribe_v2"} and not realtime,
        "mimo-asr": value == "mimo-v2.5-asr" and not realtime,
    }.get(adapter, False)
    if match:
        return "supported"
    if value == "fun-asr" or re.fullmatch(r"fun-asr(?:-mtl)?-\d{4}-\d{2}-\d{2}", value):
        return "unsupported"
    if known or any(
        token in value for token in ("filetrans", "realtime", "streaming", "paraformer")
    ):
        return "unsupported"
    if (
        value.startswith(
            (
                "deepseek",
                "claude",
                "gpt-",
                "qwen",
                "gemini",
                "glm-",
                "llama",
                "mimo-",
                "minimax",
            )
        )
        and "asr" not in value
    ):
        return "unsupported"
    return "unknown"
