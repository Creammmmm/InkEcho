# 维护清理验证（2026-10-21）

## 第一部分：生产代码中的废弃界面与薄包装

本轮从已发布功能的当前入口、动态调用与全仓引用出发清理死代码，不以减少测试数量为目标。原工作树为 `main` 的 `0.6.1` 后继版本，独立维护分支为 `codex/check-cleanup`。第一组普通提交准备版本为 `0.6.2`，不创建 release，不替换现有安装包或用户实例。

实际删除与简化：

- `ProviderPage` 已移除按钮留下的 `delete_key()`、`capability()` 方法；删除隐藏且已无业务消费者的请求超时、启用润色、失败回退和流式润色控件，以及只服务这些控件的信号/加载同步。真实设置仍由设置页维护。
- 删除 `AppearancePage` 未使用的预览回调参数与隐藏托盘勾选框，同步简化 `SettingsPage` / `MainWindow` 参数链；删除 `StatisticsPage` 未读取的日志参数。配置中的兼容字段不删除。
- 删除 `ProviderClient.check_connection()` 与 `Connection` 返回类型这层薄包装，相关测试直接验证 `models()` 的列表结果、GET 路径与请求行为。模型发现仍不等于模型能力验证；底层实际能力测试保留。
- 删除无当前产品、打包、脚本或 pyproject 入口的阶段零 `src/inkecho/probe.py`，不复制为新的重复工具；历史源码继续由 Git 保留。

以下实际路径保持：隐藏的请求参数与实时地址仍承载合法保存配置及协议同步；`provider_capability`、`Session.sample_audio()`、底层模型/能力验证、所有实时协议适配器、动态回调、凭据原子写/权限/符号链接拒绝、输出时当前焦点判断、取消与过期屏障均未删除。没有访问系统密钥环、云端账户或真实用户配置。

### 测试调整与本地结果

只移除针对已删除能力按钮的转发、隐藏控件自身行为及过时隐藏字段参数分支测试。三项协议/服务地址/采样率前置检查保留，改从真实「保存配置」路径触发，仍验证在外部访问之前拒绝非法配置且不更改采样率。

保存竞争测试不降级：在凭据保存等待期间，从真实 `SettingsPage` 并发修改启用润色、流式润色、失败回退；保留新表单不被覆盖、凭据输入及时清空、原配置选择及三项用户偏好不被迟到保存覆盖的全部原断言。模型发现测试直接使用 `models()`，保留模型过滤、错误与认证边界。

运行：

```sh
.venv/bin/ruff check src/inkecho/providers.py src/inkecho/ui/information.py src/inkecho/ui/providers.py src/inkecho/ui/settings.py src/inkecho/ui/window.py src/inkecho/ui/workspace.py tests/test_providers.py tests/test_ui.py
.venv/bin/ruff format --check src/inkecho/providers.py src/inkecho/ui/information.py src/inkecho/ui/providers.py src/inkecho/ui/settings.py src/inkecho/ui/window.py src/inkecho/ui/workspace.py tests/test_providers.py tests/test_ui.py
.venv/bin/pytest -q tests/test_ui.py tests/test_providers.py tests/test_workspace.py tests/test_startup_shortcut_health.py tests/test_provider_guidance.py tests/test_ui_protocol_acceptance.py tests/test_model_style_layout.py
```

实际结果：原始测试会话 88533 自然退出 0，**261 项通过，12.85 秒**；Ruff lint、八文件格式检查及 `git diff --check` 通过。主 Agent 已逐文件审查本组 diff，并接受上述结果。

这些是离屏 Qt、临时配置、本地 HTTP 模拟与受控系统后端检查。运行环境允许本地测试服务与线程唤醒，不代表调用真实云端、修改真实 GNOME 快捷键或实际 AppImage/桌面验收。没有录制物理麦克风、发送用户窗口输入、替换安装包或重启用户实例；不能由本轮测试扩展平台支持声明。

## 后续审核与最终检查

验证工具和其对应测试的保留/删除审核仍在进行，具体实施范围由主 Agent 审查证据后划定。`DEFAULT_PROVIDERS` 暂保留，未将测试用合成配置迁移为本轮附带改动；诊断入口存在的底层能力不因普通 UI 按钮移除而删除。

每个后续组须分别记录实际修改、保留的安全边界与本地功能结果。最终提交完成、工作树干净后，再以本报告为证据对精确 HEAD 执行完整本地 workflow；本节尚不声称最终全套通过，focused 结果不代替完整检查。
