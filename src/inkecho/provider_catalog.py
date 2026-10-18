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
    protocol: str = "http"


WS_ASR_ADAPTERS = frozenset(
    {"stepfun-realtime", "dashscope-ws", "xfyun", "tencent-asr", "volcengine"}
)
HTTP_ASR_ADAPTERS = frozenset(
    {
        "multipart",
        "elevenlabs",
        "mimo-asr",
        "openrouter-asr",
        "stepfun-http",
        "zhipu-asr",
        "minimax-asr",
        "zenmux-asr",
        "orca-audio",
    }
)
STATIC_MODEL_ADAPTERS = frozenset(
    {"elevenlabs", "mimo-asr", "minimax-asr", "zhipu-asr", *WS_ASR_ADAPTERS}
)

PRESETS = (
    Preset(
        "xfyun",
        "讯飞 · 实时听写",
        "transcription",
        "xfyun",
        "https://iat-api.xfyun.cn",
        ("iat",),
        ("app_id", "api_key", "api_secret"),
        "xfyun_iat",
    ),
    Preset(
        "tencent-asr",
        "腾讯云 · 实时识别",
        "transcription",
        "tencent-asr",
        "https://asr.cloud.tencent.com",
        ("16k_zh", "16k_en", "16k_zh_large"),
        ("app_id", "secret_id", "secret_key"),
        "tencent_asr",
    ),
    Preset(
        "volcengine-key",
        "火山 · API Key 实时识别",
        "transcription",
        "volcengine",
        "https://openspeech.bytedance.com",
        ("bigmodel",),
        ("api_key",),
        "volc_binary",
    ),
    Preset(
        "volcengine-app",
        "火山 · App / Access 实时识别",
        "transcription",
        "volcengine",
        "https://openspeech.bytedance.com",
        ("bigmodel",),
        ("app_key", "access_key"),
        "volc_binary",
    ),
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
        "dashscope-fun",
        "百炼 · Fun-ASR 实时任务",
        "transcription",
        "dashscope-ws",
        "https://dashscope.aliyuncs.com/api/v1",
        ("fun-asr-realtime", "fun-asr-realtime-2026-02-28"),
        protocol="dashscope_task",
    ),
    Preset(
        "dashscope-paraformer",
        "百炼 · Paraformer 实时任务",
        "transcription",
        "dashscope-ws",
        "https://dashscope.aliyuncs.com/api/v1",
        ("paraformer-realtime-v2",),
        protocol="dashscope_task",
    ),
    Preset(
        "stepfun-realtime",
        "阶跃星辰 · 实时语音识别",
        "transcription",
        "stepfun-realtime",
        "https://api.stepfun.com/v1",
        ("stepaudio-2.5-asr-stream",),
        protocol="stepfun_realtime",
    ),
    Preset(
        "stepfun-http",
        "阶跃星辰 · 录音转写",
        "transcription",
        "stepfun-http",
        "https://api.stepfun.com/v1",
        ("stepaudio-2.5-asr", "step-asr"),
    ),
    Preset(
        "zhipu-asr",
        "智谱 · 录音转写",
        "transcription",
        "zhipu-asr",
        "https://open.bigmodel.cn/api/paas/v4",
        ("glm-asr-2512",),
    ),
    Preset(
        "minimax-asr",
        "MiniMax · 录音转写",
        "transcription",
        "minimax-asr",
        "https://api.minimax.cn/v1",
        ("asr-1.0",),
    ),
    Preset(
        "zenmux-asr",
        "ZenMux · 录音转写",
        "transcription",
        "zenmux-asr",
        "https://zenmux.ai/api/v1",
        ("qwen/qwen3-asr-flash",),
    ),
    Preset(
        "orca-audio",
        "OrcaRouter · 音频理解转写",
        "transcription",
        "orca-audio",
        "https://api.orcarouter.ai/v1",
        ("google/gemini-2.5-pro",),
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
    http = parameters.get("asr_protocol", "http") == "http"
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
    dashscope = bool(
        re.fullmatch(
            r"(?:fun-asr-realtime|paraformer-realtime-v2)(?:-\d{4}-\d{2}-\d{2})?",
            value,
        )
    )
    step_live = value in {"stepaudio-2.5-asr-stream", "step-asr-1.1-stream"}
    step_http = value in {"stepaudio-2.5-asr", "step-asr"}
    orca_audio = value == "google/gemini-2.5-pro"
    zenmux = value == "qwen/qwen3-asr-flash"
    known = (
        value in {"iat", "16k_zh", "16k_en", "16k_zh_large", "bigmodel"}
        or dashscope
        or step_live
        or step_http
        or orca_audio
        or zenmux
        or qwen_live
        or qwen_http
        or multipart
        or value in {"scribe_v1", "scribe_v2", "mimo-v2.5-asr"}
    )
    match = {
        "xfyun": value == "iat" and parameters.get("asr_protocol") == "xfyun_iat",
        "tencent-asr": value in {"16k_zh", "16k_en", "16k_zh_large"}
        and parameters.get("asr_protocol") == "tencent_asr",
        "volcengine": value == "bigmodel"
        and parameters.get("asr_protocol") == "volc_binary",
        "qwen": qwen_live if realtime else qwen_http and http,
        "multipart": multipart and http,
        "openrouter-asr": multipart and http,
        "dashscope-ws": dashscope
        and parameters.get("asr_protocol") == "dashscope_task",
        "stepfun-http": step_http and http,
        "stepfun-realtime": step_live
        and parameters.get("asr_protocol") == "stepfun_realtime",
        "zhipu-asr": value == "glm-asr-2512" and http,
        "minimax-asr": value == "asr-1.0" and http,
        "zenmux-asr": zenmux and http,
        "orca-audio": orca_audio and http,
        "elevenlabs": value in {"scribe_v1", "scribe_v2"} and http,
        "mimo-asr": value == "mimo-v2.5-asr" and http,
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
        value.rsplit("/", 1)[-1].startswith(
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
