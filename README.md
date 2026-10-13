# InkEcho

InkEcho 是一个 Linux 桌面语音输入应用：录音后调用云端转写，可选按 Prompt 润色，再输入文字。不使用剪贴板或系统输入法。

当前版本为 **0.1.0a7 开发预览版**，采用“输出到当前光标”的键盘输入方式：开始录音不要求先选文本框，录音、识别与润色期间可自由切换窗口；输出中切换窗口，后续字符也可进入新焦点。主动取消和过期任务仍停止未发送的文字，已经发送的按键无法撤回。

当前后端面向 **X11 / XWayland 应用**，不是所有 Wayland 桌面应用。实际 a7 包已在 GNOME Wayland 宿主的自有 GTK XWayland 窗口通过录音、本机 HTTPS 服务、处理中切窗、Unicode 输出与取消验证；Chrome XWayland 另通过输入诊断，VTE XWayland 的自有原始终端也通过生产键盘输入验证（未启动 shell）。原生 Wayland GTK（包括该模式下的 GNOME 文本编辑器）不支持这条新键盘路径。当前 Codex 窗口已确认为 XWayland，但尚未向用户的输入框发送测试文字，不能据此保证兼容。详见[当前光标验收](docs/current-cursor-input-validation.md)及[键盘传输实测](docs/keyboard-transport-validation.md)。

版本化 a7 包已构建、验收并部署到原有稳定启动路径；用户的 Ctrl+F4 和三份 JSON 配置保持不变。此前 alpha6 的[原生 AT-SPI 验收](docs/native-voice-workflow-validation.md)、[独立云端验收](docs/native-cloud-workflow-validation.md)与[音频反馈修复](docs/audio-feedback-validation.md)保留为历史证据；旧版“失焦即取消”不再是 a7 的操作要求。

![InkEcho 开发预览版实际运行界面](docs/images/inkecho-home.png)

截图来自 0.1.0a7 实际 AppImage，在 Ubuntu 26.04 GNOME Wayland 上以独立默认测试配置运行；图中的 F13 不代表用户当前快捷键设置。

## 运行

需要 Linux 图形桌面、X11 / XWayland 显示与 libX11、音频服务，以及已解锁的系统 Secret Service（例如 GNOME Keyring）。云端功能需要自行配置对应供应商的有效密钥与模型。Ubuntu 24.04/26.04 的完整 Wayland/X11 桌面矩阵尚未全部实测。

源码运行需要 Python 3.12+ 和 uv：

```sh
uv sync --locked
uv run python -m inkecho
```

在界面中分别设置转录与润色服务，测试麦克风，选择 Prompt；GNOME 快捷键需要在录音设置页主动启用。其他桌面可自行将快捷键绑定到 `python -m inkecho --toggle`，使用实际安装的 Python 完整路径。开始后可切换窗口，识别完成时将光标放在希望接收文字的位置。主动取消会停止后续发送；目标不支持时会提示错误，不会自动粘贴。

本地发布产物为 `dist/InkEcho-0.1.0a7-x86_64.AppImage`（约 103 MiB）：

```sh
chmod +x dist/InkEcho-0.1.0a7-x86_64.AppImage
./dist/InkEcho-0.1.0a7-x86_64.AppImage
```

构建步骤、校验和与运行依赖见[打包说明](docs/packaging.md)。桌面启动器、图标与自启动均由用户主动安装；移动 AppImage 后可在设置中修复路径。

## 验证与文档

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

集成测试需要允许本地套接字。部分受限沙箱会禁止 asyncio 的线程唤醒套接字，造成线程测试等待；应在正常本地环境运行。

- [用户指南](docs/user-guide.md) · [故障排查](docs/troubleshooting.md)
- [兼容性矩阵](docs/compatibility-matrix.md) · [实际验收清单](docs/acceptance-checklist.md)
- [架构](docs/architecture.md) · [供应商](docs/providers.md) · [配置与凭据](docs/configuration.md)
- [阶段 0 实测报告](docs/feasibility-report.md) · [开发与提交流程](docs/DEVELOPMENT.md)
- [项目规范](docs/PROJECT_SPEC.md) · [Agent 开发入口](AGENTS.md)

## 隐私与许可证

音频在内存中处理，默认不保存录音或识别正文。转录会把音频发送到所配置的云端服务；开启润色会进一步发送识别文字。API Key 只通过系统凭据服务保存，普通 JSON 与日志不保存密钥。统计只保存汇总数字，缺失 Token 用量明确显示未知。

项目采用 [MIT License](LICENSE)。随包第三方运行时的许可见[第三方声明](THIRD_PARTY_NOTICES.md)。Windows/macOS 仅预留适配接口，尚未支持。
