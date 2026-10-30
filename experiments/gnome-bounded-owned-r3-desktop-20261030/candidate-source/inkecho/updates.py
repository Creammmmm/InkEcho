"""Manual update discovery; no package download, execution or installation."""

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

_REPO = "Creammmmm/InkEcho"
_RELEASES = f"https://github.com/{_REPO}/releases"


@dataclass(frozen=True)
class UpdateResult:
    status: str
    current_version: str
    latest_version: str = ""
    release_url: str = ""
    download_url: str = ""
    message: str = ""


def _version(value: object) -> tuple[int, int, int]:
    # Project release policy uses stable X.Y.Z, not arbitrary PEP 440 versions.
    if not isinstance(value, str) or not re.fullmatch(
        r"v?\d{1,8}\.\d{1,8}\.\d{1,8}", value
    ):
        raise ValueError
    return tuple(map(int, value.removeprefix("v").split(".")))


def _safe_url(value: object, prefix: str) -> str:
    if not isinstance(value, str):
        return ""
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
        or not value.startswith(prefix)
        or any(c in value for c in ("\\", "\r", "\n"))
        or any(part in (".", "..") for part in parsed.path.split("/"))
        or "%" in parsed.path
    ):
        return ""
    return value


async def check_for_update(
    current_version: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 10,
) -> UpdateResult:
    """Read this repository's latest stable release without credentials."""
    try:
        current = _version(current_version)
    except ValueError:
        return UpdateResult("error", current_version, message="当前版本格式无效。")
    if client is None:
        async with httpx.AsyncClient(follow_redirects=False) as owned:
            return await check_for_update(
                current_version, client=owned, timeout=timeout
            )
    try:
        response = await client.get(
            f"https://api.github.com/repos/{_REPO}/releases/latest",
            headers={"Accept": "application/vnd.github+json"},
            timeout=timeout,
            follow_redirects=False,
        )
        if response.status_code != 200:
            return UpdateResult("error", current_version, message="暂时无法检查更新。")
        data = response.json()
        latest = _version(data["tag_name"])
        if data.get("draft") is not False or data.get("prerelease") is not False:
            raise ValueError
        tag = data["tag_name"]
        release = _safe_url(data["html_url"], f"{_RELEASES}/tag/{tag}")
        if release != f"{_RELEASES}/tag/{tag}":
            raise ValueError
        assets = data.get("assets", [])
        if not isinstance(assets, list) or len(assets) > 100:
            raise ValueError
        download = ""
        for asset in assets:
            if asset.get("name") == f"InkEcho-{tag.removeprefix('v')}-x86_64.AppImage":
                download = _safe_url(
                    asset.get("browser_download_url"), f"{_RELEASES}/download/{tag}/"
                )
                expected = f"{_RELEASES}/download/{tag}/{asset['name']}"
                if download != expected:
                    download = ""
                break
        newer = latest > current
        return UpdateResult(
            "available" if newer else "current",
            current_version,
            tag.removeprefix("v"),
            release,
            download,
            "发现新版本。" if newer else "当前已是最新版本。",
        )
    except httpx.TimeoutException:
        return UpdateResult("error", current_version, message="检查更新超时。")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return UpdateResult(
            "error", current_version, message="检查更新失败或返回数据无效。"
        )
