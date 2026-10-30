# Fcitx 重新启用验证

2026-10-31，隔离私有 D-Bus 和 PID/网络命名空间中运行真实 Fcitx 5.1.19，临时配置、临时 HOME，不连接用户的图形会话或输入法服务。使用真实插件和当前源码：实际导入 `fcitx5_install.py` 的 SHA-256 为 `407cd00c47fcf277f247827cc86c5a04b75fd7d1074abbdf3d721552de7ddae9`。夹具自行构造源清单，并用子类固定系统版本，未验证正式包的系统探测或安装路径。

正常安装及刷新后，`GetAddonsV2` 的 InkEcho enabled 位为 true；调用停用再启用后仍为 true。通过 Fcitx 控制接口显式禁用插件后，该位变为 false；再由 InkEcho 停用、恢复及刷新后仍为 false，未擅自改变用户的 Fcitx 插件状态。实验未发送文字。实际结果 SHA-256 为 `2b05c6796dc945438882f6a0c34ef908f7924ac598ba05f56643cc332cf09c07`；探针和启动脚本在本地 `dist/fcitx-restore-private-20261031/`，不在本摘要中归档。最初两轮夹具目录或文件权限不符合安装安全检查，失败后改为私有权限并重跑成功。

离线执行以下命令共 84 项通过，Ruff 检查通过：

```sh
python -m pytest -q tests/test_fcitx5_install.py tests/test_fcitx5_staging.py tests/test_framework_detection.py
python -m ruff check src/inkecho/platform/fcitx5_install.py tests/test_fcitx5_install.py
```

模拟刷新失败或超时，配置保留并提示状态未知；并发替换和同内容删除重建不会被失败处理删除。模拟发布描述后的目录 fsync 或临时文件 unlink 失败时，即使刷新尚未执行，描述也可能已经发布；调用方提示恢复未确认并要求检查，而不声称配置不存在。失败时不自动回滚：按路径删除无法与并发替换安全地原子绑定；请求超时也不证明服务端未执行或插件未加载。若配置留存且服务已加载，后续自动检测仍会执行现有的服务身份、插件启用状态和版本校验。

真实服务实验只覆盖受控私有会话及成功返回的刷新，不证明失败或超时的远端行为，也未测试完整 Session、窗口输入、真实拼音、系统 Portal、Ubuntu 24/26 双系统应用包或所有并发竞态。不得据此扩大兼容性声明。
