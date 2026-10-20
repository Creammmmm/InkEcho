"""Offline API onboarding; links are fixed platform metadata, never user URLs."""

from dataclasses import dataclass
from html import escape

from inkecho.provider_catalog import PRESETS


@dataclass(frozen=True)
class PlatformGuide:
    name: str
    console: str
    docs: str
    note: str = "在平台控制台创建 API Key，并确认所选模型已开通且账户有可用额度。"


# Official public entry points reviewed on 2026-10-21. Login pages can redirect.
PLATFORMS = {
    "bailian": PlatformGuide(
        "阿里云百炼",
        "https://bailian.console.aliyun.com/",
        "https://help.aliyun.com/zh/model-studio/get-api-key",
        "在百炼创建 API Key；当前预设为北京地域，密钥、接入地址与模型须属于同一地域。"
        "不要填阿里云 AccessKey。",
    ),
    "xfyun": PlatformGuide(
        "讯飞开放平台",
        "https://console.xfyun.cn/",
        "https://www.xfyun.cn/doc/asr/voicedictation/API.html",
        "创建应用并开通语音听写（流式版）；"
        "在同一应用中获取 APPID、APIKey 和 APISecret。",
    ),
    "tencent-asr": PlatformGuide(
        "腾讯云语音识别",
        "https://console.cloud.tencent.com/asr",
        "https://cloud.tencent.com/document/product/1093/48982",
        "开通实时语音识别；填写账户 AppID 及具有语音识别权限的 SecretId、SecretKey。",
    ),
    "volcengine": PlatformGuide(
        "火山豆包语音",
        "https://console.volcengine.com/speech/app",
        "https://docs.volcengine.com/docs/DoubaoVoice/console-guidance?lang=zh",
        "开通语音识别服务；按所选凭据模式获取 API Key 或应用 App Key / Access Key，"
        "并在资源 ID 填入控制台授权的识别资源，不要填方舟模型的 API Key。",
    ),
    "openai": PlatformGuide(
        "OpenAI",
        "https://platform.openai.com/api-keys",
        "https://developers.openai.com/api/docs/quickstart",
    ),
    "groq": PlatformGuide(
        "Groq",
        "https://console.groq.com/keys",
        "https://console.groq.com/docs/quickstart",
    ),
    "siliconflow": PlatformGuide(
        "硅基流动",
        "https://cloud.siliconflow.cn/",
        "https://docs.siliconflow.cn/docs/usercases/use-siliconcloud-in-trancy",
    ),
    "openrouter": PlatformGuide(
        "OpenRouter",
        "https://openrouter.ai/settings/keys",
        "https://openrouter.ai/docs/quickstart",
    ),
    "elevenlabs": PlatformGuide(
        "ElevenLabs",
        "https://elevenlabs.io/app/developers/api-keys",
        "https://elevenlabs.io/docs/api-reference/authentication",
    ),
    "mimo": PlatformGuide(
        "小米 MiMo",
        "https://platform.xiaomimimo.com/",
        "https://platform.xiaomimimo.com/",
    ),
    "stepfun": PlatformGuide(
        "阶跃星辰", "https://platform.stepfun.com/", "https://platform.stepfun.com/"
    ),
    "zhipu": PlatformGuide(
        "智谱",
        "https://open.bigmodel.cn/",
        "https://docs.bigmodel.cn/cn/guide/start/introduction",
    ),
    "minimax": PlatformGuide(
        "MiniMax",
        "https://platform.minimax.io/",
        "https://platform.minimax.io/",
    ),
    "minimax-cn": PlatformGuide(
        "MiniMax 国内平台",
        "https://platform.minimax.cn/",
        "https://platform.minimax.cn/",
        "在国内平台开通对应语音模型并创建 API Key；密钥、模型与国内接入地址须匹配，"
        "不要与海外平台或其他套餐的凭据混用。",
    ),
    "zenmux": PlatformGuide(
        "ZenMux", "https://zenmux.ai/", "https://docs.zenmux.ai/guide/quickstart.html"
    ),
    "orca": PlatformGuide(
        "OrcaRouter", "https://www.orcarouter.ai/", "https://www.orcarouter.ai/support"
    ),
    "anthropic": PlatformGuide(
        "Anthropic",
        "https://platform.claude.com/",
        "https://platform.claude.com/docs/en/api/overview",
    ),
    "gemini": PlatformGuide(
        "Google AI Studio",
        "https://aistudio.google.com/apikey",
        "https://ai.google.dev/gemini-api/docs/api-key",
    ),
    "opencode": PlatformGuide(
        "OpenCode", "https://opencode.ai/", "https://opencode.ai/docs/zen/"
    ),
    "deepseek": PlatformGuide(
        "DeepSeek",
        "https://platform.deepseek.com/api_keys",
        "https://api-docs.deepseek.com/",
    ),
    "ark": PlatformGuide(
        "火山方舟",
        "https://console.volcengine.com/ark",
        "https://docs.volcengine.com/docs/ark/quick-start?lang=zh",
        "在方舟开通模型并创建 API Key；按控制台说明填写模型 ID 或推理接入点 ID。"
        "语音服务与方舟凭据不能混用。",
    ),
    "atlascloud": PlatformGuide(
        "AtlasCloud",
        "https://www.atlascloud.ai/",
        "https://www.atlascloud.ai/docs/en/api-keys",
    ),
    "cometapi": PlatformGuide(
        "CometAPI", "https://www.cometapi.com/", "https://www.cometapi.com/quickstart/"
    ),
    "requesty": PlatformGuide(
        "Requesty", "https://app.requesty.ai/", "https://docs.requesty.ai/quickstart"
    ),
    "api-route": PlatformGuide(
        "API Route", "https://www.api-route.com/", "https://www.api-route.com/"
    ),
    "codingplanx": PlatformGuide(
        "CodingPlanX", "https://codingplanx.ai/", "https://codingplanx.ai/docs"
    ),
    "tencent-tokenhub": PlatformGuide(
        "腾讯 TokenHub",
        "",
        "",
        "在当前平台控制台开通模型并创建对应 API Key。"
        "此平台公开引导入口尚未核实，请以服务提供方给出的地址为准。",
    ),
}

