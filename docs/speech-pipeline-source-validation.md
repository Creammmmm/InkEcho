# 语音输入修复：源码验证索引

记录时间：2026-10-23。本文汇总 `codex/ubuntu24-input-pipeline` 的源码模块验证，整理时 HEAD 为 `9268c9a` / `0.8.13`。各实测绑定各自冻结文件和SHA，不能整体改称最终HEAD已通过同一轮检查。本报告不是发布批准，也不是已完成的AppImage包验收。

**0.9.0 candidate AppImage 路径、SHA-256、inventory SHA-256、最终 source commit、不可变包验 stage SHA：全部 pending。** 尚不能宣称同一 AppImage 已通过 Ubuntu 24.04 / 26.04 双系统包验收；不能更新稳定入口或将下列源码结果标为新包通过。

## 已有报告与源码实测

| 项目 | 可审阅报告 | 已有实际证据 | 必须保留的边界 |
| --- | --- | --- | --- |
| 录音开头缺失、异步凭据等待 | [音频链路修复](ubuntu24-audio-pipeline-repair.md) | 两个真实 Ubuntu 桌面均运行 Recorder / QAudioSource / Session、独占虚拟音频和本地 TLS fixture。约400ms假凭据等待时，旧源丢失开头marker，修复源保留约1600个marker样本；取消、短按停止及迟到凭据有回归覆盖。 | Ubuntu24使用旧0.8.0包解释器提供依赖、冻结新源覆盖，明确是源码验证。没有开启物理麦克风，没有真实云ASR，也不能据已知fixture final文本证明自然语音准确率。 |
| 识别润色与输出重叠 | [音频链路修复：SSE时序及完整链路](ubuntu24-audio-pipeline-repair.md) | 修正probe使用产品 ManagedQtEventLoop 后，两系统真实本地 HTTPS/SSE 在完整文本前约418ms开始 observing-input dispatch。Ubuntu26另有真正 native Wayland Chrome 完整Session源码实测，可信 input 前缀1–9、实际部分图「本地」、最终九字精确。 | observing fake不等于键盘接收；26完整链路绑定冻结0.8.7源，不能冒充最终HEAD或0.9包。fixture故意分段/停顿不代表真实供应商网络延迟或flush行为。Ubuntu24 r2源另有真实完整Session→Code普通/取消实测，见下表；这些均不是新包。 |
| Codex / Electron 输入错误、逐步输出 | [键盘输入诊断及r2回归](ubuntu24-keyboard-regression-validation.md) | 旧源普通Chrome、VTE及GTK基线保留。真实Code/xterm收到245个NUL而非正文；物理a正常，借用映射单字中失败，core映射提示后单字与InputFocus对照成功。最终r2仅借行范围、按图revision及当前窗口去重，GTK4 245字每个前缀正确且实际中间画面渐进；Code混合17字精确。 | 用户“恒重复前两字”未完全同形复现；客户端旧映射可导致旧字复用是机制推断。r1每键全图提示曾导致GTK4我→测，真实失败及其原始返回1不得删除。r2已修正该候选，但源码短句/控件证据不能替代同SHA新包或用户全部应用。 |
| 当前光标语义与取消后停发 | [键盘输入r2焦点/transport取消](ubuntu24-keyboard-regression-validation.md) | 主 Agent 审阅两个新空自有窗口后，前3字进入Code，第三release后切GTK，后3字进入GTK；第6字后取消，两个receiver继续观测1200ms，无尾字、映射归还、按键平衡，正常退出。 | 此项是 `can_continue` transport取消，不是完整 Session.cancel 或按ESC端到端证明；不捕获录音目标、不将焦点变化视为失效、不重放已发或不确定输入。 |
| 无语音不弹窗、Xorg ESC、润色模板 | [交互取消及纠错模板](interaction-cancellation-correction-validation.md) | quiet empty/whitespace/零PCM/供应商明确empty保持内部EMPTY分类，桌面idle及非弹窗状态；真实错误保留。Ubuntu24 Xorg源码ESC实测：普通a到达，活动ESC取消后闲时ESC恢复，焦点保持，自有Qt目标正常退出。四个内置模板增加同音/近音/近形纠错与歧义及专有信息保护规则。 | 196项初始检查及后续targeted结果不可相加当完整最终suite。保留既有sandbox挂起、错误fixture路径及修正记录。模板文本断言不是实际模型纠错质量；未访问真实云或真实密钥。新包quiet八场景门尚待运行。 |
| 原生Wayland ESC | [Wayland任务ESC](wayland-task-escape-validation.md) | Ubuntu26真实own-app Registry / GlobalShortcuts Portal；生产 TaskEscape / PortalTaskEscape 同一轮peer disconnect后取消，后续闲时ESC到达，owned native Qt目标及sender自然退出；107项focused检查通过。 | 初次授权可能显示系统UI，最初grant完成未被主 Agent 或自动化直接观察；bounded窗口采样不是保证永不闪窗。活动ESC按下被拦，断连后的对应release到达目标，此边界明确保留。不是Ubuntu24 native Wayland支持或同SHA包验收。 |
| 新旧后台身份、已启用自启动 | [运行身份与自启动](startup-identity-autostart-validation.md) | 私有IPC复现新调用请求被既有owner接收而未进入初始化；私有非执行AppImage样本复现launcher更新但已启用autostart仍旧路径。修复仅同步已有受管理autostart的可执行token，保留参数，不创建/开启自启动；30项integration检查通过。 | 没有加入跨版本身份握手或自动旧实例替换。合成APPIMAGE路径并非真实旧/新release二进制交接验收；不能仅凭新文件名认定实际处理进程已升级。正式包验必须记录真正owner PID/starttime及包内模块origins。 |

