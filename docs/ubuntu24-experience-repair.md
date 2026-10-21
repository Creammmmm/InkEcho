# Ubuntu 24.04 体验修复验证

本报告记录针对 v0.6.0 用户反馈的修复；各项源码检查、实际桌面检查和实际包检查分别记录，不能互相代替。

## 录音启动与真实收音提示

### 发现与修复

`Recorder` 原本已在收到首个完整 16 位采样后发出 `capturing`，并立即读取 `QAudioSource.start()` 返回时已有的首批缓冲；实时连接建立前的 PCM 也已有有界队列，未发现该路径主动丢弃开头音频。可是 `Overlay.show_state("recording")` 原本不论是否收到采样，都立即启动动画。因此用户可在麦克风仍初始化时看到波形并开始讲话，视觉提示早于实际收音。此次修复让启动阶段保留静态「麦克风正在启动，请稍候」提示，首个有效采样到达后才启动动画并显示「正在聆听」。已排队的动画回调也不能提前推进相位，三种显示风格遵循相同规则。Wayland 显示宿主沿用同一控件，不额外捕获焦点。

另一个确定的前置阻塞点是实时会话构造函数同步加载系统 TLS 信任库，该构造发生在麦克风启动前。现将信任库准备移到实时连接 `start()` 的后台线程，保留原有连接超时、取消、过期、CA 校验和主机名校验；麦克风无需等待该磁盘操作。连接就绪前的首块 PCM 仍由原有有界队列保存。取消后，即使后台信任库线程稍后完成，也不得启动网络连接或发送旧音频。没有把麦克风改为常开，也不保证设备实际启动前的声音可以恢复。

### 可重复源码验证

在 Ubuntu 26.04.1 开发主机运行：

```sh
.venv/bin/python -m pytest -q tests/test_audio.py tests/test_realtime.py tests/test_qwen_vad.py tests/test_application.py tests/test_overlay_host.py tests/test_ui.py
```

结果：`322 passed, 2 skipped in 7.93s`。两项跳过均为需要显式物理麦克风授权的测试。其后加强「取消后后台线程实际完成也不连接」断言，单独重跑 `tests/test_realtime.py -k cold_tls`：`2 passed, 118 deselected in 0.13s`。格式和静态检查通过。

共享基类的签名 ASR、Step、DashScope、能力验证及实时任务链路另跑：`tests/test_signed_asr.py tests/test_step_realtime.py tests/test_dashscope_realtime.py tests/test_provider_capability.py tests/test_application_realtime.py tests/test_application_early_realtime.py`，结果 `129 passed in 8.35s`。这些使用本地固定服务，未调用用户云端账户。

新增的两种 TLS 场景以受事件控制的工作线程模拟缓慢信任库读取：构造会话不触发读取；事件循环继续运行；连接前首块 PCM 完整留在队列；正常完成仍校验证书；取消会清空队列，线程返回后也不能连接。它们不连接真实供应商，不读取用户密钥。界面三种风格均检查首采样前定时器停止、排队 tick 不推进、采样后动画启动以及结束后停止。

同进程 12 次本地小测中，信任库读取首次 `0.626 ms`、中位 `0.089 ms`，新构造函数中位 `0.010 ms`。这仅说明本机该操作很快；不能据此将用户较长卡顿归因于 TLS，也不能宣称已经测得实际语音识别延迟改善。

### 实际音频服务验证状态

已有合成音频探针可在实际桌面上创建唯一命名的临时虚拟源，将 100 ms 首标记置于生成音频开头，测量启动到首帧、播放到首信号以及标记完整性；不访问物理麦克风，不更改默认源，并清理自己创建的音频模块：

```sh
.venv/bin/python scripts/validation/audio_onset_probe.py
```

本轮开发主机未安装 `pactl` 和 `paplay`，探针安全退出 1，未创建音频节点，不能算作通过。实际 Ubuntu 24.04 音频服务、物理麦克风开头识别率、真实云端结果，以及最终 AppImage 的双系统结果须在后续验收中独立记录；上述源码回归没有覆盖这些范围。

随后在实际 Ubuntu 24.04.5 / GNOME Shell 46.0 / Xorg 的专用 KVM 桌面上，使用冻结修复源码及原 v0.6.0 包的依赖运行同一合成首标记探针。冻结清单 SHA-256 为 `05fcf39cfd24eed7d97f074376922fb8850a620537e4ce0d8c7e8addc6e977a7`；复用依赖的包清单 SHA-256 为 `6e74fed8ef8e4e35e9ea73063226cfa50cbfdacd27bee6156cdc0deb6a07e629`。原执行进程自然退出 0，未发送强制终止信号：

| 轮次 | 启动到首帧 | 播放到首信号 | 标记非零采样数 | 动画开始时已收字节数 |
|---|---:|---:|---:|---:|
| 1 | 22.596 ms | 72.412 ms | 1601 | 624 |
| 2 | 22.706 ms | 84.329 ms | 1601 | 624 |
| 3 | 8.697 ms | 71.383 ms | 1601 | 624 |

三轮初始化动画均停止，每轮仅一次首采样信号；实际收到完整采样后动画才启动，生成的 100 ms 开头标记均完整经过采集路径。默认音频源保持不变，创建的虚拟模块已清理。原始证据位于 `build/ubuntu24-perf-vm/output/ubuntu24-audio-source-r1/result.json` 与 `terminal.json`。这是**冻结修复源码 + 原包依赖**的实际音频服务检查，不是新 AppImage 验收，也没有覆盖物理麦克风或真实云端识别率。

## Ubuntu 24.04 当前光标与逐字符输出

### 路径审查与源码修复

