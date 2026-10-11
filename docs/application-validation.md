# 应用层验证记录

本页区分可复现自动测试、实际桌面观测与仍待验收的项目。其他模块验证见 [阶段 0 报告](feasibility-report.md)、[配置说明](configuration.md) 与 [验收清单](acceptance-checklist.md)。

## 自动回归

```bash
QT_QPA_PLATFORM=offscreen uv run pytest -q tests/test_application.py tests/test_desktop_acceptance.py tests/test_ui.py
```

2026-10-12：应用编排与独立验收回归共 15 项通过，界面交互 7 项通过。这里的编排回归使用替代输入端、录音器、服务响应与凭据后端，验证任务时序，不把替代对象结果视为真实桌面兼容性证据。测试范围包括：

- 转写、润色与注入状态流，鉴权错误的明确提示。
- 捕获目标后密钥读取期间失焦拒绝；主窗口隐藏后的预留切换时间允许选择目标。
- 取消后返回的转写、润色或凭据结果不修改新任务状态；失败的录音启动能释放任务。
- 录音期间修改供应商地址和密钥引用，不改变当前任务的服务快照。
- Qt 实际点击保存外观、模板副本，重新加载可还原；内置模板保持原样。
- 切换供应商后，旧异步模型列表不覆盖新表单；密钥保存前固定配置选项，密码输入框立即清空。
- 自身窗口拒绝快捷键输入；无托盘时处理期间保留取消入口；准备录音期间取消恢复主窗口。
- 九页导航回到顶部，长页面可滚到底部，图标资源有效。

包含后台线程、D-Bus 或 Qt 音频发现的测试应运行在允许本机 IPC 的环境。当前受限执行沙箱曾阻止 asyncio 自唤醒套接字写入，造成线程结果等待挂起；宿主环境运行通过。此限制不应被解释成应用功能成功或失败。

## 实际启动与页面

```bash
QT_QPA_PLATFORM=offscreen uv run python -m inkecho \
  --config-dir /tmp/inkecho-review/config \
  --data-dir /tmp/inkecho-review/data \
  --screenshot-dir /tmp/inkecho-review/pages --quit-after 0.2
```

九页截图启动与正常退出通过。根评审另在专用 Xvfb `:92` 实际启动并逐页审阅；中文显示清楚，长页面可滚动。截图命令输出仅包含页数、Qt 平台和窗口可见性，不含用户内容。截图检查证明界面渲染，不证明云端模型或原生 Wayland 输入能力。

独立验收驱动 `scripts/validation/desktop_app_probe.py` 已验证双进程单实例的 `--show`、`--toggle`、`--cancel`、`--quit`，以及损坏配置保留原字节并以退出码 1 结束的无人值守模式。根评审结果保存在本地 `build/ui-root-lifecycle/result.json`；临时配置未写入用户真实设置。

## 生产悬浮窗焦点

先启动专用 Xvfb，再执行（禁止使用用户正在工作的显示器）：

```bash
uv run python scripts/validation/overlay_focus_probe.py --isolated-display :91
```

2026-10-12 实测通过。探针使用生产 `Overlay`，创建自己的可编辑目标，采样显示前、波形录音、圆点录音、转写、润色、注入、成功、失败、取消与隐藏后的焦点。10 次焦点窗口 ID 完全相同。两种样式均未改变目标焦点；该结果仅适用于所测隔离 X11 环境，不能扩展为原生 Wayland 保证。

## 实际录音到目标链路

独立验收代理使用 `scripts/validation/voice_workflow_probe.py` 验证生产 Session、Qt Recorder、ProviderClient、实际 AT-SPI 编辑目标和生产悬浮窗。云服务由本地可信 TLS 模拟器提供确定的 Unicode 响应，因此该验证可以覆盖真实音频采集、TLS 请求、处理时序与直接输入，不证明商业服务账户权限或识别准确率。2026-10-12 源码运行通过，结果见本地 `build/voice-source-acceptance.json`：三次真实麦克风 WAV 分别为 19,786 / 19,786 / 19,104 字节；一次成功精确输入 28 个 Unicode 码点，两次取消分别覆盖迟到回复与焦点离开后返回。统计中的润色 Token 为模拟器精确返回的 5 / 7 / 12；目标焦点保持，未产生音频文件。该结果不包含尚待重建的最终 AppImage。

原生 Wayland 自动输入、原生会话物理快捷键触发、真实云端模型请求及更多浏览器/终端输入，仍需独立实测；原生会话锁定期间不绕过锁屏。没有用户云端凭据时不宣称完成实际商业 API 验收。
