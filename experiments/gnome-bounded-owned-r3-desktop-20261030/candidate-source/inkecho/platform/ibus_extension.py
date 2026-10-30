"""Explicit user actions for the untrusted, experimental GNOME Shell bridge.

Installing does not enable it; none of these methods runs without a user action.
"""

import hashlib
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

UUID = "inkecho-ibus-v2-prototype@local.invalid"
FILES = {
    "capability.js": "fcbaf3e7fd0184ca3141f3c4d811f7496ef753fd6282714ec128a26151a1c881",
    "delivery_gate.js": (
        "6900065ef4996dced1e451b7a0f14d744862e1da089e8474caf8d1789b9b9e6d"
    ),
    "extension.js": "b9b762262dd38d3086f029747750a21cb8b62a46d73b05bf70c7fdc307a911b2",
    "metadata.json": "c53d67c6b8d2e9769e7dcf0a3b6545dbc57673e8ea29a7e487bf55761c214317",
}


class ExtensionError(RuntimeError):
    pass


class ExtensionManager:
    def __init__(self, *, source=None, runner=subprocess.run):
        self.source = source or Path(__file__).with_name("ibus_candidate")
        self.runner = runner

    def _run(self, *args):
        env = os.environ.copy()
        for name in ("LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH"):
            env.pop(name, None)
        env["LC_ALL"] = "C"
        try:
            result = self.runner(
                ["/usr/bin/gnome-extensions", *args],
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ExtensionError("GNOME 扩展服务不可用。") from exc
        if result.returncode:
            raise ExtensionError(
                "操作未完成：扩展可能已存在、尚未加载，或当前桌面不支持。"
            )
        return result.stdout

    def status(self):
        try:
            output = self._run("info", UUID)
        except ExtensionError:
            return "未发现扩展或扩展服务不可用；安装后可能需要重新登录。"
        try:
            self._verify_installed(output)
        except ExtensionError:
            return "扩展文件未通过校验；无法确认当前安装的是 InkEcho 扩展。"
        for line in output.splitlines():
            if line.strip().startswith("State:"):
                state = line.split(":", 1)[1].strip().upper()
                return {
                    "ACTIVE": (
                        "扩展显示正在运行，安装文件已校验；"
                        "运行代码和输入框兼容性尚未确认。"
                    ),
                    "ENABLED": "扩展已启用但运行状态未确认。",
                    "INACTIVE": "扩展已安装但未运行。",
                    "DISABLED": "扩展已停用。",
                    "ERROR": "扩展运行出错；请停用并改用键盘输出。",
                    "OUT_OF_DATE": "扩展与当前 GNOME 版本不兼容。",
                }.get(state, "扩展状态无法确认。")
        return "扩展已发现，但运行状态无法确认。"

    @staticmethod
    def _verified(source):
        payload = {}
        for name, digest in FILES.items():
            path = source / name
            if path.is_symlink():
                raise ExtensionError("扩展文件不安全。")
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise ExtensionError("应用中缺少扩展文件。") from exc
            if hashlib.sha256(data).hexdigest() != digest:
                raise ExtensionError("扩展文件校验失败。")
            payload[name] = data
        return payload

    def install(self):
        payload = self._verified(self.source)
        try:
            with tempfile.TemporaryDirectory(prefix="inkecho-ibus-") as temporary:
                archive = Path(temporary) / "extension.zip"
                with zipfile.ZipFile(
                    archive, "w", compression=zipfile.ZIP_DEFLATED
                ) as out:
                    for name, data in payload.items():
                        out.writestr(name, data)
                self._run("install", str(archive))
        except OSError:
            raise ExtensionError(
                "扩展暂存文件处理失败，请检查临时目录权限和空间并确认扩展状态。"
            ) from None

    def _verify_installed(self, info):
        paths = [
            line.split(":", 1)[1].strip()
            for line in info.splitlines()
            if line.strip().startswith("Path:")
        ]
        if len(paths) != 1 or not Path(paths[0]).is_absolute():
            raise ExtensionError("无法确认已安装扩展的位置；未启用。")
        self._verified(Path(paths[0]))

    def enable(self):
        self._verify_installed(self._run("info", UUID))
        self._run("enable", UUID)

    def disable(self):
        self._run("disable", UUID)
