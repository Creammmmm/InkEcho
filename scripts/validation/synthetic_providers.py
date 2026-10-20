"""Explicit credential-free synthetic legacy records for tests and probes only.

New installations intentionally contain no provider records. This module is not
part of the shipped inkecho package and must only seed isolated configuration.
"""

from inkecho.config import Provider

SYNTHETIC_PROVIDERS = (
    Provider(
        "qwen",
        "Alibaba Qwen",
        "transcription",
        "qwen",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "",
        "provider/qwen",
    ),
    Provider(
        "deepseek",
        "DeepSeek",
        "polishing",
        "openai",
        "https://api.deepseek.com",
        "",
        "provider/deepseek",
    ),
)