各报告包含其冻结源、工具及原始结果路径与SHA。报告中的旧源基线、失败fixture、被拒绝的guard、候选r1失败及后续成功具有不同范围，不能只摘选成功计数。上述focused suites有重叠，不能累加为独立总测试量。完整clean最终HEAD检查及其记录仍为发布前门。

## 已实现源码及版本定位

| 提交 | 变化 | 本索引的解释 |
| --- | --- | --- |
| `3059a05` | 录音先于异步凭据设置，保留开头PCM及启动竞态处理 | 对应录音缺失源码修复，不把本已工作的SSE流式能力重新算作新修复。 |
| `dc3ac5a` | Xorg生产Session分段映射/取消回归覆盖 | 测试提交，本身没有修复Electron。 |
| `94422c3` | 已启用受管理autostart更新image路径 | 只修路径漂移，没有旧owner身份握手。 |
| `619bf8e` / 0.8.10 | 当前Xorg client键图缓存提示，借行范围及revision/窗口去重 | 最终r2；原r1 GTK4错误仍记录。提示是缓存失效信号，不是目标完成显示的ACK；不改按键等待。 |
| `940ab17` / 0.8.11 | native Wayland任务期Portal ESC | 先disconnect再同轮取消，保留活动release透传及初次授权边界。 |

这不是最终release源commit列表；0.9.0准备提交、主分支合并及最终source SHA仍pending。模块报告中早期的“当前源码/候选”属于当时记录，最终键盘行为应以r2部分及提交 `619bf8e` 为准。

## 完整Session的实际源码对照

以下均使用真实Recorder、Session、本地TLS ASR及HTTPS/SSE、生产键盘，而不是仅调用sender或替换接收端。独立receiver与原始进程结果详见[音频报告](ubuntu24-audio-pipeline-repair.md)；各自正常与取消场景使用新的空白自有目标。

| 实际桌面与场景 | 实测结果 | 归属与限制 |
| --- | --- | --- |
| Ubuntu24.04.5 GNOME46 Xorg，Code/xterm + 真正离线Codex，普通9字 | 首PCM7.113ms，marker1600样本；实际输入比完整润色文本早297.722ms。9个trusted DOM key、9个UTF8 PTY正文及9个Kitty释放码精确、无NUL；截图前后实际计数2/2、5/5、8/8均是部分正文，最终9字准确。sender与Code/owner原wait自然0，映射及默认音频设备恢复。 | r2冻结manifest `92e88de01d36fdea98756dd3442edc38641ad27de17782f84eb1b44704e8e7e4`，键盘386d8349…；旧0.8.0解释器只作依赖，产品模块来自冻结r2。CLI随Code关闭时PTY hangup记为 `cli_exit=-1`，不能写CLI exit0。最初Pulse17依赖失败未发键，原失败保留。 |
| 同桌面，fresh Code，真实Session.cancel | first-sent回调同步调用Session.cancel，epoch1→3，即时失效；仅1个press/release。独立receiver60次、1.206536s观察始终只有「本」，实际PTY与最终图相同；没有后续SSE尾字。sender与Code/owner自然0、恢复检查通过。 | 这是Session取消，不仅是 `can_continue` transport模拟。CLI关闭仍有独立PTY hangup-1记录；没有验证真实云和物理麦克风。 |
| Ubuntu26.04 native Wayland，fresh native Chrome，真实Session.cancel | epoch1→3，1次实际native press/release及ACK、0 guard拒绝。独立receiver107次、1.208353s始终仅「本」，实际部分/最终图相同；Mutter图、group、modifiers、X11图及音频默认设备恢复，sender/guardian/browser/原wait均自然0。 | 绑定0.8.11冻结源stage `e23ddc39170f59d83f6950155d0068aeca395eaa080b1feee94b8c5b49eeeecc`。sender的名义sleep1.2实际1.140958s，不将它算作1200ms证据；通过门来自独立system-Python receiver的实际1.208353s。 |

