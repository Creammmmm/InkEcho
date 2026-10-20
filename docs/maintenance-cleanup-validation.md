# 维护清理验证（2026-10-21）

## 第一部分：生产代码中的废弃界面与薄包装

本轮从当前入口、动态调用与全仓引用出发，删除无用或重复检查及废弃代码，同时保留实际行为与安全边界的保护。原工作树为 `main` 的 `0.6.1` 后继版本，独立维护分支为 `codex/check-cleanup`。第一组普通提交准备版本为 `0.6.2`，不创建 release，不替换现有安装包或用户实例。

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

## 第二部分：架构核对与合成配置迁移

只读审查覆盖 `src/inkecho` 全部 54 个 Python 模块及 9 个资源文件。AST 与全仓引用只是候选线索，还逐项核对动态调用和外部回调：

- `asr_streaming.ADAPTERS` 按固定允许列表动态加载实时协议，不因缺少静态 import 而删适配器。
- Qwen 的 `set_preview_callback()` 由 `Session` 的 `getattr` 入口调用；WebSocket `process_redirect()` 与 CookiePolicy `set_ok()` 为外部回调，分别阻止密钥随重定向传递与隐式会话 Cookie。
- 当前输出时的 X11 焦点判断与混合键盘后端选路不是旧录音目标追踪，保持不变；EOF/取消恢复、凭据文件边界与协议最终结果屏障均保留。
- 图标资源仍被安装与运行入口使用，旧受管理图标散列及配置字段仍有兼容用途，不按名称猜测删除。

`docs/architecture.md` 已按当前实现修正：去除开始录音捕获目标、AT-SPI 定向插入及系统凭据服务的旧描述，说明当前光标键盘语义、录音与授权并行、HTTP/实时协议及草稿最终屏障、混合键盘/guardian、五页工作台、配置目录明文凭据与实际 Ubuntu 会话/BMP 边界。没有借文档修订扩张支持范围。

生产 `config.DEFAULT_PROVIDERS` 只被测试与验证脚本消费。两份原有无密钥 `Provider` 字面值现迁至 `scripts/validation/synthetic_providers.py`，名称为 `SYNTHETIC_PROVIDERS`；11 个存活测试文件与 `performance_package_probe.py`、`ui_protocol_acceptance.py` 显式引用该夹具，pytest 路径加入验证脚本目录。夹具不进入生产 `inkecho` 包，也不改变新配置目录不预建平台的行为。独立冻结/暂存验证脚本时须一并带上该 helper，不得为方便导入而放回生产模块。真实 JSON 格式、已有用户记录与迁移边界未变。

本组对受影响的配置、UI、应用、实时预览与协议页面组运行一次检查，初轮 250 项通过、1 项失败：`test_model_configuration` 仍断言第一组已移除的隐藏 `page.timeout`。删除这条过时控件断言后，对同组重跑，原始会话 98371 自然退出 0，**251 项通过，7.88 秒**；真实设置页超时与保存竞争测试继续保留。Ruff lint、15 文件格式及差异检查通过。原始事实另存忽略目录 `build/maintenance-cleanup/synthetic-providers-validation.json`；仍属离屏 Qt、临时配置及本地模拟，不是桌面包或真实账户验收。

## 第三部分：退役工具、测试与现行驱动

清理前完整检查基线为 **2158 项通过、3 项跳过，66.66 秒**；测试目录为 80 个测试文件及 `conftest.py`。详细分层、保留与合并依据见 [检查项审计](check-audit.md)。此基线不是清理后最终通过结果。

经主 Agent 审查调用关系与替代路径，实际移除 53 个历史/重复验证脚本及 14 个配对测试文件，合计 67 条路径均列于[退役工具索引](retired-validation-tools.md)。索引固定到 `2c562eae0c313a32f7f972572f8bfc77a61709f6` 的原源码，历史报告与其真实结果不重写。此组数量不包括第一组删除的生产阶段零 `probe.py`。没有为了减少数量删除取消、凭据、协议、当前光标或按键/映射恢复等有效边界断言。

当前入口共用小型 `scripts/validation/desktop_preflight.py`，替代从旧实验脚本间接获取桌面就绪状态；新增 10 个受控测试案例，验证会话、身份及锁定状态的现有判断。锁屏状态读取失败时前置拒绝；logind 身份未核实时保持 `verified=false`，不扩张为完整桌面身份保证。迁移不自动启动录音或输入，也不把桌面尚未就绪当成产品不支持。

`desktop_app_probe.py` 按现行五页工作台做最小修复，新增两个驱动测试；不顺便新增产品功能。验证工具执行者的 focused 组为 **155 项通过，0.29 秒**。当前 pytest collection 为 **1832 项**，这只是收集结果，不是完整测试已通过。

主 Agent 已实际读取本轮源码驱动的 `/tmp/inkecho-cleanup-desktop-r2/result.json` 与原始终端：`kind=source`、`qt_platform=offscreen`，五张页面截图实得 1120×850；主进程自然退出 0，show/quit 单实例通信、冷控制命令退出 0 且配置不变、损坏配置退出 1 且原字节保留均通过。原始执行会话 86971 自然退出 0，终止信号列表为空。主 Agent 实际查看帮助页截图，显示执行时开发版本 `0.6.2`；之后 `0.6.3` 为维护报告后继版本，没有借截图声称已构建新安装包。第一次 r1 受限 IPC 初始化失败、primary exit 1 的事实保留，未当作产品功能失败或通过；r2 在允许本地 IPC 的环境完成。

上述驱动结果不表示实际 Wayland 输入、物理设备、云端或 AppImage 验收；它只说明源码入口、当前页面和隔离配置生命周期。没有访问剪贴板或修改真实配置。pytest 全局导入路径最终仅为 `src` 与 `scripts/validation`，删除已无必要的 `scripts/feasibility` 全局路径；显式可行性工具仍可按其自身入口运行。

## 最终检查状态

主 Agent 已审查本组精确删除集合、动态入口与关键行为测试保留，接受 preflight 迁移、合成夹具及架构文档修订。普通维护后继版本准备为 `0.6.3`；没有创建新 release、重打包、更新本机安装或重启用户实例。

主 Agent 实际核对的 Python 文件规模如下，计数包含各目录内的 Python 辅助文件，不把它等同于测试案例数：

| 范围 | 清理前 | 当前 |
| --- | ---: | ---: |
| 生产源码 | 54 | 53 |
| tests（含 conftest） | 81 | 69 |
| feasibility | 41 | 21 |
| validation | 65 | 35 |

最终分组提交完成、工作树干净后，由主 Agent 以本报告为证据对精确 HEAD 执行完整本地 workflow，最终测试结果与耗时以生成的精确提交验证记录为准。此处尚不填写清理后全套通过或加速结论，1832 项收集及各 focused 结果不代替完整检查。
