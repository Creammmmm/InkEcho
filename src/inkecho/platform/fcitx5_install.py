"""Explicit user actions for the experimental Fcitx addon candidate."""

import hashlib
import os
import platform
import re
import subprocess
from contextlib import ExitStack
from pathlib import Path

from . import fcitx5_staging as staging


class FcitxInstallError(RuntimeError):
    pass


class FcitxInstaller:
    def __init__(self, *, source=None, data_home=None, runner=subprocess.run):
        appdir = os.environ.get("APPDIR")
        self.source = source or (
            Path(appdir) / "usr/share/inkecho/fcitx5/x86_64" if appdir else None
        )
        if data_home:
            self.data_home = Path(data_home)
        else:
            configured = Path(os.environ.get("XDG_DATA_HOME", ""))
            self.data_home = (
                configured if configured.is_absolute() else Path.home() / ".local/share"
            )
        self.runner = runner

    def _run(self, args):
        env = os.environ.copy()
        for key in ("LD_LIBRARY_PATH", "PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH"):
            env.pop(key, None)
        env["LC_ALL"] = "C"
        try:
            result = self.runner(
                args, capture_output=True, text=True, timeout=10, env=env, check=False
            )
        except FileNotFoundError as exc:
            if args and args[0] == "/usr/bin/fcitx5":
                raise FcitxInstallError(
                    "无法启动 Fcitx5。请先通过系统软件管理器安装 Fcitx5，"
                    "然后重新检查输入桥。"
                ) from exc
            raise FcitxInstallError("Fcitx5 服务不可用。") from exc
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise FcitxInstallError("Fcitx5 服务不可用。") from exc
        if result.returncode:
            raise FcitxInstallError("操作未完成，请确认 Fcitx5 正在运行。")
        return result.stdout

    def _system(self):
        try:
            release = platform.freedesktop_os_release()
            version = self._run(["/usr/bin/fcitx5", "--version"])
            matches = re.findall(r"\b\d+\.\d+\.\d+\b", version)
            if not matches:
                raise ValueError("version unavailable")
            system = (
                release.get("ID", ""),
                release.get("VERSION_ID", ""),
                platform.machine(),
                matches[0],
            )
            if (
                system not in staging.TESTED_SYSTEMS
                or not staging.TESTED_CANDIDATE_SHA256
            ):
                raise ValueError("not tested")
            return system
        except (OSError, ValueError) as exc:
            raise FcitxInstallError(
                "当前系统或 Fcitx5 版本没有通过此插件的验证。"
            ) from exc

    def install(self):
        system = self._system()
        if self.source is None:
            raise FcitxInstallError("应用中没有可用的输入桥候选文件。")
        # A verified existing installation is already the desired state. Never
        # replace it: Fcitx may have the library mapped in a running process.
        if self._check_staged(system[3]):
            return
        try:
            staging.stage(
                self.source,
                self.data_home,
                os_id=system[0],
                os_version=system[1],
                architecture=system[2],
                fcitx_version=system[3],
            )
        except (OSError, ValueError, staging.StagingError) as exc:
            # Another installer may have atomically published the same bridge
            # after our initial check. Never accept a different description.
            if (
                isinstance(exc, FileExistsError)
                or isinstance(exc, staging.StagingError)
                and str(exc) == "description_exists"
            ) and self._check_staged(system[3]):
                return
            if isinstance(exc, OSError):
                # Publication may already have happened before fsync or
                # temporary-file cleanup failed; never claim it was absent.
                raise FcitxInstallError(
                    "安装结果未确认：配置可能已发布或已有输入桥配置，请检查输入桥状态。"
                ) from exc
            raise FcitxInstallError(
                "安装未完成：文件校验失败或已有输入桥配置。"
            ) from exc

    def _check_staged(self, version):
        digest = staging.TESTED_CANDIDATE_SHA256
        if not digest:
            return False
        try:
            with ExitStack() as stack:
                data = staging._directory(self.data_home)
                stack.callback(os.close, data)
                addon_parent = staging._child(data, "fcitx5", create=False)
                stack.callback(os.close, addon_parent)
                addon = staging._child(addon_parent, "addon", create=False)
                stack.callback(os.close, addon)
                expected = staging._conf(
                    str(self.data_home / "inkecho/fcitx5" / digest / "libinkecho"),
                    version,
                )
                if staging._read(addon, "inkecho.conf", 65536) != expected:
                    return False
                owned = staging._child(data, "inkecho", create=False)
                stack.callback(os.close, owned)
                versions = staging._child(owned, "fcitx5", create=False)
                stack.callback(os.close, versions)
                candidate = staging._child(versions, digest, create=False)
                stack.callback(os.close, candidate)
                library = staging._read(candidate, "libinkecho.so", 16 * 1024 * 1024)
                return hashlib.sha256(library).hexdigest() == digest
        except (OSError, ValueError, staging.StagingError):
            return False

    def status(self):
        system = self._system()
        if not self._check_staged(system[3]):
            return "未发现经过校验的输入桥；可能尚未安装。"
        return "已安装输入桥；运行状态需通过输入服务检查确认。"

    def available_for_auto(self):
        """Require a verified current system and its still-published bridge."""
        return self.auto_version() is not None

    def auto_version(self):
        """Return the verified disk version to compare with the live core."""
        try:
            system = self._system()
        except FcitxInstallError:
            return None
        return system[3] if self._check_staged(system[3]) else None

    def _can_restore_disabled(self):
        """Recognize a retained verified library with no published description."""
        digest = staging.TESTED_CANDIDATE_SHA256
        if not digest:
            return False
        try:
            with ExitStack() as stack:
                data = staging._directory(self.data_home)
                stack.callback(os.close, data)
                addon_parent = staging._child(data, "fcitx5", create=False)
                stack.callback(os.close, addon_parent)
                addon = staging._child(addon_parent, "addon", create=False)
                stack.callback(os.close, addon)
                try:
                    os.stat("inkecho.conf", dir_fd=addon, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    return False
                owned = staging._child(data, "inkecho", create=False)
                stack.callback(os.close, owned)
                versions = staging._child(owned, "fcitx5", create=False)
                stack.callback(os.close, versions)
                candidate = staging._child(versions, digest, create=False)
                stack.callback(os.close, candidate)
                library = staging._read(candidate, "libinkecho.so", 16 * 1024 * 1024)
                return hashlib.sha256(library).hexdigest() == digest
        except (OSError, ValueError, staging.StagingError):
            return False

    def enable(self):
        system = self._system()
        if not self._check_staged(system[3]):
            if not self._can_restore_disabled():
                raise FcitxInstallError("未找到经过校验的输入桥，请先安装。")
            # Reuse normal staging, which never replaces another description
            # or a library already mapped by the running input service.
            try:
                self.install()
            except FcitxInstallError:
                raise FcitxInstallError(
                    "输入桥恢复未确认，加载配置可能已发布或改变；请检查输入服务状态。"
                ) from None
            if not self._check_staged(system[3]):
                raise FcitxInstallError(
                    "输入桥恢复未确认，加载配置可能已发布或改变；请检查输入服务状态。"
                )
        try:
            self._run(
                [
                    "/usr/bin/gdbus",
                    "call",
                    "--session",
                    "--dest",
                    "org.fcitx.Fcitx5",
                    "--object-path",
                    "/controller",
                    "--method",
                    "org.fcitx.Fcitx.Controller1.Refresh",
                ]
            )
        except FcitxInstallError:
            # A timeout does not prove the remote action did not run. Never
            # remove a potentially concurrent publication by pathname here.
            raise FcitxInstallError(
                "Fcitx5 刷新未确认，加载配置可能已保留或改变，插件状态未知；"
                "请检查输入服务状态，必要时手动停用。"
            ) from None

    def disable(self):
        try:
            for digest in (
                staging.TESTED_CANDIDATE_SHA256,
                *staging.RETIRED_CANDIDATE_SHA256,
            ):
                try:
                    staging.deactivate(self.data_home, digest=digest)
                except staging.StagingError as exc:
                    if str(exc) == "description_changed":
                        continue
                    raise
                return
            raise staging.StagingError("description_changed")
        except (OSError, ValueError, staging.StagingError) as exc:
            raise FcitxInstallError("停用未完成：配置不存在或已被修改。") from exc
