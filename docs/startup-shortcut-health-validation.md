# 启动快捷键健康检查回归验证（2026-10-21）

## 原因与修复

模型配置引导完成后，主 Agent 审查实际启动入口时发现：上一轮设置页精简删除了 `RecordingPage.check_shortcut()`，但 `__main__.run()` 仍在创建窗口、初始化会话后调用该方法。单独构造设置窗口的测试未经过这一启动分支，因而没有发现缺失方法；实际入口会抛出 `AttributeError` 并退出。

本次恢复该方法作为只读启动健康检查，调用既有 `GnomeShortcuts.status()`，不调用注册或修改接口，不恢复已删除的按钮。健康检查与注册共用 `shortcut_lock`；开始按键录入与注册任务推进 `shortcut_revision`，检查返回时再次确认修订及录入状态，避免迟到结果覆盖新录入或注册成功/失败提示。系统检查不可用时显示可行动的 GNOME 权限与重新录入提示，不显示后端异常细节。

注册操作取得同一把锁后，读取当时最新保存的快捷键作为回滚目标。因此两个注册排队时，第二次配置写入失败会恢复第一次已成功保存的绑定，而不是排队前的过时值。旧后端提示不再引用已删除的「保存并启用快捷键」按钮，改为点击「全局快捷键」重新按键录入、自动保存的操作。

产品修复准备版本为 `0.5.12`，三处版本元数据已按开发规范同步。本轮先前的 `0.5.11` AppImage 仅为候选，必须保留其失败/中止记录，不得部署；修复后须重新构建并重新执行同一 SHA 的双 Ubuntu 包验收，不能沿用旧候选包结果。

API 配置引导本身及其链接核实、离屏布局检查见[模型配置引导验证](provider-onboarding-validation.md)。本修复不改变引导、凭据存储或输入语义。

## 本地检查

运行：

```sh
.venv/bin/ruff check src/inkecho/ui/settings.py src/inkecho/platform/hotkeys.py tests/test_startup_shortcut_health.py
.venv/bin/ruff format --check src/inkecho/ui/settings.py src/inkecho/platform/hotkeys.py tests/test_startup_shortcut_health.py
.venv/bin/pytest -q tests/test_startup_shortcut_health.py tests/test_hotkeys.py tests/test_startup.py tests/test_workspace.py
```

实际结果：Ruff lint、三文件格式检查通过；上述测试 **47 项通过，耗时 2.84 秒**，原始执行会话自然返回退出码 0。受限沙箱内的线程唤醒不工作，初次受限测试等待被终止；最终结果来自允许线程唤醒的独立本地测试执行，不将环境挂起记作产品通过。

新增检查包含：

- 调用真实 `__main__.run()`，构造真实 `MainWindow` 及设置页面，执行启动健康检查，并经 `quit_after` 自然进入原有退出清理路径；验证状态检查恰好一次、没有注册快捷键、会话与单实例清理完成、UI 任务集合清空，以及临时配置 JSON 字节保持不变。这能捕获实际入口与页面方法不一致的问题，而不只检查方法名存在。
- 模拟健康检查仍在等待时开始新按键录入，再分别完成成功或失败注册，确认旧健康结果不覆盖新操作提示。
- 模拟系统状态检查不可用，确认有明确的重新录入/权限提示且不泄露异常内容、不写配置。
- 两次注册排队，第二次本地保存失败时确认系统绑定及保存配置恢复到第一次成功的值。

## 范围与限制

测试使用真实 Qt 窗口但运行于 **offscreen** 平台；录音设备枚举、系统输入后端初始化及 GNOME 快捷键状态/注册接口受控模拟，所有配置、统计与日志写入临时目录。没有读取或修改真实用户凭据，也没有写入真实 GNOME 快捷键或真实用户配置。

这验证真实应用入口与实际页面类之间的调用及退出流程，但**不是 AppImage/AppRun 实际启动验收**。实际包启动、FUSE、GNOME 会话、原生 Wayland / XWayland / Xorg、物理麦克风、物理快捷键和云端服务仍须在后续包验收报告各自记录；不能由本地模拟测试推断支持。
