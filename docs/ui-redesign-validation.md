# 设置页面重构验证记录

## 范围与当前状态

本记录对应设置入口整合、概览 / 模型配置 / 风格 / 设置 / 帮助导航、模型配置表单及 RAM 实时预览的开发验收。当前为源码验证记录，尚不能据此声称已经完成新 AppImage 的 Ubuntu 24.04 与 26.04 实际包验收或正式发布。

完整工作区测试、实际桌面页面截图和会话信息由主 Agent 在验收后补充；以下仅记录已经执行的结果。

## RAM 实时预览与最终正文隔离

Qwen 实时协议的 `conversation.item.input_audio_transcription.text` 使用 `text + stash` 作为可替换快照，只经 `Session.preview(str)` 交给悬浮界面。草稿不写磁盘、日志、统计，不触发润色或模拟键盘；最终正文仍来自 validated completed，成功仍需原有 session.finished 屏障。普通 HTTP 转写不产生伪实时正文。

预览合计限制 100000 字符；非字符串或超限草稿忽略。completed 后拒绝新草稿。Session 通过 epoch、task ID、原任务对象和上下文一致性隔离取消 / 替换后的迟到回调；开始录音、空闲、取消、成功和失败清空预览。非 Qwen 实时适配器没有新增 partial 支持声明。

复现：

```sh
.venv/bin/python -m pytest -q tests/test_realtime.py tests/test_realtime_preview.py tests/test_billing_updates.py
.venv/bin/ruff check src/inkecho/app.py src/inkecho/realtime.py src/inkecho/billing.py src/inkecho/updates.py tests/test_realtime_preview.py tests/test_billing_updates.py
```

2026-10-20 实际结果：**138 passed，1.44s**；上述 Ruff 检查通过。WSS 使用本地 TLS 回环、合成 PCM 与测试凭据；没有使用真实麦克风、用户密钥或真实云端调用。验证覆盖：可替换草稿、草稿不成为 final、无效 / 超限草稿不破坏 final、completed 后迟到草稿、取消与替换任务隔离、普通 HTTP 无伪实时，以及既有 WSS 最终完成屏障。

## 余额与更新查询

余额只在显式刷新时请求官方 DeepSeek `GET https://api.deepseek.com/user/balance`，凭据由调用方提供，不自行读取配置；未知平台明确不支持查询，不生成虚构余额。界面调用方还需核验当前配置使用官方地址，防止自定义平台密钥送到其他平台。错误信息不包含响应正文、异常详情或认证字段。

更新检查只读取本仓库 GitHub latest stable release，按项目稳定 X.Y.Z 比较；只接受同仓 HTTPS release 地址及精确匹配版本 / 文件名的 AppImage 地址，不自动下载、执行或安装。异步取消继续向上传播。

上述 138 项中包含余额 / 更新 14 项 mock 测试。未将 mock 成功当作真实账户余额或实际远端更新检查成功。

## 官方协议依据

