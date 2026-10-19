# InkEcho

InkEcho 是 Linux 桌面语音输入应用：录音后调用云端转写，可选按 Prompt 润色，
再把文字输入到输出当时的光标位置。不使用剪贴板或系统输入法。

## v0.5.0

统一五页工作台，并修复原生Wayland语音悬浮预览抢走输入焦点的问题：主设置保持原生，
仅悬浮通过独立XWayland显示宿主运行。概览已移除「准备就绪 / 开始录音」整块，
默认通过快捷键开始 / 停止，准备中和任务中仍可取消。

新0.5.0 AppImage已以同一SHA完成Ubuntu24.04 Xorg、Ubuntu26.04原生Wayland / XWayland
实际包与本机私有FUSE验收；本机稳定入口已更新。下载附件及发布状态以GitHub为准，
精确产品提交、SHA和限制见[0.5.0验收报告](docs/v0.5.0-dual-ubuntu-validation.md)。

## v0.4.0（历史说明）

本版将全部供应商凭据明文保存到当前配置目录的 `credentials.json`，不再依赖系统
密钥环。目录0700、文件0600；旧密钥环不读取或迁移，升级后需重新填写。
旧v0.3.0资产保持原样，行为见[历史验收](docs/v0.3.0-dual-ubuntu-validation.md)。

本版整合18项云ASR供应商/参考入口与四种润色线协议：Chat Completions、Responses、
Anthropic Messages、Gemini。语音模型列表按所选供应商和协议过滤ASR候选，排除纯文本、
TTS、图像、embedding及协议不匹配模型；仍可手填未知模型，但未知不等于已验证。
无发现接口时只显示内置候选，不伪称连接成功。

保留原生Wayland四槽输出、10ms逐字释放等待、整句ASR最终结果与会话收尾重叠及流式
润色/输出。开始录音不捕获目标，录音、识别与润色期间可自由切换窗口；输出时后续字符
跟随新光标。主动取消、过期或被替代后停止未发送文字，已发按键不可撤回或自动重放。

供应商/协议范围、官方依据与本地测试见[适配记录](docs/provider-adaptation-validation.md)。
本版0.4.0 AppImage的实际SHA、双系统凭据/界面/输入及候选FUSE结果见
[本版验收报告](docs/v0.4.0-dual-ubuntu-validation.md)。发布状态以GitHub为准。
本地TLS/WSS/SSE及合成音频测试不代表真实云账户、模型权限或语音准确率认证。

## 下载与运行

发布包为Linux x86_64。从[正式版本列表](https://github.com/Creammmmm/InkEcho/releases)或
[v0.5.0发布页](https://github.com/Creammmmm/InkEcho/releases/tag/v0.5.0)
下载AppImage和同名`.sha256`文件；实际发布状态及最新版以GitHub为准。

```sh
sha256sum -c InkEcho-0.5.0-x86_64.AppImage.sha256
chmod +x InkEcho-0.5.0-x86_64.AppImage
./InkEcho-0.5.0-x86_64.AppImage
```

若旧实例仍运行，请通过其托盘或界面正常退出再启动新版；单实例通信可能只唤起旧实例。
升级不会自动更改用户的供应商、模型、快捷键或密钥。不要把文档中的示例当作本机设置。

需要Linux图形桌面和音频服务，不再依赖系统密钥环。配置语音与润色模型、有效凭据，
再选择风格模板。实时ASR必须选择平台支持的对应协议，不能只修改模型名称。
GNOME快捷键需要用户主动启用，其他桌面可自行绑定应用的`--toggle`入口。

2026-10-20 源码界面已整合为**概览、模型配置、风格、设置、帮助**五页：概览提供
三项使用统计、七日图、模型选择与显式计费刷新；模型页合并语音和润色；设置集中超时、
录音、快捷键与Siri灵感悬浮预览；帮助可手动检查正式版。新配置目录不预建默认平台，
需自行命名、填写并保存；已有配置保留。窗口关闭到托盘，无托盘时保留最小化恢复入口。
0.4.4本地工作台完成交付后，0.5.0已独立重新构建并通过同SHA双Ubuntu实际验收；
Siri悬浮在Wayland仅用独立XWayland显示宿主，主设置保持原生，不抢测试目标焦点。
默认通过快捷键开始录音，概览不再显示开始录音卡片。
详见[0.5.0包验收](docs/v0.5.0-dual-ubuntu-validation.md)、
[使用指南](docs/user-guide.md)和[界面验证记录](docs/ui-redesign-validation.md)。

实际验证范围为Ubuntu24.04.5/GNOME46 Xorg，以及Ubuntu26.04.1/GNOME50.1原生Wayland
和XWayland的限定自有测试目标。GNOME46原生Wayland仍不支持；不保证任意应用或
完整桌面组合。原生路径只接受BMP文本，emoji等非BMP字符明确拒绝；输出前须松开修饰键
并关闭Caps Lock，已有预编辑或输入法状态可能影响目标接收。X11/XWayland另行验证。
本次未验证真实麦克风、物理快捷键、真实云账户或guest FUSE，不增加Windows/macOS支持。

源码运行需要Python3.12+和uv：

```sh
uv sync --locked
uv run python -m inkecho
```

打包、系统依赖和桌面集成见[打包说明](docs/packaging.md)。启动器、图标、自启动由用户
主动安装；移动AppImage后可在设置中修复路径。

## 验证与文档

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

本地协议测试需要允许回环套接字；受限沙箱的socket权限错误不代表供应商服务已测试失败。
推送前还须按[开发规范](docs/DEVELOPMENT.md)为精确提交执行完整检查并生成记录。

- [用户指南](docs/user-guide.md) · [故障排查](docs/troubleshooting.md)
- [兼容性矩阵](docs/compatibility-matrix.md) · [实际验收清单](docs/acceptance-checklist.md)
- [架构](docs/architecture.md) · [供应商](docs/providers.md) · [配置与凭据](docs/configuration.md)
- [项目规范](docs/PROJECT_SPEC.md) · [Agent入口](AGENTS.md)

## 历史证据

以下报告只证明其记录的版本与范围，不代表当前用户的模型、快捷键或运行进程状态。

- [0.2.10供应商包验收](docs/provider-dual-ubuntu-validation.md)
- [v0.2.0验收](docs/v0.2.0-dual-ubuntu-validation.md) · [a18验收](docs/a18-dual-ubuntu-validation.md)
- [a14双系统报告](docs/a14-dual-ubuntu-validation.md) · [a13包](docs/performance-a13-package-validation.md)
- [a12慢流反例](docs/performance-a12-paced-validation.md) · [a11负面记录](docs/performance-a11-package-validation.md)
- [性能总览](docs/performance-validation.md) · [原生Wayland技术验证](docs/native-wayland-keymap-validation.md)
- [当前光标语义验收](docs/current-cursor-input-validation.md) · [键盘传输证据](docs/keyboard-transport-validation.md)

## 隐私与许可证

音频在内存中处理，默认不保存录音或识别正文。转录会把音频发到用户配置的云服务；
开启润色会进一步发送识别文字。按用户2026-10-19修订，全部认证字段以明文保存在
当前配置目录的专用`credentials.json`（目录0700/文件0600），其余配置仅保存引用。
不读取或迁移旧系统密钥环，旧引用需重新填写；日志不保存密钥。统计只保存汇总数字，缺失Token用量明确显示未知。

项目采用[MIT License](LICENSE)。随包运行时许可见[第三方声明](THIRD_PARTY_NOTICES.md)。
参考OpenLESS目录与协议行为的独立实现边界见适配记录；未引入其AGPL源码或库。
