# InkEcho

InkEcho 是一个 Linux 桌面语音输入应用：录音后调用云端转写，可选按 Prompt 润色，再通过辅助功能接口向已校验的文本目标输入文字。默认不读取、修改或使用剪贴板。

当前版本为 **0.1.0a1 开发预览版**。已有可运行的中文设置界面、录音、供应商配置、任务取消、焦点保护、统计、桌面集成及 AppImage 构建。安全输入已在隔离 X11 的 GTK 可编辑控件实测；原生 Wayland 输入暂未启用，本机 Chrome 与 VTE 终端不提供所需接口。不能据此宣称“任意应用均支持”。

![InkEcho 开发预览版实际运行界面](docs/images/inkecho-home.png)

截图来自本次实际 AppImage，在隔离 X11 测试环境运行。

## 运行

需要 Linux 图形桌面、音频服务、AT-SPI 辅助功能服务，以及已解锁的系统 Secret Service（例如 GNOME Keyring）。云端功能需要自行配置对应供应商的有效密钥与模型。Ubuntu 24.04/26.04 的完整 Wayland/X11 桌面矩阵尚未全部实测。

源码运行需要 Python 3.12+ 和 uv：

```sh
uv sync --locked
uv run python -m inkecho
```

在界面中分别设置转录与润色服务，测试麦克风，选择 Prompt；GNOME 快捷键需要在录音设置页主动启用。其他桌面可自行将快捷键绑定到 `python -m inkecho --toggle`，使用实际安装的 Python 完整路径。失焦、取消或不支持的目标会停止流程，不会自动粘贴。

本地发布产物为 `dist/InkEcho-0.1.0-alpha-x86_64.AppImage`（约 103 MiB）：

```sh
chmod +x dist/InkEcho-0.1.0-alpha-x86_64.AppImage
./dist/InkEcho-0.1.0-alpha-x86_64.AppImage
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