Ubuntu26普通9字完整链路另绑定0.8.7冻结源，记录全部可信1–9前缀和实际部分/最终图。上述多次冻结源的结果不合成为一次clean最终HEAD或同SHA包验收；各报告保留完整module origins、raw SHA和退出结果。

## 同SHA实际包验收待填

| 必需门 | Ubuntu24.04 | Ubuntu26.04 |
| --- | --- | --- |
| 完全相同0.9.0 AppImage的SHA及大小、inventory SHA | pending | pending |
| 该AppImage自身提取、该包Python解释器、完整文件集及模块origin审计 | pending | pending |
| 实际处理owner PID/starttime、配置目录隔离、版本/来源确认 | pending | pending |
| 源码修复绑定到新包的quiet/no-speech及错误可见性 | pending | pending |
| 真Recorder→Session→本地ASR/SSE→真实键盘→独立receiver前缀/部分及最终像素 | pending（Xorg + Code/xterm） | pending（native Wayland owned target） |
| 按键平衡、映射/修饰状态和默认音频设备恢复、原始自然wait及清理 | pending | pending |
| ESC活动取消及闲时恢复、明确授权/后端限制 | pending（Xorg） | pending（native Portal） |
| 实际AppImage Dock身份、关闭/退出/快捷键后台行为的既有包门 | pending | pending |

任一包门未完成时只可称候选包。Ubuntu24本轮实际GUI键盘证据为GNOME46 Xorg；不得据此宣称GNOME46 native Wayland已支持。Ubuntu26原生结果也不能由XWayland或单系统结果替代。

## 验收fixture闭包准备（不算包验通过）

0.9静态Code闭包已准备为 `build/release-0.9.0/code-closure-r1.json`（SHA `e2766ec39cb78164b35113f804e393502c19731e382aa2d1dfbbfc111360b3f5`）。显式package模式将artifact、inventory、冻结源及模块origins审计绑定到选定新包解释器，然后调用唯一通用完整链路sender。私有Code profile、假凭据、禁外网namespace、真实sandbox、透明PTY及只读阈值截图均独立于用户配置。未运行的包wrapper不能写成已验收。

Pulse工具是外部验收依赖，不改变AppImage。经审的prepare将分别冻结Ubuntu24 native16.1和Ubuntu26 native17.0 payload及固定SHA；相同regular launchers根据实际OS选择并清除仅external Pulse进程的AppImage库/Python环境。独立两实际OS的 `--version` 与只读默认sink查询已验证；没有加载虚拟模块、开启物理麦克风或改系统库。它只证明fixture工具可运行，不证明0.9应用音频链路。原sandbox socket拒绝及补充的正常权限只读结果均保留。

实际包验、物理麦克风自然语音识别、真实云供应商准确率/网络时延是不同验证层次。本次源码fixture使用假密钥、本地协议服务及已知文本，不能推导后两项通过。

## 完整源码检查中的工作区测试假设修正

首次完整检查结果为 **1917 passed、2 skipped、1 failed**。唯一失败是
`test_preparing_shortcut_keeps_status_cancel_until_pending_cleanup` 仍假设等待密钥时
不存在任务；这与已实测的「先开始收音，再异步读取密钥」行为矛盾。原工作区 fixture
还创建真实 Recorder、键盘输入和全局 Escape，模拟设备列表只屏蔽了页面枚举，不能
隔离真正的录音启动或 X11 快捷键后端。

本次只修复测试：向工作区注入模拟录音器、已授权模拟输入与不接触桌面的 Escape
对象，保留真实按钮的取消连接和 active 状态。断言加强为等待密钥时录音已启动一次、
任务有效且处于 RECORDING、取消按钮可用；点击后必须清空待处理工作、录音、任务、
密钥与上下文，启动 Future 结束为 False，并保留「已取消」状态。fixture 以完整
Session.close 收尾。产品代码没有改变，也没有删除或跳过该回归。

应用修正后的 `tests/test_workspace.py` 初次定向运行 **14 passed、1 warning**；
取消测试的 Qt 等待期间，无关概览余额 timer 创建的协程在执行前取消，产生未 await
警告。该原始结果保留，不能据此宣称余额产品行为已修复。随后该取消回归在 show 前
通过真实导航选择模型配置页，隔离不属于本测试的概览后台 timer；余额功能仍由本文件
已有独立测试覆盖。相同文件再次运行 **14 passed、无 warning**，Ruff、格式及差异
检查通过，没有修改产品。最终 release 准备和打包前仍须重新完成完整源码检查；此次
定向结果不能替代该门，更不能算实际新包验收。