PRESET_PLATFORMS = {
    "qwen": "bailian",
    "dashscope-fun": "bailian",
    "dashscope-paraformer": "bailian",
    "bailian-chat": "bailian",
    "xfyun": "xfyun",
    "tencent-asr": "tencent-asr",
    "volcengine-key": "volcengine",
    "volcengine-app": "volcengine",
    "openai-asr": "openai",
    "openai-responses": "openai",
    "openai-chat": "openai",
    "groq": "groq",
    "siliconflow": "siliconflow",
    "siliconflow-chat": "siliconflow",
    "openrouter-asr": "openrouter",
    "openrouter-chat": "openrouter",
    "elevenlabs": "elevenlabs",
    "mimo-asr": "mimo",
    "mimo-chat": "mimo",
    "stepfun-realtime": "stepfun",
    "stepfun-http": "stepfun",
    "stepfun-chat": "stepfun",
    "zhipu-asr": "zhipu",
    "minimax-asr": "minimax-cn",
    "minimax-chat": "minimax",
    "minimax-messages": "minimax",
    "zenmux-asr": "zenmux",
    "orca-audio": "orca",
    "orca-chat": "orca",
    "anthropic-messages": "anthropic",
    "gemini-native": "gemini",
    "opencode-responses": "opencode",
    "opencode-chat": "opencode",
    "deepseek-chat": "deepseek",
    "ark-chat": "ark",
    "atlascloud-chat": "atlascloud",
    "cometapi-chat": "cometapi",
    "requesty-chat": "requesty",
    "api-route-chat": "api-route",
    "codingplanx-chat": "codingplanx",
    "tencent-tokenhub": "tencent-tokenhub",
}