- [Qwen-ASR-Realtime 服务端事件](https://docs.modelstudio.console.alibabacloud.com/en/model-studio/qwen-asr-realtime-server-events)：text 与 stash 合并为当前预览，completed.transcript 为最终文本。
- [DeepSeek 查询余额](https://api-docs.deepseek.com/api/get-user-balance/)：官方只读余额端点、余额币种及可用性字段。
- [GitHub 获取最新 Release](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)：本仓库 latest stable release 查询。

本地 OpenLESS 仅作只读调查，未找到可复用的余额查询实现；未复制其 AGPL 源码。

## 待补充验收

- 完整源码检查与最终提交验证记录。
- 当前桌面会话中的五个页面、托盘关闭行为、应用图标分组及悬浮样式实际验证。
- 如后续打包：同一版本、同一 SHA-256 AppImage 在双 Ubuntu 的实际包验收记录。

## 官方控制台链接与有符号余额补验

`console_for_provider` 只根据已知 adapter 与 HTTPS 官方 API hostname 返回固定控制台链接，不从用户可控地址拼接控制台链接；不认识的主机、网关或不匹配的适配器返回空链接。以下是本次只读核对的官方来源：

- DeepSeek：[官方 API 开放平台入口](https://www.deepseek.com/platform/)、[余额接口](https://api-docs.deepseek.com/api/get-user-balance/)；固定控制台 `https://platform.deepseek.com/usage`。
- 百炼 / Qwen：[阿里云官方百炼控制台](https://bailian.console.aliyun.com/us-east-1)；固定入口 `https://bailian.console.aliyun.com/`。
- OpenAI：[官方 API 平台](https://platform.openai.com/)、[官方用量与费用说明](https://help.openai.com/en/articles/10478918-reviewing-api-usage-and-costs)；固定用量入口 `https://platform.openai.com/usage`。
- SiliconFlow：[官方 Dify 接入说明](https://docs.siliconflow.cn/docs/usercases/use-siliconcloud-in-dify)，其中给出 `https://cloud.siliconflow.cn/account/ak`；固定控制台入口 `https://cloud.siliconflow.cn/`。
- Step：[官方开放平台](https://platform.stepfun.com/)，其中提供 `https://api.stepfun.com/v1` 示例；固定控制台入口 `https://platform.stepfun.com/`。
- Groq：[官方 Factory Droid 接入说明](https://console.groq.com/docs/coding-with-groq/factory-droid)，其中提供官方 API 地址及 `https://console.groq.com/keys`；固定控制台入口 `https://console.groq.com/`。

DeepSeek 官方余额 schema 将 total / granted / topped_up 定义为字符串，并未给出非负数约束。因此本实现接受所有有限有符号 Decimal，不擅自拒绝负余额；仍拒绝 NaN、Infinity 和非数字。这是兼容 schema 的行为，未据此声称真实账户必定可能欠费。新增 mock 用例显示 `is_available=false` 且总余额 `-1.20` 时完整返回，不隐藏为查询失败。

2026-10-20 单独重跑 `tests/test_billing_updates.py`：**29 passed，0.09s**，对应两个模块的 Ruff 检查通过；此处为新增补验，前述 138 项记录仍为当时的真实运行结果。没有读取真实账户、发送真实余额请求或验证登录后的控制台页面。

## 用户需求逐项实现与迁移

| 用户要求 | 当前实现与验证 |
|---|---|
| 设置不再显示 Python 独立图标 | 保留原有单实例 IPC；启动时统一 Qt application name、全局 icon、desktop ID；XWayland 原生 WM_CLASS 与 desktop StartupWMClass 都是 InkEcho，原生 Wayland app_id 与正式 desktop 文件 basename 一致。实际证据见下；未把属性一致冒充各桌面的 Dock 视觉验收。 |
| 五个左侧入口 | 仅概览 / 模型配置 / 风格 / 设置 / 帮助五页；子编辑器使用明确命名，不保留隐藏旧九页。 |
| 字数、时长、次数、七日图 | 本地数值统计三卡、成功失败取消与 Token；最近七天按本地日期补零，显示每日录音次数；不保存识别历史。finished 写入统计后以及从托盘打开时立即刷新，不覆盖模型编辑草稿。 |
| 概览选择配置、计费状态 | 语音 / 润色配置独立选择；DeepSeek 官方 openai adapter + 精确官方 Base URL 才能显式读取 key 请求余额。切模型、禁润色、配置 / 凭据修改时丢弃旧结果；缺 key 的单项失败不阻断其他项。未知余额不估造；六个平台显示已核官方控制台。 |
| 合并模型页、去预填默认 | 一个模型页下分语音 / 润色；新目录无预建阿里或 DeepSeek 文件，无预填显示名或默认平台。首次须完成名称、URL、模型、认证信息并保存；旧配置、隐藏 JSON 参数、实时地址和凭据不删除。 |
| 非供应商措辞、过滤协议、隐藏高级字段 | 用户界面使用模型配置 / 服务平台。仅显示 adapter 支持的转写方式；未选平台时方式禁用。JSON、可选实时地址和旧超时控件隐藏；超时统一到设置，旧表单不回写过时的超时或润色开关。 |
| 关闭润色灰显 | 概览润色选择、整个润色编辑器、设置中的润色超时 / 流式开关 / 失败回退均实际 disabled 并灰显；模板仍可离线编辑，云端预览按钮禁用。 |
| 风格模板与自定义 | 四个内置模板：忠实整理、社交聊天、编程智能体、正式邮件。内置只读资源受保护，编辑另存用户副本；新建、复制、保存、删除与选择自定义保留。 |
| 设置集中、Siri 风格预览 | 录音 / 快捷键、外观 / 悬浮、输入兼容、数据 / 日志、启动 / 桌面集成集中于设置；可选 Siri 灵感光谱、波形、呼吸圆点。Siri 仅显示 RAM 草稿，不提前发送到目标应用，最终屏障不变。 |
| 帮助版本和检查更新 | 直接显示运行版本；显式点击才查询本仓库 latest 正式版，只读、不自动下载 / 安装。 |
| 去退出按钮、关闭到托盘 | 主窗口不再有退出按钮；有托盘则关闭隐藏，无托盘则保持可恢复最小化窗口。托盘退出与 --quit 保留正常资源清理入口。 |

新目录与旧目录区分：`ConfigStore.initialize()` 不创建默认模型，但已有 provider / credentials / Prompt 文件保持原样。旧测试和性能诊断需要合成平台时显式 seed，不通过全局测试默认值掩盖空安装。未读取用户真实凭据，不自动迁移系统密钥环。

## 源码界面与桌面身份实际观察

2026-10-20，本机 Ubuntu 26.04 源码验证；全部使用 `build/` 下独立配置、数据、统计与缓存目录，未录音、未请求真实模型或真实余额，也未向任何应用发送正文。

- `build/ui-redesign-source-r3/pages/page-01.png` 至 `page-05.png`：首次五页 offscreen 启动成功，原始进程正常退出 0。后续发现紧凑性与初始校验提示问题，保留原图。
- `build/ui-redesign-source-r4/pages/page-01.png` 至 `page-05.png`：收敛后五页 offscreen 实图，显示概览首屏选择 / 余额、三指标卡，模型页正常首次引导、无重复子标题、隐藏 JSON / 实时 URL，设置润色关闭态灰显。offscreen 不证明桌面置顶或焦点行为。
- `build/ui-redesign-visuals-r1/`：七张合成数值 / 文字图片。`overview-week.png` 为七天 3 / 8 / 2 / 6 / 9 / 4 / 7 次的实际绘制；`polish-disabled.png` 与 `polish-enabled.png` 为润色编辑页两态；`social-style.png` 为社交模板；`siri-preview.png` 为合成文字光谱预览，`siri-cancelled.png` 为清空后取消态。此处草稿是固定测试文本，不是真实语音识别结果。
- `build/ui-redesign-identity-r1/result.json`：原生 Wayland 自有源进程 PID 24796，五页截图成功，最终 wait 0；仅从该进程 WAYLAND_DEBUG 的 `set_app_id` 提取正值 `io.github.Creammmmm.InkEcho`。同一私有 config 的第二个 `--show` PID 24896 返回 0，原始主进程仍存活，证明复用 IPC。
- 同一 identity r1 的 XCB 首次源启动 wait -6，缺 libxcb-cursor 等依赖；失败日志保留，未安装系统库。后续 r2 已能启动，但观察工具 xdotool 缺失导致 owner 失败，未将该次算作完整身份通过。
- `build/ui-redesign-identity-r3/result.json`：仅为该任务私有 LD_LIBRARY_PATH 从旧已验 0.4.0 包复制五个缺失的 XCB 库（cursor / icccm / image / keysyms / render-util），其余仍用本机源环境。私有包装器从实际 MainWindow.winId 记录自有窗口 ID 33554439，读取该 ID 的属性：`WM_CLASS = "InkEcho", "InkEcho"`、`_NET_WM_PID = 28710`、图标属性存在；第二次 --show PID 28763 返回 0，原进程存活，最终 wait 0。未查询其他应用窗口标题、未激活其他窗口、未安装系统依赖。

源身份匹配修复了 Python 默认身份来源；GNOME / 其他桌面 Dock 的实际图标合并外观仍需新包实际验收时观察，不能从属性自动推导。源码 XCB 使用借用依赖不是新 AppImage XWayland 验收，也不是 Ubuntu 24.04 结果。

## 本地测试补充

- 配置 / 模型 / Qt 协议定向批次：128 passed（含原 72 项 UI），8.46s。
- 排除 test_ui 的完整批次：1928 passed，3 skipped，59.94s。此处为当时文件状态，后续补了统计自动刷新等用例，最终干净提交检查另行记录。
- 新工作台用例：10 passed，1.05s；包含空安装五页、润色禁用、超时统一、七天补零、无托盘关闭可恢复、余额金额与网关隔离、缺 key 安全错误、任务结束自动刷新和恢复窗口不覆盖模型草稿。

本机 sandbox 的本地 asyncio / socket 限制曾使异步测试挂起；正常停止各自测试进程后，在允许本地回环的执行环境完成上述批次。未更改生产异步逻辑绕过限制。

最终定向批次（当前未提交源码）：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/pytest \
  tests/test_ui.py tests/test_workspace.py tests/test_model_configuration.py \
  tests/test_realtime_preview.py tests/test_billing_updates.py -q --disable-warnings
```

实际 **121 passed，8.76s**；原始日志 `build/ui-redesign-final-targeted.txt`。最终 `ruff check .`、`ruff format --check .`（335 files）及 `git diff --check` 均通过。润色关闭态主按钮追加独立 disabled ID 样式，避免蓝白 primary 规则覆盖灰显。

剩余边界：以上为源码验证，未完成当前新 AppImage 的同 SHA 双系统验收；未测试真实余额账户、真实云端识别、物理麦克风 / 快捷键，以及新 Siri 悬浮在实际目标应用上的无抢焦点 / 置顶 / 点击穿透。手动升级检查协议为 mock 验证，未自动下载安装。实际源身份与五页截图已完成，不将其重复标成包验收。

审查补验：缺凭据路径使用实际 `security.CredentialError` 类型（继承 RuntimeError），界面逐配置与外围明确捕获并显示安全错误，不让「正在刷新」残留；取消仍单独传播。修复后 `tests/test_workspace.py` **10 passed，1.07s**，两文件 Ruff 通过。原先 fake ValueError 用例已替换，避免掩盖异常类型边界。

最终余额状态补验：官方 `is_available` True / False 分别显示「账户可用」/「账户当前不可用」，不推断欠费原因；参数化界面用例覆盖两态及币种 / 金额。`tests/test_workspace.py` **11 passed，1.15s**；Ruff 全仓检查与格式检查（335 files）再次通过。三个元数据字段已显式同步准备 0.4.2，源码截图仍保留拍摄当时 0.4.1，不改写图片中的历史版本。

## 后续修订：移除概览录音卡片（0.4.3 源码）

按用户新增要求，概览已整块删除「准备就绪 / 开始录音」卡片，包含状态描述、音量条、录音时长、开始和取消按钮；未保留隐藏录音控件。页面顺序为模型选择 / 计费、三项指标 / 七日图、隐私说明。默认用既有快捷键启动 / 停止录音，`handle_command("toggle")` 路径不变。

仅卡片专属回调与连接删除；悬浮、托盘和共享 RecordingControls 的时长更新保留。详细错误 / 取消原因转到既有状态栏，idle 不覆盖末次详情。窗口底部仅准备中或任务进行中显示「取消当前任务」，沿用 Session.cancel；借用现有 100ms Session.timer 更新，不增加第二套状态机。无系统通知时，提示用户使用托盘菜单或打开设置后在窗口底部取消。

源码私有离屏截图 `build/ui-card-removal-source-r1/overview.png` 实际显示无录音卡片的新概览；不据此声称新包已部署。定向原批次 UI + 工作台 **85 passed，8.84s**，随后增加真实准备中取消回归，`tests/test_workspace.py` **14 passed，1.72s**：实际 toggle 到阻塞的模拟授权，处理 Qt timer 后按钮可见，点击后 pending 清理且按钮隐藏；全程无输入授权 / 录音 / 云请求。全仓 Ruff / 格式检查335files、diff空白检查通过。

旧 0.4.2 AppImage `243aaedc4bc51aa12766638daa0c37e441e305f9ef0497099ec3a4bdc38695b7` 保留为候选，未更新稳定入口。其 workspace R1 即刻断言和 R2 3秒等待均因原生 Wayland Qt minimized 标志不成立而失败并原样保留，后续不重写为通过。

独立最小关闭诊断 `build/v0.4.2-ui-acceptance/results-close-r1/diagnostic.json` 原进程36173正常wait0，保护路径不变。仅自有 WAYLAND_DEBUG 证实 `xdg_toplevel#41.set_minimized` 已发送；Qt close返回时曾为minimized随后清除，显式hide后show_window恢复visible/exposed。Qt6.12官方[requestWindowStates源码](https://raw.githubusercontent.com/qt/qtbase/v6.12.0/src/plugins/platforms/wayland/plugins/shellintegration/xdg-shell/qwaylandxdgshell.cpp)明确在请求后移除WindowMinimized；[xdg-shell协议源](https://raw.githubusercontent.com/wayland-mirror/wayland-protocols/main/stable/xdg-shell/xdg-shell.xml)不提供当前最小化查询。该结果证明请求与恢复路径，**没有观察 compositor 最小化外观**；Xorg仍需用其实际状态验收。后续0.4.3新包必须重新完成同SHA双系统实际验收，不借用此0.4.2候选结果。

Root 独立受限 sandbox 批次未完整通过：确认自有测试 PID37897 后发 SIGINT，原进程返回 exit2，已经完成 **84 passed，94.37s**，最后本地事件循环仍在等待；该批记为中断，不当作全通过。允许本地 socket 环境的85项与新增14项记录如上保留；最终干净提交的完整 workflow 另行执行。

## 0.4.4 源码修复：Wayland 悬浮预览不抢焦点

0.4.3 候选包保留，SHA-256 `d11b8502bf5c4ed10221ff2b0915ae80630ffbe1ee24babcfdc3d172e6ca8ea7`，没有替换稳定入口。五页、空配置 / 旧配置、计费 mock、身份 IPC、AppRun 和 local WSS 检查已有实际记录，但首次 native 输入测试在 Siri 焦点检查处停止，未发送按键，后续输入与 Ubuntu 24.04 验收没有执行。

独立无输入诊断 `build/v0.4.3-ui-acceptance/results-focus-r3/diagnostic.json` 证实旧 Tool 悬浮确实夺焦：显示前浏览器 document / field 均聚焦，显示时十个新鲜样本 document=false、field=true，样本年龄8–27ms，同时 Qt 悬浮 active / focus=true；隐藏后自然恢复。该问题不是过期采样，也不能以 Qt no-focus flags 代替桌面实测。

两项一次性可行性探针保留于 `results-tooltip-r1/{wayland,xcb}.json`。原生 ToolTip 缺 transientParent，Qt 日志明确无法创建 popup，窗口随后销毁，不能作为可用悬浮。独立 XCB ToolTip + override-redirect 在同一个原生 Wayland 浏览器目标前持续可见 / exposed，20个新鲜 document / field 样本均为true；自有窗口 WM_HINTS 不接受焦点且 override-redirect=yes。两项仅固定合成草稿，无输入，未修改产品配置。

修复保留主设置应用的原生 Wayland 后端，仅悬浮使用 QProcess 的独立 XCB 宿主；Xorg 直接使用相同 ToolTip / override-redirect widget。宿主仍设置 InkEcho application name、desktop ID 与图标，不创建另一套设置或模型会话。主进程仅经 stdin 传递白名单显示设置、状态、音量和最多240字符的 RAM 草稿；不发送凭据、模型、URL、音频，不将正文放入 argv / env / 日志 / 文件，也没有截图或任意文件输出命令。

协议使用递增 revision 与完整快照：音量 / partial 更新每40ms合并为一个待发送快照，取消 / idle 的状态边界拒绝旧 ACK，宿主拒绝旧 revision，终态丢弃草稿。代理的可见性只由实际宿主 ACK 更新，支持同一状态下较旧音量 revision 的 ACK，避免持续更新时永远等不到最新 ACK。首 ACK 最长等待3秒；启动失败 / 意外退出显示安全状态，不自动重启、重放或回退抢焦的 native 窗口。正常关闭以 EOF 清空并退出；仅异常卡死的自有显示宿主，在3秒后清理并再次有界等待，不涉及输入 worker。

实际生产 `create_overlay` 源码代理验证在 `build/v0.4.3-ui-acceptance/results-proxy-focus-r1/proxy.json`：原生主进程54680，XCB宿主54914；一秒后真实 ACK visible / exposed=true、style=siri、text_length=35；取消处理后ACK长度0，隐藏后visible / exposed=false。20个 document / field 样本全部true、年龄16–30ms；外层诊断与自有浏览器自然wait0，cleanup为空。宿主 finished 信号触发诊断 Qt 循环退出；该源探针没有单独保存宿主退出码，后续新包门需记录。旧0.4.3包在此仅提供依赖运行时，不作为0.4.4新包验收。

该次固定 helper SHA-256 `2d29e6cbda94fb255293243550f977e90cd06f4da028aebb60042cf5b405cbbc`，plan `54f792f9b151ca346f06c7b37ea6f2ab83cba89f6ad5d2bbfd57e59d5f47d24f`，owner `d640136d862ff1e7110d9dfb8eb1beac721a353bd8d71f993a8c7898ad5fc5ca`，runner `311bca1868a9ac50fe3afece4e049b182a8f889f3e57effe64382d5f98336388`。实际用户配置只作 hash-only before / after 观测，不解析或还原；候选包、旧包、稳定入口、图标与冻结源码仍严格保护。

定向验证：既有工作台 / UI **86 passed，9.11s**；新增协议与生命周期 **29 passed，0.09s**，覆盖非法 / 超长 / 非显示字段、取消与旧快照、合并音量、连续更新 ACK、同 revision exposed 变化、旧状态 ACK 拒绝、首 ACK 超时安全提示、EOF正常退出与异常显示宿主有界清理。此处不声称新 AppImage 双系统支持：0.4.4 仍须构建同 SHA 的新候选并分别完成 Ubuntu 26.04 与 24.04 实际包验收；不沿用旧包输入结论，不改物理快捷键或麦克风配置。

配置外部变化单列：早期 focus R1 / R2 的 preflight 看到用户正在编辑的真实配置与旧保护快照不一致，子诊断尚未启动；这两次不算焦点复测，不将变化归因于探针。未解析配置正文、未恢复旧文件。改用同一次 owner 的只读 hash 观测后，实际 tooltip 两项与生产代理源诊断的 before / after 均无差异；这只描述各自观察窗口，不承诺用户配置永远不变。其余不可变保护仍全部通过。

最终本次源码 Ruff 检查、格式检查（338 files）及 diff 空白检查通过。版本三处同步为0.4.4；等待干净提交的完整本地检查与新候选双系统验收。
