"""Bounded, read-only account balance queries; never persist credentials."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

import httpx

from inkecho.config import Provider


@dataclass(frozen=True)
class BalanceAmount:
    currency: str
    total: str
    granted: str
    topped_up: str


@dataclass(frozen=True)
class BalanceResult:
    status: str
    message: str
    balances: tuple[BalanceAmount, ...] = ()
    console_url: str = ""
    is_available: bool | None = None


def console_for_provider(provider: Provider) -> str:
    """Return a fixed official console only for a known adapter + API host.

    This does not query an account or infer that its balance API is supported.
    Custom gateways and mismatched adapters receive no inferred console link.
    """
    try:
        parsed = urlsplit(provider.base_url)
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
        ):
            return ""
        targets = {
            "api.deepseek.com": ({"openai"}, "https://platform.deepseek.com/usage"),
            "dashscope.aliyuncs.com": (
                {"qwen", "dashscope-ws", "openai"},
                "https://bailian.console.aliyun.com/",
            ),
            "api.openai.com": (
                {"multipart", "openai", "openai-responses"},
                "https://platform.openai.com/usage",
            ),
            "api.siliconflow.cn": (
                {"multipart", "openai"},
                "https://cloud.siliconflow.cn/",
            ),
            "api.stepfun.com": (
                {"stepfun-http", "stepfun-realtime", "openai"},
                "https://platform.stepfun.com/",
            ),
            "api.groq.com": ({"multipart", "openai"}, "https://console.groq.com/"),
        }
        item = targets.get(parsed.hostname)
        return item[1] if item and provider.adapter in item[0] else ""
    except ValueError:
        return ""


def balance_platform(provider: Provider) -> str:
    """Recognize only the adapter and exact endpoint whose balance API we support."""
    if provider.adapter == "openai" and provider.base_url.rstrip("/") in {
        "https://api.deepseek.com",
        "https://api.deepseek.com/v1",
    }:
        return "deepseek"
    return ""


def _amount(value: object) -> str:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError
    return str(number)


async def fetch_balance(
    provider_id: str,
    api_key: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 10,
) -> BalanceResult:
    """Query only the official DeepSeek endpoint for the selected configuration.

    Unknown platforms are not queried. Caller owns cancellation and supplied clients.
    Server error bodies and exception strings are never returned to the UI.
    """
    console = "https://platform.deepseek.com/usage" if provider_id == "deepseek" else ""
    if provider_id != "deepseek":
        return BalanceResult(
            "unsupported", "余额未知：当前适配未提供余额查询，请到官方控制台查看。"
        )
    if not api_key.strip():
        return BalanceResult("missing_key", "请先保存 API Key。", console_url=console)
    if client is None:
        async with httpx.AsyncClient(follow_redirects=False) as owned:
            return await fetch_balance(
                provider_id, api_key, client=owned, timeout=timeout
            )
    try:
        response = await client.get(
            "https://api.deepseek.com/user/balance",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            },
            timeout=timeout,
            follow_redirects=False,
        )
        if response.status_code in (401, 403):
            return BalanceResult(
                "unauthorized", "密钥无效或无查询权限。", console_url=console
            )
        if response.status_code != 200:
            return BalanceResult(
                "error", "余额查询失败，请稍后重试。", console_url=console
            )
        data = response.json()
        available = data["is_available"]
        rows = data["balance_infos"]
        if type(available) is not bool or not isinstance(rows, list) or len(rows) > 10:
            raise ValueError
        balances = []
        for row in rows:
            if row["currency"] not in ("CNY", "USD"):
                raise ValueError
            balances.append(
                BalanceAmount(
                    row["currency"],
                    _amount(row["total_balance"]),
                    _amount(row["granted_balance"]),
                    _amount(row["topped_up_balance"]),
                )
            )
        return BalanceResult(
            "ok", "已查询账户余额。", tuple(balances), console, available
        )
    except httpx.TimeoutException:
        return BalanceResult("error", "余额查询超时。", console_url=console)
    except (httpx.HTTPError, ValueError, InvalidOperation, KeyError, TypeError):
        return BalanceResult(
            "error", "余额查询失败或返回数据无效。", console_url=console
        )