def setup_guidance(
    preset_id: str | None,
    base_url: str,
    fields: tuple[str, ...],
    *,
    role: str,
    protocol: str = "http",
    adapter: str = "",
) -> tuple[str, str]:
    """Return a compact summary and escaped HTML without I/O or credential access.

    A selected preset must still match its complete endpoint. A saved custom
    gateway cannot acquire official key instructions merely by sharing an adapter.
    """
    preset = next((p for p in PRESETS if p.id == preset_id), None)
    if preset is None and base_url:
        preset = next(
            (
                p
                for p in PRESETS
                if p.id in PRESET_PLATFORMS
                and p.role == role
                and p.adapter == adapter
                and p.base_url.rstrip("/") == base_url.rstrip("/")
                and (
                    p.protocol == protocol
                    or (p.adapter == "qwen" and protocol in {"http", "qwen_realtime"})
                )
                and (p.adapter != "volcengine" or p.credential_fields == fields)
            ),
            None,
        )
    platform = PRESET_PLATFORMS.get(preset.id if preset else None)
    official = bool(
        preset
        and preset.base_url
        and preset.role == role
        and (not adapter or preset.adapter == adapter)
        and (
            preset.protocol == protocol
            or (preset.adapter == "qwen" and protocol in {"http", "qwen_realtime"})
        )
        and base_url.rstrip("/") == preset.base_url.rstrip("/")
    )
    guide = PLATFORMS[platform] if platform and official else None
    names = {
        "api_key": "API Key",
        "app_id": "AppID",
        "api_secret": "APISecret",
        "secret_id": "SecretId",
        "secret_key": "SecretKey",
        "app_key": "App Key",
        "access_key": "Access Key",
    }
    credentials = "、".join(names[field] for field in fields)
    if guide:
        summary = f"{guide.name} · 获取凭据 → 选择模型 → 保存配置"
        first = guide.note
        links = " · ".join(
            f'<a href="{escape(url, quote=True)}">{title}</a>'
            for title, url in (
                ("平台控制台 ↗", guide.console),
                ("配置文档 ↗", guide.docs),
            )
            if url and (title != "配置文档 ↗" or url != guide.console)
        )
    elif preset_id is None and not base_url:
        summary = "首次配置？先选择服务平台，再查看对应的配置步骤。"
        first = "先选择服务平台；本页会显示该平台的凭据获取入口及填写步骤。"
        links = ""
    else:
        summary = "自定义服务 · 使用当前服务提供方的地址与凭据"
        first = (
            "向当前服务提供方获取 Base URL、模型 ID 和凭据；"
            "不要将其他平台的密钥填入未确认的网关。"
        )
        links = ""
    model_step = (
        "选择语音识别模型；纯文本或语音合成模型不能用于转写。"
        if role == "transcription"
        else "填写可用的文字模型 ID；名称须与控制台一致，不是配置的显示名称。"
    )
    if role == "transcription" and protocol in {
        "qwen_realtime",
        "stepfun_realtime",
        "dashscope_task",
        "xfyun_iat",
        "tencent_asr",
        "volc_binary",
    }:
        model_step += " 当前为实时识别，请在设置中使用 16 kHz 录音。"
    if guide and platform == "bailian" and role == "transcription":
        model_step += (
            " Qwen 实时请选择 qwen3-asr-flash-realtime 与实时转写方式；"
            "HTTP 模型使用录音结束后上传。"
        )
    steps = (
        first,
        f"为配置填写便于辨认的显示名称，将 {credentials} 填入对应凭据栏。{model_step}",
        "点击「保存配置」；更换已有配置时，凭据全部留空可保留原凭据。「测试连接」仅检查模型列表或显示内置目录，不代表语音或润色已验证。",
    )
    details = "<ol>" + "".join(f"<li>{escape(step)}</li>" for step in steps) + "</ol>"
    if links:
        details = f"<p>{links}</p>" + details
    return summary, details
