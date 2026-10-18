"""One explicit adapter selection shared by Session, capability tests and forms."""

from importlib import import_module

from inkecho.config import Provider
from inkecho.providers import ProviderError

ADAPTERS = {
    "xfyun": ("inkecho.xfyun_realtime", "XfyunConfig", "XfyunSession"),
    "tencent-asr": ("inkecho.tencent_realtime", "TencentConfig", "TencentSession"),
    "volcengine": ("inkecho.volc_realtime", "VolcConfig", "VolcSession"),
    "qwen": ("inkecho.realtime", "RealtimeConfig", "QwenRealtimeSession"),
    "stepfun-realtime": (
        "inkecho.step_realtime",
        "StepRealtimeConfig",
        "StepRealtimeSession",
    ),
    "dashscope-ws": (
        "inkecho.dashscope_realtime",
        "DashscopeRealtimeConfig",
        "DashscopeRealtimeSession",
    ),
}


def classes(adapter: str) -> tuple[type, type]:
    """Resolve only the built-in allowlist, never an import named by user JSON."""
    names = ADAPTERS.get(adapter)
    if names is None:
        raise ProviderError("configuration")
    module = import_module(names[0])
    return getattr(module, names[1]), getattr(module, names[2])


def streaming_config(provider: Provider, *, sample_rate: int = 16000) -> object:
    config, _ = classes(provider.adapter)
    return config.from_provider(provider, sample_rate=sample_rate)


def create_streaming_session(
    provider: Provider, config: object, key: str, *, qwen_factory=None, **policy
) -> object:
    config_type, factory = classes(provider.adapter)
    if not isinstance(config, config_type):
        raise ProviderError("configuration")
    if provider.adapter == "qwen" and qwen_factory is not None:
        factory = qwen_factory
    return factory(config, key, **policy)