原 Xorg / XWayland 后端使用 `XSendEvent`；其事件带合成标志，目标程序可以忽略此类事件。此次仅在明确的 `XDG_SESSION_TYPE=x11` 会话采用独立 `XTest` 后端，事件发往发送当时的焦点，仍逐字符让出事件循环。XWayland 的客户端映射与合成器物理键盘映射不同，不能把其私有键码直接用于全局 XTest，因此保留现有 Wayland / XWayland 路径。新后端借用空键码，保留映射所有权检查与恢复；检测物理按键或危险修饰状态时停止，不模拟释放用户按键，不回退剪贴板或输入法。常见 Num Lock 状态保留。映射检查与修改仍非全局原子事务，不能声称消除了其他程序同时改布局的所有竞态。

GNOME 46 的实际接口已有 `ConnectToEIS` 和键码 / keysym 通知，却没有 `SetKeymap` / `KeymapCapabilities`。官方 Mutter 46 的 `notify_keyval_in_impl()` 只查当前映射中的现有 keysym，找不到即退出；直接发送任意中文 keysym 并不是可行修复。[Mutter 46 实现](https://raw.githubusercontent.com/GNOME/mutter/46.0/src/backends/native/meta-virtual-input-device-native.c)。新预检先核对接口，缺失时返回固定 `unsupported_compositor` 并关闭临时会话，用户看到明确的 Ubuntu 24.04 / GNOME 46 登录「Ubuntu on Xorg」提示；程序不自动切换或修改系统。GNOME 50 原有原生路径保持不变。

相关源码回归：`tests/test_keyboard.py tests/test_wayland_keyboard.py tests/test_hybrid_keyboard.py tests/test_wayland_worker.py`，`231 passed in 4.95s`，格式与静态检查通过。覆盖路由隔离、Num Lock、物理修饰拒绝、按下释放、已有取消恢复，以及缺接口在读取不存在属性前正常关闭、支持接口继续授权。测试不代表真实应用通过。

### 实际目标逐字符接收

实际 Ubuntu 24.04.5 / GNOME Shell 46.0 / Xorg 专用 KVM 桌面运行冻结源码；源清单 SHA-256 为 `9e3e95de2a1f7d6ca73b567d9324cdebe6f236c180d34753ec7f579ccead6ed1`，原 v0.6.0 包依赖清单 SHA-256 为 `6e74fed8ef8e4e35e9ea73063226cfa50cbfdacd27bee6156cdc0deb6a07e629`。每次校验原依赖文件与符号链接、当前导入产品模块来源，接收窗口 PID、当前激活与文本焦点均核实为本次自有目标。GTK 以文本缓冲变更记录时间，VTE 的真实 PTY 子进程在 raw 模式按每次读取记录 UTF-8 字节与时间，不执行 shell。

| 实现与目标 | 收到字符 / 中间前缀 | 首字至末字 | 每次接收最多一字符 | 按下 / 释放 | 映射恢复 / 自然退出 |
|---|---:|---:|---|---:|---|
| 原 v0.6.0，VTE | 35 / 34 | 1532.193 ms | 是 | 35 / 35 | 是 / 0 |
| 修复源码，GTK TextView | 35 / 34 | 1528.630 ms | 是 | 35 / 35 | 是 / 0 |
| 修复源码，VTE | 35 / 34 | 1535.515 ms | 是 | 35 / 35 | 是 / 0 |
| 修复源码，VTE 第八字取消 | 8 / 7 | 320.023 ms | 是 | 8 / 8 | 是 / 0 |

每项接收内容均逐码点精确，取消后额外观察 700 ms 无尾部；所有原始执行自然退出，未强制终止。原始逐字时间戳与内容位于 `build/ubuntu24-perf-vm/output/ubuntu24-experience-source-r1/{old-vte-r1,source-gtk-r1,source-vte-r1,source-vte-cancel8-r1}/result.json`，同目录保留接收记录、执行终态、桌面身份和依赖审计。

这些结果**确切排除了上述场景在输入阶段末尾一次性收到全部文字**。同时原 v0.6.0 的自有 VTE 也通过，故不能将「终端拒绝 XSendEvent」写成已复现的用户故障根因；35 字首末跨度也未显示明显提速。新 XTest 路径是兼容性改进，不能据此承诺所有应用或所有负载都逐字呈现。本轮四项沿用历史桌面助手的 simple IM 上下文，不能代替系统默认输入上下文中的实际应用验收。随后源码 Session 链路仅恢复了 GNOME 进程中的 `QT_IM_MODULE` / `GTK_IM_MODULE` / `XMODIFIERS`，没有完整合并用户服务 activation 环境，不能称为完整恢复默认桌面输入上下文；再后面的真实编辑器与 CLI 另行合并 GNOME 进程及 activation 环境。正文均不调用系统输入法作为输出路径。

Xorg 新路径需要系统 `libXtst.so.6`；实际 Ubuntu 24.04 验证机只读查询确认安装 `libxtst6:amd64 2:1.2.3-1.1build1`。未将开发主机 Ubuntu 26 的系统库复制进包。缺库时连接失败且不会开始映射或按键发送。

### 实际 Session 与本地固定服务链路

第二份冻结清单 `ca8f549b4e47724f7a7326eb306b80138ba2b9cc54e4a2bc0663026449942d8a` 复用同一原 v0.6.0 包依赖，在上述真实 Xorg 桌面中使用 qasync 事件循环与生产 `Session`。合成 PCM 经过真实 Qwen 实时客户端连接本地 TLS WebSocket；最终确认文字再交给本地 HTTPS SSE 润色，35 字按 70 ms 间隔供给；生产工厂输出到独立 GTK TextView。未访问物理麦克风、用户凭据或真实供应商。

原执行 `85657` 自然退出 0。录音停止请求至首个发送字符 `215.297 ms`；任务开始至首字 `226.746 ms`，早于润色结束的 `2537.980 ms`。目标实际收到 35 字、34 个中间前缀，每次最多增加一字符，首末接收跨度 `2263.954 ms`；映射恢复、接收进程自然退出 0，诊断为空，WSS 收到预期 6400 字节且仅完成一次，ASR 最终内容核对正确。产品模块来源与依赖清单均验证通过。原始证据位于 `build/ubuntu24-perf-vm/output/ubuntu24-experience-source-r2/source-session-gtk-r1/result.json`，同级保存桌面身份、依赖审计和原始执行终态。

这证明该生产 Session / 本地协议 / GNOME 进程来源的输入上下文 / GTK 组合在润色仍进行时已逐字符输出，并非全部完成后批显。此轮没有完整恢复 activation 环境，默认桌面输入环境的实际应用证据须看后续独立记录。70 ms 供给决定了本轮大部分输出跨度；此结果不是实际云端转写耗时或用户物理麦克风识别率，也不能外推其他目标与负载。

### 前段等待与未验范围

源码审查未发现 `XGrabServer`。普通输入循环每字符都有异步等待；统计 `finished` 与性能结果在输入完成后才发出，不在每个字符上同步写统计。流式润色在首段到达后启动输出消费者，最终结果仅核对后缀；HTTP 转写和非流式润色仍须先等待最终结果。故须将「结束录音到首字」和「首字到末字」分别测量，当前直接工厂验证只覆盖后者，尚不足以解释用户等待发生在哪一段。

前表只覆盖生产键盘工厂到真实 GTK / VTE；随后完整 Session 场景补足了一个本地协议链路，但两者均不是新 AppImage 验收。该表本身不覆盖实际 GNOME Text Editor、Files 可编辑框、Claude Code、codex-cli 与 GNOME 46 原生 Wayland 任意中文；后续实际编辑器与新包证据见下文，不由这张源码表代替。物理键、真实供应商负载、其他工具包与应用绘制合并行为均需独立证据。

### 实际 GNOME Text Editor 与默认桌面输入环境

补充使用系统真实 `gnome-text-editor --new-window` 打开本轮专用空文档，而非自制 GTK 控件。启动前确认无既有该应用进程，确认本次窗口 PID、激活窗口与实际空白编辑控件；保留 GNOME 进程 / 用户服务的真实输入环境（本轮 `GTK_IM_MODULE` 未设置、`QT_IM_MODULE=ibus`、`XMODIFIERS=@im=ibus`），不人为把目标应用切换为 simple/compose。InkEcho 正文仍由模拟键盘发送，不通过输入法或 AT-SPI 写入；AT-SPI 仅只读记录固定公开样本文字的逐字前缀。

| 实现与真实目标 | 最终正文 | 完整逐字前缀 | 首字至末字 | 字符间隔中位 / 最大 | 映射恢复 / 正常退出 |
|---|---|---|---:|---:|---|
| 原 v0.6.0，GNOME Text Editor | 未收到 | 无 | 无 | 无 | 是 / 0 |
| 修复源码，GNOME Text Editor | 21 字精确 | 1 至 21 全部，最大增长 1 字 | 942.320 ms | 47.969 / 52.288 ms | 是 / 0 |

原包在同一真实应用、桌面环境与观测器条件下报告按下 / 释放完成，但编辑器未收到正文；修复源码则逐字符接收，未发现非预期文字。两轮应用均正常退出、无强制终止；修复轮通过自有窗口的关闭 / 丢弃未保存内容导航退出，专用空文档不保存正文。这复现了一个实际 GTK 4 编辑器拒绝旧合成事件的场景，支持 Xorg 改用 XTest 的兼容性修复；不能外推到所有终端或所有用户程序。原始证据为 `build/ubuntu24-perf-vm/output/ubuntu24-experience-actual-apps-r3/{old-editor-r3,source-editor-r3}` 的 `observation.json`、`dispatch.json`、`terminal.json`，同级保存依赖审计与身份。

工具失败也保留：r1 因 GI 多接口同名方法解析错误，读回工具失败，不能判定产品；r2 修复接口后最终 21 字精确、持续出现前缀 2 至 21，但观测器在首次 AT-SPI 初始化完成前过早发布就绪，未观察首字，严格验收失败。r3 在发布就绪前完整初始化并缓存实际空白、已聚焦可编辑控件，记录基线及准备时间后才允许发送；没有修改产品等待时间，也没有放宽逐字链标准。r1/r2 目录完整保留，不作为通过结果。

源码阶段的上述记录不覆盖 Files、新包与真实 CLI。最初专用 VM 库存盘点时 Claude Code / codex-cli / Node 未安装；后续固定离线 CLI 工具及新包验证在下文单独记录，不能把这一时点的库存状态当作最终验收结论。

## AppImage 直接运行图标

源码已统一 AppImage 根目录 desktop 文件、图标资源与 Qt 桌面 ID：`io.github.Creammmmm.InkEcho`，X11 声明沿用 `StartupWMClass=InkEcho`，实际匹配仍以侧栏观测为准。直接运行正常 AppImage 主进程时，在用户数据目录安全注册受管理入口及图标，无须先点安装集成；冷控制命令不会注册、不启用自启动、不覆盖无主管理或符号链接入口。图标原子写入完成后才发布 desktop，已一致时不重复重写，移动 AppImage 后仅更新自有入口路径。

针对性验证 `tests/test_integration.py tests/test_startup.py tests/test_packaging.py` 为 `29 passed in 1.57s`，涵盖正常主进程注册、冷控制边界、自启动缺省、非自有/符号链接保护及原子写顺序。随后在实际 Ubuntu 24.04 / GNOME 46 Xorg，直接运行同一候选 AppImage runtime（guest 使用 extract-and-run，非 FUSE 声明），配置和日志私有，但 desktop / 图标注册到实际 Shell 可见的用户数据目录。根 Agent 审查 `build/ubuntu24-perf-vm/output/ubuntu24-experience-dock-r4/dock.png`：左侧 Dock 为单一 InkEcho 蓝色品牌图标并带运行点，托盘也使用同一图标，图标反馈项实际通过。

真实自有窗口 PID 8741 的 `WM_CLASS="InkEcho", "InkEcho"`、`_GTK_APPLICATION_ID` 与 `_KDE_NET_WM_DESKTOP_FILE` 均为预期 InkEcho 身份，实际 desktop 的 `StartupWMClass=InkEcho` 和 Icon 与之匹配。Gio 找到真实用户 desktop，GTK 解析出对应 256px 图标；Shell 只读 Introspect 被正常权限限制，未启用 unsafe Eval，以实际截图验证侧栏。原运行自然退出 0，无信号；`terminal.json` 记录 1 个 desktop 与 8 个图标路径全部精确恢复，无未恢复路径。QMP 原始截图成功后，由系统 Python 离线转换已存在的 PPM；首次转换环境缺 PIL 的工具退出不属于产品问题，没有重新截图覆盖原帧。

## 候选 0.6.7 的同包双系统验收记录（交付门未完成）

产品提交 `4121ce4bac59a0ae59cd0ff83d8ab8d9597f0ce7`，AppImage `InkEcho-0.6.7-x86_64.AppImage`，SHA-256 `1dd85e0551850bb4a766639dd8111407b9e5f5c29a812eb93c1915b3acf18f28`。候选冻结清单 SHA-256 `b264c7aa519bf2cc8f5f5aaadbb0e258c591367dd6c42f10be94b7d3b442ceff`，包库存 SHA-256 `6bbb1172072b66b553bf5308d0d674e3c738b9b933f12cfe18e043b69093ca06`。以下包验证使用该同一镜像及包内产品代码，不把此前源码叠加结果当作包结果。

| 实际系统与会话 | 已完成的必要包检查 | 范围 |
|---|---|---|
| Ubuntu 24.04，实际 GNOME 46 / Xorg 专用 KVM | 实际入口与五页 / IPC 退出边界；本地协议链路；Qwen 服务端 VAD 最终结果屏障；实际音频服务首采样动画门；实际 GNOME Text Editor 正常及取消第八字 | 入口经 AppImage runtime extract-and-run；与 host 正式 FUSE 挂载分开记录。真实 GTK / VTE 源码验证不替代此列包验证。 |
| Ubuntu 26.04，实际 GNOME / Wayland host | 正式 FUSE 挂载入口与五页；同包本地协议；服务端 VAD；首采样动画；原生 / XWayland 切换正常与中途取消 | 所有原执行自然返回 0；不包含真实云端语音准确率与物理麦克风标记实验。 |

24 包原始门证据位于 `build/ubuntu24-perf-vm/output/inkecho-candidate-0.6.7-r1`，其中首次 protocol 使用过时的 UI 隐藏字段检查而失败，该结果保留；修订后的真实包链路通过证据为 `build/ubuntu24-perf-vm/output/inkecho-candidate-0.6.7-r2/gates/protocol/{result.json,tool-result.json,terminal.json,origins.json}`（原执行 11470 自然 0）。仅替换过时 UI 字段观察为真实 Session.settings 与 ConfigStore 状态核对，SSE 时序、取消、实际协议链路未删减；26 包原始证据位于 `build/ubuntu24-experience/host-package-r1/{fuse-entry,protocol,vad,audio,mixed-normal,mixed-cancel}`。根 Agent 在最终接受前检查原始 JSON、进程自然退出与关键截图，不只依据工具总结。

### 新包在真实 GNOME Text Editor 中逐字接收

本轮启动真实 `gnome-text-editor --new-window` 打开专用空文档，先确认独占应用 PID、激活窗口与实际空白可编辑焦点，再从新包调用生产键盘工厂；产品模块来源硬限定新包 `packages`。AT-SPI 仅只读观察，不用于写入。目标保留真实 GNOME 输入环境，不通过禁用目标已有输入法插件制造兼容性。没有向云端提交固定测试文字，也未读取真实密钥。

| 真实应用场景 | 最终文字与实际前缀 | 首字至末字 | 相邻字符中位 / 最大 |
|---|---|---:|---:|
| GNOME Text Editor 正常输出 | 21 字精确，1 至 21 每个前缀均读回 | 952.560 ms | 48.194 / 54.978 ms |
| GNOME Text Editor 第八字取消 | 8 字精确，1 至 8 每个前缀均读回，后续观察无尾部 | 324.325 ms | 47.454 / 52.510 ms |

两项最大前缀增长均为一字符，无非预期正文；按下 / 释放平衡、映射恢复、应用自然退出 0、无强杀。观测器先完整初始化并读取空白聚焦基线后才发布就绪。原始证据：`build/ubuntu24-perf-vm/output/ubuntu24-experience-package-apps-r1/{package-editor-normal-r1,package-editor-cancel8-r1}` 的 `observation.json`、`dispatch.json`、`terminal.json` 与同级身份 / 库存审计。这确切排除了上述实际场景末尾一次性输入全部文字，不代表所有应用的绘制节奏一致，也没有据此宣称每秒字符数明显提高。

### 真实 CLI 的显示节奏须与发送区分

后续采用独立固定 CLI 二进制、私有配置与本地禁联网模型入口，在根 Agent 确认真实输入编辑状态后输入固定公开样本，不按 Enter 提交、不调用云端推理、不读取用户 CLI 配置或凭据。最初库存盘点中的「CLI 未安装」只描述当时状态；后续专用测试二进制验证应以此段实际记录为准。

Codex CLI v0.160.0 的真实 TUI 完整显示过 21 字样本，记录到前缀长度 `1, 2, 4, 6, 8, 10, 11, 13, 16, 18, 20, 21`，首末可见跨度约 1060.537 ms。UI 约 100 ms 合并绘制，因而未通过「可见前缀必须每次只增加一字符」的严格门；这既不是末尾一次性输入，也不能写成每字均独立绘制通过。生产发送保持逐键，21 次按下 / 21 次释放，按键间隔中位 48.408 ms / 最大 52.032 ms；TUI 渲染间隔中位约 100.751 ms。按下 / 释放与映射清理通过；接收编辑内容已完整出现，但最终关闭过程会清空编辑区，不能只用关闭后的最终屏幕文本判断之前没有输入。原始 `state.json` 保存 `sample_complete_ever=true` 与逐段快照，`rendered.json` 是后续关闭状态，两者时间语义不同。

分析 JSON 为 `build/ubuntu24-experience/codex-tui-r5-analysis.json`；即刻抓取的 `prefix-21.png` 仍是旧帧，不能当作全文出现证据，应读带时间的实际屏幕文本快照。Codex 原始证据：`build/ubuntu24-perf-vm/output/cli-tui-r5/codex-package-r5`。CLI 子进程 exit 0，GTK / VTE owner 自然退出 0（同级 `codex-package-r5-owner-terminal.json`）；外层严格前缀控制器原执行 `40124` 返回 1，因为不是 1 至 21 的完整逐字渲染链。必须分别记录产品接收、子进程退出与严格验收失败，不能把它们合写为整项自然 0 通过。没有强杀。

Claude Code 2.1.258 也在完成正常首次引导后的真实离线对话编辑状态收到完整 21 字，前缀长度 `1, 3, 5, 7, 9, 12, 14, 16, 18, 20, 21`，可见首字至完整显示 1008.946 ms。生产 21 次按下 / 21 次释放，间隔中位 47.844 ms / 最大 52.350 ms；CLI 渲染中位 100.783 ms，同样合并约两至三字，严格每帧一字未通过，但已明确渐进显示且完整接收。未按 Enter 发送正文，无云请求；来源见 `build/ubuntu24-experience/claude-tui-r5-analysis.json`。

Claude 原包装控制器 `36619` 达到 180 秒期限后返回 1，记录 `still_running=true`，没有强杀；后续仍在同一自有会话继续正常引导 / 编辑。捕获控制文件非原子改写又使观察定时器遇到瞬时空 JSON，抛出 `JSONDecodeError` 后定时器停止，故自动最终截图 / 退出监控不可靠；这是夹具问题，原失败记录保留。修正私有控制文件后，根 Agent 以身份核验的正常 Ctrl+C 关闭该实例（关闭助手 `9382` 自然 0）。之后独立 pidfd 观察器原执行 `8130` 自然 0，确认 CLI exit 0 与 GTK owner 结束；这不是原父控制器完成了 wait。`build/ubuntu24-perf-vm/output/cli-tui-r5/claude-package-r5/later-natural-exit-observation.json` 记录两进程退出、无强制信号，并逐字节核对原包装器超时终态未变。最终截图在退出时才补抓，不作为 21 字全文截图；完整输入的证据为此前带时间的实际 TUI 文本前缀，不能用早于全文渲染的即时 `prefix-21.png` 或只看分析总结代替。

### 同包 Xorg 输出中切换光标与取消

同一候选包在两个独占 GTK 接收窗口间完成受控焦点切换。正常场景在 A 收到前 8 字后切至 B，A 精确 8 字、B 精确 27 字；取消场景同样先向 A 输出 8 字，再切 B，累计第 14 字取消，B 精确 6 字，之后无剩余正文。两窗口每次接收均只增加一字符，正常按下 / 释放为 35 / 35，取消为 14 / 14；临时映射恢复，两个接收进程均自然退出 0，无强制信号。

原始证据为 `build/ubuntu24-perf-vm/output/ubuntu24-package-xorg-switch-r2/{normal-r2,cancel14-r2}/result.json`，同级 `normal-r2-terminal.json`、`cancel14-r2-terminal.json` 记录原 owner wait 完成且返回 0；包内模块来源及同 SHA 均在结果中固定。这是受控 GTK 接收器的当前光标语义与取消证明，不能代替 Files 的真实控件绘制结果。

### 旧候选 Files 延迟与后续修复；Dock 已通过

Files 搜索 / 重命名旧夹具 r3/r4/r5 没有证明目标编辑焦点，未发送识别正文，不当作产品失败或通过。r5 当时未先验证异步选择，原因只能保留为假说；r6 明确验证文件已选择后，F2 仍未出现重命名框，所以不能将「未等选择」定为已定位原因。只读 Gio 查询表明该文件 `can-rename/can-write/can-delete=TRUE`、uid 1000、挂载可写，不能归因文件权限。

r7 在 guest 本地专用目录通过正常上下文菜单进入真实重命名框，核实自有窗口、可编辑焦点后由候选包发送固定 21 字。独立 QMP 连续画面显示首字之后停顿，再出现全文；因此**候选 0.6.7 没有通过 Files 渐进呈现要求**，不能凭发送器计数或最终全文判为成功。AT-SPI 的该 Entry 文本接口始终报告 0，故不能伪造其逐字文本事件；应看 `build/ubuntu24-perf-vm/output/files-f2-diagnostic-r7/candidate-input-r1` 中的帧图、`dispatch.json` 与 `terminal.json`。退出时 Esc 取消重命名，自有文件未改；发送助手 0，应用进程消失，但该轮正常退出辅助命令返回 255、原包装器超时仍保留，不能把所有控制器状态合成一次完整 0 通过。

r8 的同一实际控件对照中，普通 ASCII 持续呈现；候选包混合中文样本首次与再次发送均表现为首字后全文。独立 Pillow 画面与 QMP 结果一致，排除了只因 QMP 抓帧或单次中文暖场造成的解释。证据为 `build/ubuntu24-perf-vm/output/files-ascii-warm-r8/{result.json,contact-sheet.png}` 及两份中文 `dispatch.json`。这一对照尚不足以断言 GTK 或 IBus 内部根因。

r9 进一步固定为相同的「中」重复 21 次及原按键节拍：每字重写同一键码映射的对照有 22 次映射写入（含恢复），仍首字后全文；仅首次映射、后续复用同一键码的实验只有 2 次写入（含恢复），帧图持续出现约 7 / 14 / 19 / 21 字。两轮发送耗时分别 1099.636 / 1037.900 ms，按下 / 释放平衡、映射恢复、应用退出 0、自有文件未改。原始证据为 `build/ubuntu24-perf-vm/output/files-repeat-r9/{repeat-rewrite-dispatch.json,repeat-once-dispatch.json,result.json,contact-sheet.png}`。这支持**频繁映射更新与该 Files 控件延后绘制相关**，并不证明 GTK / IBus 内部具体机制；仅映射一次也只适用于相同字符，不是任意混合 Unicode 的产品修复。该轮对照本身没有形成已验产品修复，不能返写候选 0.6.7 已通过；后续正式源码方案及其实际验证见下节。

### 后续正式源码修复：Xorg 相邻双行合并更新

针对上述尚未通过的 Files 场景，生产 `_XTestDriver` 增加可选的批次准备：只借用原本为空、未列入修饰键表的相邻两条键码行，每批最多容纳两个不同字符，通过一次 `XChangeKeyboardMapping(..., count=2)` 同时更新。没有合法相邻空行时明确拒绝，不回退到仍会批显的单行方案。已有符号在当前批次或后续流片段中直接复用；换行仍使用真实 Return，不为换行或空闲输出会话改表。新批次最后只用一行时，另一行保留本次已拥有的值。原 100 ms 首次映射等待及后续逐键等待均未增加。

实现只扩展 Xorg 的 `_XTestDriver` 和现有逐字循环中的可选准备调用，纯 `XSendEvent` / XWayland 路径不变。写入前登记两行 pending 意图，读回后保存实际规范化快照；取消、过期或部分写入 / 读回失败仍逐行清理所有明确属于本任务的行。外部替换行不覆盖，且仍尝试恢复另一条自有行。焦点在每字发送时重新读取；已尝试按下的键仍在 `finally` 中释放，不重放不确定输入。

源码文件 `src/inkecho/platform/keyboard.py` 的本轮冻结 SHA-256 为 `8c81ec8ba2e6519016c94ae687ca48647fc2d89417cea89ad8a554c513b47690`。定向回归 `tests/test_keyboard.py tests/test_xorg_pair.py` 为 `74 passed in 0.11s`；混合路由、Wayland、worker 与 streaming 相关四组为 `202 passed in 4.98s`，合计 276 项通过，Ruff 检查和格式检查通过。新增覆盖单次 count=2 请求、符号复用、无合法 pair、modifier 排除、规范化读回、第二行读回失败、外部冲突、跨片段 / Return、首等待取消、按下后取消、deadline 及资源恢复。

随后在实际 Ubuntu 24.04.5 / GNOME 46 / Xorg 的真实 Files 重命名框中，直接运行该正式源码的生产工厂，未再替换 `map` / `prepare`；冻结清单 SHA-256 为 `b08d7bc51640207c1512c3534a7fb39f9f1fa593c7d81f869225317e7d1464d6`，源码 keyboard SHA 与上文一致，仅运行依赖复用原候选 0.6.7 包。根 Agent 审阅实际帧图并核对以下结果：

| 正式源码实际场景 | 正文与接收画面 | 发送耗时 | 清理与退出 |
|---|---|---:|---|
| r20，mixed 21 字；原执行 74498 | 帧图连续增长；文件名逐码点精确并恢复 | 1067.199 ms | 按下 / 释放平衡，完整映射恢复，应用自然 0 |
| r21，long 36 字；原执行 19447 | 跨越多批仍连续增长；文件名逐码点精确并恢复 | 1755.305 ms | 按下 / 释放平衡，完整映射恢复，应用自然 0 |
| r22，累计第 8 字取消；原执行 84090 | 仅「中文输入验证 c」8 字，额外观察 700 ms 无尾部 | 462.843 ms | 按下 / 释放平衡，完整映射恢复，应用自然 0 |

三项原执行均自然返回 0，未强制终止；原始帧图、发送事件、文件名精确读回及恢复证据在 `build/ubuntu24-perf-vm/output/{files-production-r20,files-production-r21,files-production-r22}` 的 `result.json`、对应 `production-*-dispatch.json` 与帧图中。Files 的 AT-SPI Entry 文本接口仍返回 0，故只把实际帧图作为渐进呈现证据，不伪造完整逐字 AT-SPI 事件链。

同一正式源码另在真实 GNOME Text Editor 回归，原执行 `99567` 自然 0：21 字精确、1 至 21 完整前缀、最大增长 1 字，无额外正文；首字至末字 932.495 ms，字符间隔中位 47.330 ms / 最大 49.264 ms，映射恢复、按键平衡、应用自然 0。原始证据为 `build/ubuntu24-perf-vm/output/editor-production-r23/case/{terminal.json,observation.json,dispatch.json}`。

上述已验证**正式源码修复**，但**不是原候选 0.6.7 已包含此修复**，也不构成新 AppImage 验收。三处开发元数据准备递增至 0.6.8；此前 r7 至 r16 的失败与实验对照不覆盖、不删除。新包仍须以新版本与新 SHA 完成双系统实际验收。

Dock r1/r3 的工具未给 X11 只读搜索传入真实图形环境，继承 SSH 无 DISPLAY，所以没有找到窗口；不是产品无窗口或 WM_CLASS 不匹配证据。r4 修正后已有真实侧栏截图及同一自有窗口的实际身份匹配通过，见上节。候选不修改用户 host 的 Dock 设置、不重启 Shell、不启用 unsafe Eval；guest 仅暂时使用 Shell 实际可见的数据目录，正常退出后精确恢复自己管理的 9 个文件。

### 构建 0.6.8 前的历史边界记录

以下为源码验证结束、新包构建之前的状态；其中「新包待验」由后文最终 0.6.8 同 SHA 实测结果取代，旧候选及旧失败证据仍保留。

Ubuntu 24.04 / GNOME 46 原生 Wayland 缺少本实现所需的任意 Unicode 键盘映射接口；此轮没有将其冒充已支持。已验证的 24 输入会话为 Xorg，产品对缺失接口提供明确切换提示，不静默回退剪贴板或系统输入法。Ubuntu 26.04 原生 Wayland 与 XWayland 保留其各自同包验证范围。

物理麦克风开头与真实供应商识别准确率未用生成音频替代宣称；已有生成标记实验证明实际 Recorder 开头标记完整、动画在首次采样后才启动。网络 / 云端转写 / 非流式润色仍可能占据结束录音至首字的等待，不能把输入阶段逐字证明写成消除了整条云端延迟。Dock r4 已实际通过，Files 的正式源码修复也已在上述目标场景验证，但包含该修复的新包仍待验；CLI 不能承诺每字单独一帧绘制。候选 0.6.7 的 SHA 不变，不能把后续源码结果写成旧候选已全部修复；新包及其他未验会话须独立记录，所有剩余必要项通过前不更新稳定入口、不发布新 release。

## 最终候选 0.6.8 的双系统实际包验收

本节是上述「新包待验」之后的结果，不改写旧候选 0.6.7 或旧实验的失败。最终构建来自产品提交 `5eca696fd12fe4889441cf36eab927e6f27a908c`，包为 `InkEcho-0.6.8-x86_64.AppImage`，SHA-256 为 `066ff4aed54df7da93c4fe2315b0ec4df0ed328ef83b900dc2ff1414a9389fd7`。Ubuntu 24.04 与 26.04 均使用这个包，包内 inventory SHA-256 为 `2cfc75001c23c48f94abbb1ae12b3456efad8c66244fcd5995378acd2e7b09a8`；候选清单为 `7d34e5ce4ddae8b994651634f807364070bded0e33bf6f575391c2865012c488`。本次报告提交按规范只递增三处开发元数据至 0.6.9，**没有重建或把已验的 0.6.8 包改标为 0.6.9**。

### Ubuntu 24.04.5 / GNOME 46 / Xorg

实际包完成入口、配置 / 本地协议、VAD、采音动画四门：原执行 `45215`（提取）、`53517`（入口）、`70387`（协议）、`97942`（VAD）、`95234`（音频）均自然返回 0。包内实际 Recorder 的三轮首帧为 12.943 / 18.892 / 16.040 ms，标记非零样本分别为 **1600 / 1601 / 1601**，动画均在已收到 624 bytes 后才开始；不能将第一轮写成 1601，也不能用合成标记替代物理麦克风或真实供应商准确率验收。

| 真实目标 / 场景 | 实际结果 | 原执行自然终态 |
|---|---|---|
| Files 重命名框，混合 21 字 | 画面渐进；发送耗时 1064.546 ms；文件名逐码点精确并恢复 | 63693 = 0 |
| Files，长 36 字跨映射批次 | 画面渐进；发送耗时 1748.248 ms；文件名精确并恢复 | 54047 = 0 |
| Files，第 8 字取消 | 发送耗时 458.454 ms；第 8 字取消后再观察 700 ms，无尾部 | 53935 = 0 |
| GNOME Text Editor，21 字 | 完整 1 至 21 前缀、最大增长 1；首末字 925.521 ms，间隔中位 46.842 / 最大 50.790 ms | 54275 = 0 |
| 输出时切换两个 Xorg 光标，正常 / 取消 | A8 / B27；取消 A8 / B6；逐字精确，取消后无正文 | 18784 / 71892 = 0 |
| AppImage 实际启动与 GNOME Dock 图标 | 实际侧栏图标与应用身份一致；暂管的 9 个资源精确恢复 | 72566 = 0 |

上述输入均按下 / 释放平衡、映射恢复、接收应用自然退出 0。Files 的 AT-SPI Text 仍报告 0，因此渐进呈现依据独立实际帧图及最终文件名，不虚构每字 AT-SPI 文本链。Dock r1 的 `69916 = 1` 是夹具仍绑定旧 SHA，启动前即拒绝；r2 仅修候选绑定，保留 r1，不作为产品失败或静默覆盖。

真实 Codex 0.160.0 与 Claude Code 2.1.258 也使用同一包的生产键盘工厂，固定 21 字输入完整、渐进，均非首字后一次性全文。Codex 观察前缀为 `1,2,4,5,6,8,9,10,11,13,15,16,17,18,19,20,21`，首末呈现 900.769 ms，发送 1039.961 ms；Claude 为 `1,2,3,4,7,8,9,10,12,14,15,16,17,18,19,20,21`，首末呈现 965.306 ms，发送 1034.836 ms。二者各 21 次按下 / 释放、映射恢复、完整文本、观察器清洁，CLI 自然退出 0；原 start 控制器分别 `53046 = 0`、`24584 = 0`。**渐进完整门通过，但每次重绘严格只增一字门仍为 false**（最大增长分别 2 / 3），不可将终端自身合帧写成每字独立绘制已通过。

CLI 在专用本地 ext4 私有 HOME / cwd 中正常引导，只复制固定二进制，不读取用户账号配置；隔离网络空间只有 DOWN 的 lo，使用固定假 key，没有提交正文 Enter、联网识别或权限绕过。Claude 首次两次正常 Ctrl+C 仅清空输入未退出；保留原 owner，由单独审阅且校验身份的正常关闭助手再发送两次 Ctrl+C，之后原 CLI 自然退出 0，无强制信号。新工具以原子控制文件及持续观察修复旧 r5 的夹具异常，旧失败记录不覆盖。

完整索引、原执行终态、CLI 原始路径及图片在 `build/ubuntu24-experience/package-0.6.8-ubuntu24-progress.json`；CLI 原始证据为 `build/ubuntu24-perf-vm/output/cli-tui-0.6.8-r1/{codex-package-r1,claude-package-r1}`。验收结束后以正常 guest `systemctl poweroff` 关闭 VM，SSH 返回 0，容器 `Exited (0)`、非 OOM、无强杀。该环境实际验证的是 Xorg；guest 通过提取运行包，**不宣称 guest FUSE 直接挂载已验证，也不宣称 GNOME 46 原生 Wayland 已支持**。

### Ubuntu 26.04.1 / GNOME 50 / 原生 Wayland 与 XWayland

同 SHA 包完成入口 / 直接运行、协议、VAD、音频及混合后端正常输出检查。 原执行自然终态为 FUSE 直接运行 `15664 = 0`、协议 `94495 = 0`、VAD `21558 = 0`、音频 `40115 = 0`、正常混合路由 `44320 = 0`，最终未增强取消门 `17502 = 0`。三轮实际合成采音首帧为 18.517 / 23.403 / 15.750 ms，动画在采样达到 628 bytes 后开始。原生 Wayland 与 XWayland 的受控切换维持生产工厂、原映射 / 取消逻辑；这些检查不等于所有真实应用、物理麦克风和云端响应时间均相同。

必须保留本轮取消门的偶发异常：`host-package-0.6.8-r1` 至 `r4` 的 mixed-cancel 原始执行均失败。r1 / r2 在 native 成功 4 / 5 次按键后，测试专用 guard 拒绝后续按下；r3 的拒绝快照证实窗口 `document_focused=true`，但输入框 `field_focused=false`，快照仅 19.543 ms，身份正确，排除了过期或 owner 改变。r4 的只读 DOM 事件显示中文正常送入 TEXTAREA，随后输入框 blur / focusout 至 BODY，后续公开样本键进入 BODY；没有 Tab、F6 或修饰键异常。**这是未定位的实际输入框焦点丢失风险，尚不能归因为纯夹具，也没有改产品重新聚焦或等待来掩盖它。**

进一步对照完整保留：`host-idle-0.6.8-r5/idle` 的无输入一秒观察原执行 `61830 = 0`，没有 blur / 鼠标 / 按键，字段焦点保持，只证明本次空闲启动对照无异常。新增被动事件观测的取消门 `host-package-0.6.8-r5` 原执行 `61163 = 0`：native 10 字，再 XWayland 4 字时取消，14 次按下 / 释放平衡、映射恢复、无 guard 拒绝、两个接收应用退出 0，无 pointer 事件；观测开销可能影响时序，不能据此断定根因已修。

最后使用**未增加上述事件观测的原始门**在 `host-package-0.6.8-r6` 重验，原执行 `17502 = 0`：native 10 / XWayland 4 各精确，14 次按下 / 释放平衡、两套映射恢复、guard 拒绝 0、两个目标退出 0、错误列表为空。因此同包正常与取消路径均有完整通过实据，但 r1 至 r4 的偶发输入框失焦也同时保留；不能宣称该 26.04 风险已经修复、或双系统所有体感完全一致。

入口、音频的实际门结果在对应 `result.json`，协议及混合路由的实际门结果在 `tool-result.json`；VAD 同时保留 `tool-result.json` 与外层 `result.json`。混合路由工具以 `SystemExit(0)` 正常结束时未落外层 `result.json`，依据实际 `tool-result.json` 与原执行 `terminal.json`，不将缺失文件当作已生成。原始 host 包门证据为 `build/ubuntu24-experience/host-package-0.6.8-r{1,2,3,4,5,6}` 对应模式的 `tool-result.json`、`terminal.json`、来源记录及诊断；r3 有 `native-guard-rejection.json`，r4 有 `rows.dom_diagnostics`。idle 对照独立记录在上列 idle 路径，不能替代输入门。所有失败自然终态和原始证据均保留，没有降低 250 ms guard 门限、改按键节拍、强制 refocus 或更改产品焦点语义。

### 最终交付范围

0.6.8 候选已经在上述两个系统对同一 SHA 完成实际包检查；Ubuntu 24.04 的 Xorg 真实编辑器、Files 和两个真实 CLI 有完整接收与渐进输出证据，旧 Files 首字后全文问题在该范围内已修复。26.04 偶发 field blur 尚未定位，应继续调查；不承诺每个 CLI 重绘单独一字。真实录音 → 云 ASR → 目标应用的完整端到端本轮未测，物理麦克风开头与识别准确率未测，不能将合成录音或本地协议门冒充这些结果。当前稳定旧版本入口未替换，没有发布 release；本轮提供的是保留上述限制的候选验证结果。
