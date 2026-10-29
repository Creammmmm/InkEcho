# Fcitx 组词保护与原生插件受限资格

2026-10-30。原生插件 SHA-256：
`acd896aae8ab38ecca2685c0dd8639f2910e841176eadccf59ee4943b158c4de`。
本记录整合同一插件的 SDK、真实桌面及官方拼音验证；没有构建或验收包含此修复的新 AppImage，
不替代项目规范第 24.3 节的同包双系统发布门。

## 行为与资格范围

新客户端要求运行中的桥支持 `Begin3(token, 3)`。旧桥缺少保护协议时，在创建 capability
或发送正文之前硬停；不降级调用 Begin/Begin2，也不据此转交键盘或 GNOME 输入桥。
文件已更新不表示 Fcitx 已加载新版，须通过明确的更新与输入法重启操作加载。

每个字符提交前检查公开 InputPanel 和 pending events。已有预编辑、候选、辅助面板或
待处理客户端事件时不调用 commitString，不重置组合、不切换输入法；本任务终止。
清除组合不会自动恢复被拒绝的任务或重放尾文。取消、过期、owner 变化与部分发送保护保持。
这些检查不能证明应用接收成功，也不能发现输入法或客户端未向公开 API 暴露的私有状态。

正式 staging 只放行上述 SHA 和既有两个 x86_64 ABI 组合：Ubuntu 24.04/Fcitx 5.1.7、
Ubuntu 26.04/Fcitx 5.1.19。它表示允许显式安装这一受限验证的插件，不表示所有会话、应用
或输入引擎都已兼容。原先 `3a3c80…` 仅进入 retired 清理列表，不再被新安装资格接受；
旧库继续保留，修改过的或非本应用描述文件仍不删除。新版客户端对仍加载旧库的服务硬停。

| 实际环境 | 同一插件的实际结果 | 记录 |
| --- | --- | --- |
| Ubuntu 24.04.5，Fcitx SDK/Core 5.1.7 | 24 项真实私有 Core/协议检查通过；server/client preedit、aux、queued event 零提交且状态保留，legacy/status、重复序号、owner/cancel、Python 部分尾文不恢复 | [SDK 记录](../experiments/fcitx-preedit-sdk-ubuntu24/REPORT.md) |
| Ubuntu 24.04.5 X11，GTK3/Fcitx Pinyin 5.1.3，LibIME 1.1.5 | 默认 auto 正文、真实 ni 预编辑长度 2、保护零次提交、Space 后原组合变为你、首字取消均通过 | [真实拼音](../experiments/fcitx-pinyin-preedit-ubuntu24-20261030/README.md) |
| Ubuntu 26.04.1 Wayland 会话，GTK3 XWayland/Fcitx Pinyin 5.1.12，LibIME 1.1.14 | 虚拟机键盘对照及真实 ni 长度 2，通过保护零提交、Space→你、首字取消；actor/daemon 退出 0，临时 hints 恢复 | [26 后续实测](../experiments/fcitx-pinyin-preedit-ubuntu26-followup-20261030/README.md) |

真实桌面 staging 当时使用明确的测试专用 SHA 放行，正式 allowlist 在这些检查与独立复核后
才更新。实验中的测试放行不等于当时已经正式合格；这些实际结果也不是新 AppImage 结果。

## 失败与资源记录

[早期双系统桌面记录](../experiments/fcitx-preedit-addon-desktop-20261030/REPORT.md)
保留了旧 26 backing 链只读故障、Unicode 触发未建立真实组合等失败。
[26 拼音首次尝试](../experiments/fcitx-pinyin-preedit-ubuntu26-20261030/README.md)
保留了 XTest 不能建立预编辑、严格在正文前停止的未通过样本。
后续持久 XTest 普通 a 对照仍无接收事件并导致窗口失活；截图显示未批准的 GNOME Remote
Desktop 授权窗口。只取消隔离客机的该请求，改用该虚拟机的 QMP 成对虚拟硬件键建立真实
拼音，产品正文仍走未修改的 auto Fcitx 路径。不能据此推断每个历史失败的唯一根因。

两系统最终均正常关机，私有进程退出并恢复临时输入法 hints。26 后续客机在有界内存盘运行，
正常退出前完整归档并全流解压校验；父盘、依赖包、所有原始记录与完整归档保留。
低配额时的归档停止及索引无损归档也如实记录，不把不完整归档当成功清理。

## 隔离候选本地检查

整合候选针对 Fcitx 协议、硬停/取消/过期、owner、路由、capability、安装与 staging、
旧描述清理和打包 pin/inventory 的 314 项检查通过（3.88 秒）。其中真实插件经过 squashfs
封装/解包后，不使用测试 SHA 覆盖，分别按两个合格 ABI 组合成功 staging；这只是小型资源
payload 测试，不是完整 AppImage 构建或实际客机验收。Ruff check 和 format 检查通过，
404 个维护文件格式正确；历史 experiments 按项目配置排除。

首次受限执行环境在 framework detector 的 asyncio 线程检查处停滞，已保留中断日志；
在正常线程/进程能力的隔离候选中重跑得到上述完整结果，未跳过失败用例。
上述隔离候选检查不生成推送前完整 workflow receipt；最终源码检查须在正式干净提交上运行，
其结果以该提交的本地验证记录为准。本次没有构建新 AppImage、更新稳定入口或发布。

复现维护检查：在候选根目录使用项目虚拟环境运行 `ruff check .`、`ruff format --check .`，
以及 `pytest -q tests/test_fcitx*.py tests/test_output_router.py tests/test_framework_detection.py`。
真实桌面的依赖清单、fixture、原始日志位置及未验范围分别见上表；不得用单元测试替代实测。

仍未验证：该插件在原生 Wayland GTK、其他输入引擎、浏览器/Electron及隐藏客户端组合状态的
新保护行为；其他会话/版本组合也没有因此新增支持。必须保留模拟键盘路径与用户选择，
不得将输入法桥资格解释为通用桌面授权或应用接收确认。
