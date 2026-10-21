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

这些结果**确切排除了上述场景在输入阶段末尾一次性收到全部文字**。同时原 v0.6.0 的自有 VTE 也通过，故不能将「终端拒绝 XSendEvent」写成已复现的用户故障根因；35 字首末跨度也未显示明显提速。新 XTest 路径是兼容性改进，不能据此承诺所有应用或所有负载都逐字呈现。本轮四项沿用历史桌面助手的 simple IM 上下文，不能代替系统默认输入上下文中的实际应用验收。后续完整链路恢复当前 GNOME 环境中的实际 `QT_IM_MODULE` / `GTK_IM_MODULE` / `XMODIFIERS`，不通过修改目标输入上下文获得通过结果，也不调用系统输入法作为输出路径。

Xorg 新路径需要系统 `libXtst.so.6`；实际 Ubuntu 24.04 验证机只读查询确认安装 `libxtst6:amd64 2:1.2.3-1.1build1`。未将开发主机 Ubuntu 26 的系统库复制进包。缺库时连接失败且不会开始映射或按键发送。

### 实际 Session 与本地固定服务链路

第二份冻结清单 `ca8f549b4e47724f7a7326eb306b80138ba2b9cc54e4a2bc0663026449942d8a` 复用同一原 v0.6.0 包依赖，在上述真实 Xorg 桌面中使用 qasync 事件循环与生产 `Session`。合成 PCM 经过真实 Qwen 实时客户端连接本地 TLS WebSocket；最终确认文字再交给本地 HTTPS SSE 润色，35 字按 70 ms 间隔供给；生产工厂输出到独立 GTK TextView。未访问物理麦克风、用户凭据或真实供应商。

原执行 `85657` 自然退出 0。录音停止请求至首个发送字符 `215.297 ms`；任务开始至首字 `226.746 ms`，早于润色结束的 `2537.980 ms`。目标实际收到 35 字、34 个中间前缀，每次最多增加一字符，首末接收跨度 `2263.954 ms`；映射恢复、接收进程自然退出 0，诊断为空，WSS 收到预期 6400 字节且仅完成一次，ASR 最终内容核对正确。产品模块来源与依赖清单均验证通过。原始证据位于 `build/ubuntu24-perf-vm/output/ubuntu24-experience-source-r2/source-session-gtk-r1/result.json`，同级保存桌面身份、依赖审计和原始执行终态。

这证明该生产 Session / 本地协议 / 默认桌面上下文 / GTK 组合在润色仍进行时已逐字符输出，并非全部完成后批显。70 ms 供给决定了本轮大部分输出跨度；此结果不是实际云端转写耗时或用户物理麦克风识别率，也不能外推其他目标与负载。

### 前段等待与未验范围

源码审查未发现 `XGrabServer`。普通输入循环每字符都有异步等待；统计 `finished` 与性能结果在输入完成后才发出，不在每个字符上同步写统计。流式润色在首段到达后启动输出消费者，最终结果仅核对后缀；HTTP 转写和非流式润色仍须先等待最终结果。故须将「结束录音到首字」和「首字到末字」分别测量，当前直接工厂验证只覆盖后者，尚不足以解释用户等待发生在哪一段。

前表只覆盖生产键盘工厂到真实 GTK / VTE；随后完整 Session 场景补足了一个本地协议链路，但两者均不是新 AppImage 验收。实际 GNOME Text Editor、Files 可编辑框、Claude Code、codex-cli 与 GNOME 46 原生 Wayland 任意中文尚不能由此宣布通过。物理键、真实供应商负载、其他工具包与应用绘制合并行为均需独立证据。

### 实际 GNOME Text Editor 与默认桌面输入环境

补充使用系统真实 `gnome-text-editor --new-window` 打开本轮专用空文档，而非自制 GTK 控件。启动前确认无既有该应用进程，确认本次窗口 PID、激活窗口与实际空白编辑控件；保留 GNOME 进程 / 用户服务的真实输入环境（本轮 `GTK_IM_MODULE` 未设置、`QT_IM_MODULE=ibus`、`XMODIFIERS=@im=ibus`），不人为把目标应用切换为 simple/compose。InkEcho 正文仍由模拟键盘发送，不通过输入法或 AT-SPI 写入；AT-SPI 仅只读记录固定公开样本文字的逐字前缀。

| 实现与真实目标 | 最终正文 | 完整逐字前缀 | 首字至末字 | 字符间隔中位 / 最大 | 映射恢复 / 正常退出 |
|---|---|---|---:|---:|---|
| 原 v0.6.0，GNOME Text Editor | 未收到 | 无 | 无 | 无 | 是 / 0 |
| 修复源码，GNOME Text Editor | 21 字精确 | 1 至 21 全部，最大增长 1 字 | 942.320 ms | 47.969 / 52.288 ms | 是 / 0 |

原包在同一真实应用、桌面环境与观测器条件下报告按下 / 释放完成，但编辑器未收到正文；修复源码则逐字符接收，未发现非预期文字。两轮应用均正常退出、无强制终止；修复轮通过自有窗口的关闭 / 丢弃未保存内容导航退出，专用空文档不保存正文。这复现了一个实际 GTK 4 编辑器拒绝旧合成事件的场景，支持 Xorg 改用 XTest 的兼容性修复；不能外推到所有终端或所有用户程序。原始证据为 `build/ubuntu24-perf-vm/output/ubuntu24-experience-actual-apps-r3/{old-editor-r3,source-editor-r3}` 的 `observation.json`、`dispatch.json`、`terminal.json`，同级保存依赖审计与身份。

工具失败也保留：r1 因 GI 多接口同名方法解析错误，读回工具失败，不能判定产品；r2 修复接口后最终 21 字精确、持续出现前缀 2 至 21，但观测器在首次 AT-SPI 初始化完成前过早发布就绪，未观察首字，严格验收失败。r3 在发布就绪前完整初始化并缓存实际空白、已聚焦可编辑控件，记录基线及准备时间后才允许发送；没有修改产品等待时间，也没有放宽逐字链标准。r1/r2 目录完整保留，不作为通过结果。

Files 搜索栏、取消第八字以及新 AppImage 的相同真实应用验收待补；Claude Code / codex-cli / Node 在专用 VM 中未安装，未联网安装，仍明确未验。

## AppImage 直接运行图标

源码已统一 AppImage 根目录 desktop 文件、图标资源与 Qt 桌面 ID：`io.github.Creammmmm.InkEcho`，X11 的 `StartupWMClass=InkEcho` 保持与现有窗口一致。直接运行正常 AppImage 主进程时，在用户数据目录安全注册受管理入口及图标，无须先点安装集成；冷控制命令不会注册、不启用自启动、不覆盖无主管理或符号链接入口。图标原子写入完成后才发布 desktop，已一致时不重复重写，移动 AppImage 后仅更新自有入口路径。

针对性验证 `tests/test_integration.py tests/test_startup.py tests/test_packaging.py` 为 `29 passed in 1.57s`，涵盖正常主进程注册、冷控制边界、自启动缺省、非自有/符号链接保护及原子写顺序。真实 GNOME Shell 侧栏观察仍待新包；仅有包内图片或 Gio 可解析资源不等于侧栏已经匹配。

## 实际包与双系统边界

当前尚未在本报告记录新包双系统验收；源码级测试和复用旧包依赖运行冻结修复源码，不构成新 AppImage 通过。物理麦克风和真实云端识别率也不由生成音频外推。
