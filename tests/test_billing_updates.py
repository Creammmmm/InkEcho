import asyncio

import httpx
import pytest

from inkecho.billing import fetch_balance
from inkecho.updates import check_for_update


def run(coroutine):
    return asyncio.run(coroutine)


def test_balance_official_and_redacted():
    async def scenario():
        def handler(request):
            assert str(request.url) == "https://api.deepseek.com/user/balance"
            assert request.headers["Authorization"] == "Bearer test-only"
            return httpx.Response(
                200,
                json={
                    "is_available": True,
                    "balance_infos": [
                        {
                            "currency": "CNY",
                            "total_balance": "1.20",
                            "granted_balance": "0",
                            "topped_up_balance": "1.20",
                        }
                    ],
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await fetch_balance("deepseek", "test-only", client=client)
        assert result.status == "ok"
        assert result.balances[0].total == "1.20"
        assert "test-only" not in repr(result)

    run(scenario())


@pytest.mark.parametrize(
    "provider,key,status",
    [
        ("qwen", "fake", "unsupported"),
        ("deepseek", "", "missing_key"),
    ],
)
def test_balance_no_request(provider, key, status):
    async def scenario():
        def handler(request):
            pytest.fail("unexpected request")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            assert (await fetch_balance(provider, key, client=client)).status == status

    run(scenario())


@pytest.mark.parametrize(
    "body",
    [
        {
            "is_available": True,
            "balance_infos": [{"currency": "CNY", "total_balance": "NaN"}],
        },
        {"is_available": "yes", "balance_infos": []},
        None,
    ],
)
def test_balance_bad_payload_safe(body):
    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=body)
            )
        ) as client:
            result = await fetch_balance("deepseek", "test-only", client=client)
        assert result.status == "error"
        assert "test-only" not in repr(result)

    run(scenario())


def release_payload():
    prefix = "https://github.com/Creammmmm/InkEcho/releases"
    return {
        "tag_name": "v0.10.0",
        "draft": False,
        "prerelease": False,
        "html_url": prefix + "/tag/v0.10.0",
        "assets": [
            {
                "name": "InkEcho-0.10.0-x86_64.AppImage",
                "browser_download_url": prefix
                + "/download/v0.10.0/InkEcho-0.10.0-x86_64.AppImage",
            }
        ],
    }


@pytest.mark.parametrize(
    "version,status",
    [("0.9.9", "available"), ("0.10.0", "current"), ("0.11.0", "current")],
)
def test_update_numeric_comparison(version, status):
    async def scenario():
        def handler(request):
            assert str(request.url).endswith("/repos/Creammmmm/InkEcho/releases/latest")
            return httpx.Response(200, json=release_payload())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await check_for_update(version, client=client)
        assert result.status == status
        assert result.download_url.endswith(".AppImage")

    run(scenario())


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/Creammmmm/InkEcho/releases/tag/v0.10.0",
        "https://evil.invalid/releases/tag/v0.10.0",
        "https://github.com/Creammmmm/InkEcho/releases/tag/v0.10.0?x=1",
    ],
)
def test_update_rejects_external_release(url):
    async def scenario():
        data = release_payload()
        data["html_url"] = url
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=data)
            )
        ) as client:
            assert (await check_for_update("0.4.1", client=client)).status == "error"

    run(scenario())


@pytest.mark.parametrize(
    "function,args",
    [(fetch_balance, ("deepseek", "test-only")), (check_for_update, ("0.4.1",))],
)
def test_cancellation_propagates(function, args):
    async def scenario():
        async def handler(request):
            raise asyncio.CancelledError

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(asyncio.CancelledError):
                await function(*args, client=client)

    run(scenario())


@pytest.mark.parametrize(
    "adapter,host,console",
    [
        ("openai", "api.deepseek.com", "platform.deepseek.com/usage"),
        ("qwen", "dashscope.aliyuncs.com", "bailian.console.aliyun.com/"),
        ("multipart", "api.openai.com", "platform.openai.com/usage"),
        ("openai-responses", "api.openai.com", "platform.openai.com/usage"),
        ("multipart", "api.siliconflow.cn", "cloud.siliconflow.cn/"),
        ("stepfun-http", "api.stepfun.com", "platform.stepfun.com/"),
        ("stepfun-realtime", "api.stepfun.com", "platform.stepfun.com/"),
        ("multipart", "api.groq.com", "console.groq.com/"),
    ],
)
def test_console_fixed_official_hosts(adapter, host, console):
    from inkecho.billing import console_for_provider
    from inkecho.config import Provider

    provider = Provider("test", "Test", "transcription", adapter, f"https://{host}/v1")
    assert console_for_provider(provider) == f"https://{console}"


@pytest.mark.parametrize(
    "adapter,url",
    [
        ("qwen", "https://gateway.invalid/v1"),
        ("qwen", "https://api.deepseek.com/v1"),
        ("custom", "https://api.deepseek.com/v1"),
        ("openai", "https://api.deepseek.com.evil.invalid/v1"),
        ("openai", "https://api.deepseek.com:8443/v1"),
        ("openai", "https://api.deepseek.com/v1?secret=test"),
    ],
)
def test_console_unknown_or_mismatched_has_no_link(adapter, url):
    from types import SimpleNamespace

    from inkecho.billing import console_for_provider

    provider = SimpleNamespace(adapter=adapter, base_url=url)
    assert console_for_provider(provider) == ""


def test_balance_preserves_finite_signed_account_amounts():
    """Official schema has no nonnegative bound; do not hide account deficits."""

    async def scenario():
        data = {
            "is_available": False,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "-1.20",
                    "granted_balance": "0.00",
                    "topped_up_balance": "-1.20",
                }
            ],
        }
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=data)
            )
        ) as client:
            result = await fetch_balance("deepseek", "test-only", client=client)
        assert result.status == "ok" and result.is_available is False
        assert result.balances[0].total == "-1.20"
        assert result.balances[0].topped_up == "-1.20"

    run(scenario())
