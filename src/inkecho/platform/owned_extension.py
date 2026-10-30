"""Explicit install/enable operations; never invoked by automatic detection."""

import hashlib
import os
import stat
import subprocess
from pathlib import Path

from inkecho.platform.ibus_extension import ExtensionError, ExtensionManager
from inkecho.platform.owned_installation import (
    FILES,
    UUID,
    installed_directory,
    verified_installation,
)


class OwnedExtensionManager(ExtensionManager):
    def __init__(self, *, source=None, runner=subprocess.run):
        def private_runner(arguments, **options):
            # GNOME's CLI creates the UUID directory with its inherited umask.
            # Scope this restriction to installation, never process-global state.
            if len(arguments) > 1 and arguments[1] == "install":
                options["umask"] = 0o077
            return runner(arguments, **options)

        super().__init__(
            source=source or Path(__file__).with_name("ibus_owned_candidate"),
            runner=private_runner,
        )

    @staticmethod
    def _verified(source):
        payload = {}
        for name, expected in FILES.items():
            path = source / name
            if path.is_symlink():
                raise ExtensionError("扩展文件不安全。")
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode):
                        raise OSError
                    data = stream.read(expected["size"] + 1)
            except OSError:
                raise ExtensionError("应用中缺少扩展文件。") from None
            if (
                len(data) != expected["size"]
                or hashlib.sha256(data).hexdigest() != expected["sha256"]
            ):
                raise ExtensionError("扩展文件校验失败。")
            payload[name] = data
        return payload

    def _verify_installed(self, info):
        paths = [
            line.split(":", 1)[1].strip()
            for line in info.splitlines()
            if line.strip().startswith("Path:")
        ]
        if paths != [str(installed_directory())]:
            raise ExtensionError("无法确认已安装扩展的位置；未启用。")
        try:
            valid = verified_installation()
        except Exception:
            raise ExtensionError("扩展文件校验失败；未启用。") from None
        if not valid:
            raise ExtensionError("未发现当前版本的扩展；未启用。")
        try:
            self._verified(installed_directory())
        except ExtensionError:
            raise ExtensionError(
                "检测到完整旧版自动输入扩展。请先停用并卸载旧扩展，"
                "再安装本版本并重新登录桌面；尚未启用或替换文件。"
            ) from None

    def install(self):
        # Never overwrite a complete old extension, mixed files or a symlink.
        # GNOME may also keep old modules loaded until the next login.
        root = installed_directory()
        if os.path.lexists(root):
            self._verify_installed(self._run("info", UUID))
            raise ExtensionError(
                "当前扩展文件已安装；如服务仍为旧协议，请重新登录桌面。"
            )
        super().install()

    def enable(self):
        self._verify_installed(self._run("info", UUID))
        self._run("enable", UUID)

    def disable(self):
        self._run("disable", UUID)

    def status(self):
        try:
            info = self._run("info", UUID)
            self._verify_installed(info)
        except ExtensionError as error:
            return str(error)
        return "扩展文件已校验；自动输出时仍须验证当前目标和服务身份。"
