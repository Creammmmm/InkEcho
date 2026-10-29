# 自动检测输入框架：证据与设计，尚未实现

## 约束

录音开始不能捕获目标；用户可以在录音、识别、润色和输出期间切换焦点。
目前 OutputRouter 在录音准备时选择并固定后端，因此当时读取的桌面输入源、
环境变量、桥是否存在，均不能证明实际输出时光标所在组件使用该桥。已经
尝试发送而结果不确定时，不能改用另一桥重放。

## 实际隔离实验

2026-10-28，Ubuntu 24.04 / GNOME 46 / X11 隔离虚拟机中，IBus V2 扩展
启用、IBus 全局引擎为 `xkb:us::eng`、GNOME input-sources 的 sources 为
`[('xkb', 'us')]`。两份独立自有 GTK 3 进程分别设置
`GTK_IM_MODULE=ibus` 和 `GTK_IM_MODULE=gtk-im-context-simple`；各进程中
新建的 `Gtk.IMMulticontext.get_context_id()` 分别实际报告 `ibus` 和
`gtk-im-context-simple`。该观测表明同一会话的不同进程可以选择不同 GTK
输入模块；它是进程内新建的 IM 上下文，不是对 Gtk.Entry 私有上下文的直接
读取，不证明任何用户窗口的具体输入法。

尝试将焦点切到自有窗口后向两者通过 V2 发送固定测试字：最初
`xdotool windowactivate --sync` 超时，之后使用不带 `--sync` 的激活并
检查活动窗口，两次均无法确认焦点；脚本在发送前停止。因而本次没有任何
输出接收结论。`target.py` SHA-256
`fef5250160c62f9688611996ecadfbb4d5f654b7a667592de22e2d4e26968ff5`；
最后的 `probe.py` SHA-256
`ef90749622786d067c7862657395ce58e78bd08f8efdbce3470bbb907f12ab22`。
文件在 `experiments/ibus-gnome-shell/auto_detection/`，仅用于自有测试窗口。
扩展被停用并卸载，GNOME 扩展列表恢复空，测试临时目录删除，VM 正常关机，
容器退出 0。未读取其他应用正文。

## 能力边界

[Fcitx5 的 InputContext 接口](https://github.com/fcitx/fcitx5/blob/master/src/lib/fcitx/inputcontext.h)
说明 `program()` 是程序名称且可为空；[焦点实现](https://github.com/fcitx/fcitx5/blob/master/src/lib/fcitx/inputcontext.cpp)
显示其焦点状态由输入上下文和焦点组维护。因此单个 `foreachFocused` 结果
不证明该上下文与 GNOME 当前前台窗口或光标属于同一控件。IBus 扩展的
Shell panel 可用也只说明面板存在；`commit_text` 返回不确认目标收到。
会话 `sources` 列表和 IBus 全局引擎同样不是某个进程内部 GTK、Qt、XIM 或
原生 Wayland 输入上下文的可靠证明。不能依赖已经过时的 `current` 设置键。

## 保守设计与尚缺验证

1. 在真正发送前获取桥可用性和**目标关联**证据，而非录音开始时固定一个
   框架。系统当前输入源和服务所有者只能作为辅助证据，不能单独决定。
2. 必须由桌面/输入框架提供可验证的当前焦点与唯一输入上下文关联；仅有
   进程名、环境变量、全局引擎、活着的服务或唯一 Fcitx 焦点仍不足够。
   这一关联目前没有实现，且不同桌面、X11/Wayland、Chromium 和终端需要
   单独验证。未找到证据时保守选择原键盘路径。
3. 焦点在输出期间允许变化。若要按片段改路由，需重新确认每片的实际目标，
   并避免与用户现有输入法和预编辑冲突；若无法确认，则不能冒称自动检测。
   即使结果为空、超时或提交状态不明，也不能重放已尝试的片段。
4. 应分别在 Ubuntu 24/26、Wayland/Xorg、IBus/Fcitx/simple、原生与 XWayland
   实际应用中执行切焦点、并发服务、无焦点、预编辑和取消测试；不读取正文。
   当前实验的焦点失败须保留并重试，不可当成通过。

当前产品自动模式继续使用键盘；此文档不是对框架自动检测的支持声明。

## 2026-10-28 系统框架与服务 owner 的额外验证

在隔离 Ubuntu 26 GNOME Wayland，会话初次重启后停在 GDM greeter，此时
session bus 没有 IBus；这是未登录状态，不能当作正常桌面判断。有界重启
一次后，用户桌面就绪，user manager 环境中 `XMODIFIERS=@im=ibus`、
`QT_IM_MODULE=ibus`，`GTK_IM_MODULE` 未设置，sources 为 xkb/us。
此时 session bus 的 `org.freedesktop.IBus` 有唯一 owner，D-Bus 返回的
UID 为 1000、PID 对应 `/usr/bin/ibus-daemon`，全局引擎为 xkb/us。
IBus 私有总线中同名服务也有 owner。图形会话未就绪时，该证据不可用。

随后仅在该虚拟机临时启动自有 Fcitx5 进程，`org.fcitx.Fcitx5` 和
`org.freedesktop.IBus` 的唯一 owner 变为同一个 Fcitx5 进程，而 user
manager 环境仍显示上述 IBus 字样，`ibus engine` 查询不再获得引擎。
因此即使 service name 和环境均出现 IBus，也不能只按名字或环境判定：
必须核对 D-Bus 唯一 owner、同用户 UID、PID 和进程镜像，并再次核对 owner
未发生变化。owner 指向 Fcitx 而环境仍指向 IBus 时，应作为冲突而回键盘。
这不是一个活跃目标控件的关联证明，也不能将系统框架误称为控件框架。
测试后只停止了测试启动的 Fcitx 进程，移除了本轮临时安装的十个 IBus
依赖包，VM 正常关机、容器退出 0；包缓存与历史留在一次性虚拟机。

`experiments/framework_detection/` 中 `evidence.py` 为独立的保守系统
框架选择模型，要求 XIM 提示与至少一项 GTK/Qt 提示一致、配置可读取、
对应框架的 owner 身份和桥握手均已确认；任一项缺失或冲突则不选择框架。
`collector.py` 仅为只读 owner 实验，查询 UID/PID/镜像并复核 name owner，
不连桥、不检查焦点、不读取正文。14 项独立测试覆盖冲突、缺失、服务更换、
非对应进程及没有桥的情况。当前模型没有真实桌面桥握手或系统环境采集的
端到端验证，固定 `/usr/bin` 进程路径也可能对非标准安装产生保守假阴性；
它仍未连接产品。采集期间连接断开、进程替换、同 UID 对进程或 session bus
的干扰也需要处理；不能将其称为强安全边界。

## 后续自动选择与窗口切换验证

后续完成系统级 Fcitx 线索采集和输出前双次 owner 核验：仅当图形会话的
XMODIFIERS 与至少一项 GTK/Qt 提示一致、Fcitx 唯一 owner 的用户与受信任的
可执行文件匹配、输入源配置可读取、桥握手成功且 owner 未改变时选择 Fcitx。
合法的空输入源列表 `@a(ss) []` 可以出现于 Fcitx 会话，不应当判为格式
错误。录音准备阶段仍尝试准备键盘；键盘不可用时先保留错误，若 Fcitx 桥
可用则不阻断它，只有需要键盘时才报告键盘错误。系统框架不保证每个控件
使用该框架；缺失、矛盾或不可信的证据在任何发送之前退回键盘。

Ubuntu 26 Wayland 的隔离会话中，使用真实 Fcitx5 和已验证候选桥，将
三个会话变量暂时设为 fcitx 后，自动模式在首段输出时选择 Fcitx；两个
自有 GTK 窗口切换后分别收到甲、乙。此前两次因 GNOME 返回合法空列表
而未选择桥；修正解析后重试通过。Ubuntu 24 X11 的独立进程对照中，Fcitx
控件收到甲，切换至 simple 控件后该桥返回明确的 no_target，控件为空。
源代码中该结果在调用 `commitString` 前产生。精确交接只适用于自动
Fcitx 且当前片段可信回复明确为 0：已确认前缀不重发，检查任务仍有效后
只将剩余字符交给键盘；超时、未知答复、取消和 IBus attempted 均不交接。
在 24 X11 真实桌面中，生产 OutputRouter 向 Fcitx 控件发送 A，切至 simple
控件后接到 no_target，只将 BC 交给隔离 xdotool ASCII 键盘模拟器，两个
自有控件分别为 A 和 BC；这不验证生产键盘或 AppImage。两台 VM 均恢复
测试设置并正常关机，容器均退出 0。具体代码仍需实际包双系统验收。

IBus 对照证实它不能被当前逻辑安全自动选择：24 X11 中两个实际聚焦的
自有 GTK 窗口先后使用 IBus 和 simple；IBus 控件收到甲，simple 控件没有
收到乙，但桥返回 attempted/计数 1。私有 IBus 总线的 CurrentInputContext
在两个窗口均返回非空路径（分别为 InputContext_8 和 InputContext_1）；
非空并不能证明目标控件会接收。两进程独立的 `get_context_id()` 在这次
未聚焦辅助上下文中均返回 None，不应拿它证明控件模块，控件运行时使用的
GTK_IM_MODULE 则由自有进程分别显式设置。曾有多轮窗口未正确聚焦而停止，
原因是 X11 同名窗口搜索首先匹配窗口管理器窗口；后续使用目标进程 PID
并选择实际应用窗口，再确认活动窗口后取得上述结果。IBus 自动选择仍
禁用；显式 IBus 仅尝试提交，目标可能没有文字。

上述实验代码更新后的 SHA-256：`target.py`
`d5ecb06be3fd9dfaa5c2e249bb42f2c0702e422624a9bb393f472cdd8317e76c`，
`probe.py` `617d106d6bf0d79e4ed0c457f9b8698d4292e1e3f13e5cd77914194ff1f2f6f7`，
`probe_fcitx.py` `9eea0d3ca08b25cca7dd65d81a17ee33415d75313c153d3fe810bc03109f13a2`，
`guest_handoff.py` `b681e5ee0938e499211b19786c27dd42df8628aca651d03cee97792bb2de2b77`。
其中 `probe.py` 在成功实测后增加了私有总线上下文检查并再次成功运行；
之前记录的哈希和失败属于不同修订，不应互换。

## 换行与部分输出提示

### 临时交接保护（后续修订）

上文的生产路由交接策略已收紧。自动 Fcitx 任务只有在整个任务尚未提交任何
字符、且收到明确的未发送结果时才可回退到键盘。提交过文字之后，遇到无
目标会继续等待输入法焦点恢复直至任务期限；过期后报告部分文字已尝试输入，
不向键盘重放后缀。取消和投递状态不明仍不能回退。等待和 Fcitx 返回均不
表示接收应用已处理文字。

该保护针对 r5 隔离桌面发现的真实失败：明确未发送后缀向键盘交接后，
目标文本发生错字。独立取证命令 `python3 build/handoff-review/reproduce.py`
从既有固定合成文字日志提取事件；末个 Fcitx 受理到接收约 502.4 毫秒，
第一次回退按键早于 B 聚焦约 195.1 毫秒。记录不能单独证明错字的精确
解码机制。路由与桥单元测试覆盖未发送回退、分片后的等待与恢复、过期和
取消；它们不能替代实际桌面或包验收。此措施会在输出途中切换到不支持
Fcitx 的目标时停止剩余输入，尚未实现可靠的跨框架连续输入，不能作为
Ubuntu 各会话组合已经支持的证明。

#### Ubuntu 26.04 隔离桌面验证

在 Ubuntu 26.04.1、XFCE、X11 活动会话的隔离 QEMU 中，以 r6 候选包
`e4f2c6de3450cd997607baaeba41dd1764f8365c0bda73d9b9dd7c4ac395db54`
解包后的运行时加载当前两个源码覆盖文件：`fcitx5.py` SHA-256 为
`8cd26a449056d65d9d08cb1c087c26a4d29c00bf8108a4d6f408ff7b2a28494e`，
`output_router.py` 为
`7dda79e409540f7950c708041649ecc108b54a369814f95edd6b7c486cf8a26c`。
测试使用独立 Fcitx 服务、候选插件和两个自有 GTK Entry，分别设置为
`fcitx` 和 `gtk-im-context-simple`；只发送固定合成文字“甲乙”。

可复现脚本位于 `experiments/fcitx-handoff/`。仅在隔离虚拟机中准备 X11
桌面、Fcitx5 和 xdotool；将其中的 `run.sh`、`probe.py`、`target.py`、
上述 r6 AppImage 及两个哈希一致的源码文件放入 `/tmp/handoff-r7/`，
运行 `bash /tmp/handoff-r7/run.sh`。脚本使用独立 XDG 目录，保存并恢复
测试会话的输入法环境变量，安装后停用候选插件。原始 `run.sh`、`probe.py`、
`target.py` 的 SHA-256 分别为 `95077f4cd5d5293a0eeae1b7f92511c658a5108e4d19157137aaf3343b6c2b66`、
`6ca8347ab302c9494370a50c3e9f6c5f0b74941bee4f106762aff68f2516f0f8`、
`d5ecb06be3fd9dfaa5c2e249bb42f2c0702e422624a9bb393f472cdd8317e76c`。
后续 Wayland 实验准备时，`build/ubuntu26-release-vm/state/handoff-r7/` 中
的原始 `probe.py` 与 `target.py` 被误覆盖。`target.py` 已按上述原始哈希
恢复；原始 `probe.py` 的同哈希副本未找到，其位置现为下述格式化版本。
原始测试输出及记录的原脚本哈希保留，不能再声称该原始脚本副本仍存在。
仓库中的 `probe.py` 后经格式化，SHA-256 为
`7e7bb94753d7d1f5a6f6bc7ffdc72f14d6d3736ab340ff6b995a0d67890df54f`；
格式化后的脚本通过 Ruff 检查，但未在该 Ubuntu 26 虚拟机重跑；后续
Ubuntu 24 验证使用了格式化版本。其他两个文件未变化。

三次独立目标测试先在 Fcitx 控件输入“甲”，再切到 simple；700 毫秒后
第二字符仍在等待且 simple 控件为空。切回 Fcitx 时最终收到“甲乙”；
停留在 simple 直至 1.5 秒任务期限时报告 `partial_input_failed`；取消时
报告 `fcitx_cancelled`。后两例只观察到“甲”，simple 为空且未调用键盘。
取消后的观察时间为 500 毫秒。原始输出保存在
`build/handoff-review/desktop26-r3.log`；前两次因脚本 Python 环境和
异步任务归属错误而失败，记录保留，不计为产品验收。测试后比较恢复了
虚拟机测试账户的原会话配置、删除临时目录并正常关机。

该实验使用从真实 Fcitx D-Bus 服务查询到的 owner 作为固定检测结果，
键盘是调用即报错的观察替身；它验证源码覆盖后的桥接与路由行为，**不是
新 AppImage 包验收**，不验证自动检测、生产键盘、真实语音或其他系统及
会话，也不证明 Fcitx 受理等于目标处理完成。跨框架连续输入仍未解决。

#### Ubuntu 24.04 Xorg 隔离桌面补测

在 Ubuntu 24.04.5、GNOME、活动 X11 会话的隔离 QEMU 中，重复上述
固定文本和自有 GTK Entry 实验。使用同一 r6 AppImage 与上述两个源码
覆盖 SHA；此次实际运行格式化后的 `probe.py`，SHA-256 为
`7e7bb94753d7d1f5a6f6bc7ffdc72f14d6d3736ab340ff6b995a0d67890df54f`，
`run.sh` 和 `target.py` SHA 与前节相同。其操作步骤和限制也与前节相同，
实测副本保存在 `build/ubuntu24-perf-vm/input/handoff-r7/`。

首两轮因 GNOME 活动概览遮挡、目标未取得焦点而失败，日志分别为
`build/handoff-review/desktop24.log` 和 `desktop24-r2.log`。在隔离桌面
退出活动概览后，第三轮 `desktop24-r3.log` 的焦点恢复、1.5 秒到期和
取消测试均通过：等待 700 毫秒期间 simple 控件为空；恢复后 Fcitx 控件
得到“甲乙”；到期和取消分别报告 `partial_input_failed` 和
`fcitx_cancelled`，只观察到已发送的“甲”，未调用键盘。取消后观察
500 毫秒。测试未修改客机账户或 GDM 会话配置；隔离的输入法环境变量
已恢复，临时文件删除，虚拟机正常关机并以 0 退出。

这仍是源码覆盖测试，使用固定真实 owner 和键盘观察替身，**不是 AppImage
包验收**；不能证明自动检测、生产键盘或跨框架连续输入已经完成。

2026-10-28 的本地回归中，非流式输出在 OutputRouter 入口将 CRLF 和单独
CR 统一为 LF，之后才交给键盘、Fcitx 或 IBus；流式输出继续在
StreamingOutput 使用同一规范化函数，并保留跨分片的 pending CR，原始
provider 偏移仍按规范化前计数。Fcitx 向键盘交接的片段偏移按规范化后
字符计算。路由测试覆盖三种后端的 CRLF/CR、含 CRLF 的已发送前缀与
未发送后缀交接；既有 StreamingOutput 测试覆盖拆分 CRLF 和结束时的 CR。
这不是跨所有桌面与应用的实际交付验证。

若 Fcitx 已确认至少一个字符被尝试提交，随后确定未发送后缀的键盘授权
或发送失败，路由返回不含正文的 `partial_input_failed`，界面提示部分
文字已尝试输入；取消仍按取消处理，不借机重放。相关应用、流式和路由
本地测试 155 项通过，1 项既有沙箱线程问题排除。

## IBus 面板焦点事件对照

2026-10-28 在独立 Ubuntu 24.04 / GNOME 46 / X11 虚拟机安装临时监听
扩展，仅监听 PanelService 的 focus-in/focus-out 并记录自有测试的上下文
路径，不读取正文。IBus GTK 自有窗口活动时，CurrentInputContext 与面板
最后 focus-in 同为 InputContext_3，发送后控件收到甲。切换到显式使用
`gtk-im-context-simple` 的自有窗口后，面板先发 focus-out(3)，再发
focus-in(1)；CurrentInputContext 和面板最后 focus-in 同为非空的
InputContext_1。此时桥提交返回 attempted、计数 1，simple 控件仍为空。
该默认上下文的 IBus D-Bus introspection 未提供客户端身份属性。
因此“收到 focus-in”“面板当前路径非空”及“CurrentInputContext 非空”
均不能单独证明当前控件接入 IBus；也不能将本次编号 1 硬编码为跨版本
可靠的无目标标志。PanelService 绑定较晚时初始状态本身还可能未知。

监听器和自有窗口测试脚本位于
`experiments/ibus-gnome-shell/focus_probe/`，合成结果为
`ubuntu24-result.json`；监听器、metadata、测试脚本本次 SHA-256 分别为
`bfe24d3d92fee2d9e2a0412e078868b14fb45c0e49e5753ee0eb39e4786fede3`、
`e85a5b1954dece4d86b75a4eaf65d3f8473e1e8583bed21faa583266f5e24233`、
`97213dd7d97ad3d337452f47312caac95a5dfa26c469da5103faa6f0c0a2068b`。
实验后两个扩展被停用并卸载，扩展列表恢复为空，临时目录清除，VM 正常
关机，容器退出 0。此结果不证明所有 GNOME、IBus 或 Wayland 版本的行为；
当前仍不能靠该焦点信号安全启用自动 IBus。

## IBus 客户端身份及虚拟上下文研究

2026-10-28 阅读 IBus 上游 [`bus/ibusimpl.c`](https://github.com/ibus/ibus/blob/main/bus/ibusimpl.c)：启用全局引擎时，守护进程创建 client 为 `fake` 的内部输入上下文，并设置包含 FOCUS 和 SURROUNDING_TEXT 的能力；真实焦点丢失时它可成为当前上下文并向面板发送 focus-in。故不能依赖这些能力位、非空路径或面板事件判断真实接收控件。 [`bus/inputcontext.c`](https://github.com/ibus/ibus/blob/main/bus/inputcontext.c) 的 client 属于内部上下文信息，前述实际 D-Bus introspection 未显示可供面板读取的 client 属性。

上游 [`src/ibusengine.c`](https://github.com/ibus/ibus/blob/main/src/ibusengine.c) 定义供引擎接收的可选 `focus-in-id`，其 client 可以报告 `fake`；但该能力由活动引擎构造时启用，调用发给引擎而非面板通用可读取接口。更换引擎会影响用户当前输入法，不能作为透明检测。观察事件即便可用，也存在监听开始前状态未知、异步切换和目标接收未确认问题，不证明可以无竞态地提交。

隔离 Ubuntu 24.04 / GNOME 46 / Xorg 上另作只读对照：保留原有 simple 引擎，运行 `experiments/ibus-gnome-shell/client_identity_probe/` 的脚本（将目录复制到来宾 `/tmp/inkecho-focus-client`，执行 `/usr/bin/python3 /tmp/inkecho-focus-client/probe.py`）；仅匹配 `org.freedesktop.IBus.Engine` 的 `FocusIn` 和 `FocusInId` 方法，自建 GTK IBus 与 `gtk-im-context-simple` 窗口依次激活 IBus、simple、IBus，每次核对 X11 活动窗口 ID 与目标相同。无合成文字或用户正文。测试得到三次无参数 `FocusIn`，零次 `FocusInId`；`dbus-monitor` 报私有总线没有 `org.freedesktop.DBus.Monitoring`，回退到 eavesdropping。前一轮只匹配 `FocusInId` 时亦没有事件，且当时输出可能受缓冲影响；后一轮通过行缓冲与 `FocusIn` 正对照排除该解释。两个脚本 SHA-256 分别为 `c642c6407cdccf88f7e7a438b2bcf820f0e6ed566ed3edd42838506f0776db84`（实测 probe）和 `d5ecb06be3fd9dfaa5c2e249bb42f2c0702e422624a9bb393f472cdd8317e76c`（target）；实验后 probe 仅经格式与导入排序调整，仓库文件 SHA-256 为 `70ed77ce169dada46ae90df1641f4ae830370bf9f0a3745aff78a2f282d48678`，格式化版本未在客机重跑。测试进程及目录已清理，客机正常关机，容器退出 0。

这一结果限于该版本及引擎，不能推广为其他引擎永不提供身份；但不能依赖可选事件做普适检测，也不应在产品中监听其他进程的输入总线。现有接口仍不能可靠区分虚拟上下文及真实当前接收控件，自动 IBus 保持禁用；显式选择 IBus 仍须告知目标可能没有收到文字，未确认发送不得重放。

## GNOME Wayland 输入焦点候选（未接入产品）

GNOME Shell [46 的 InputMethod 实现](https://github.com/GNOME/gnome-shell/blob/46.0/js/misc/inputMethod.js)维护 `currentFocus` 和自身 IBus `_context`；主线的 [Main 初始化](https://github.com/GNOME/gnome-shell/blob/main/js/ui/main.js)把它交给 compositor。该私有接口提供仅对原生 Wayland 有待验证的线索，不适用于用 GTK IBus 或 XIM 的所有目标，也不证明应用最终接受内容。输入焦点判定、当前 IBus 路径读取和面板异步提交之间可能切换焦点，不得把一时匹配作为交付确认。

隔离 Ubuntu 26 / GNOME 50 / 原生 Wayland 中使用临时本地扩展，仅返回当前焦点布尔值、Shell 上下文路径和自建窗口名称；不读取 surrounding text。客机先从已有 apt 缓存安装 IBus，现有用户会话内启动它。依次激活自建原生 GTK 输入框、原生按钮、XWayland simple 输入框、原生输入框、XWayland simple 输入框，五次窗口身份均核对一致：原生输入框 `currentFocus=true`、Shell 与 IBus 当前路径相同；按钮与 simple 则为 false、路径不同。分别发送固定字符“甲”后，原生输入框两次收到，按钮和 simple 无字，三种情况面板调用均返回 true；因此该返回值仍不是接收确认。路径编号仅为本次记录，不能硬编码。

首次安装本地扩展后 GNOME 尚未识别，正常重启客机后成功加载；一条额外检查误含远程扩展安装调用，自动审批拒绝，未执行且未重试。固定字符测试首轮桌面尚未就绪，XWayland 控件初始化失败，不能将该轮当成三类对照；桌面就绪后完整重跑才得到上述结果。实验脚本保存在 `experiments/ibus-gnome-shell/wayland_focus_probe/`；实测 extension、metadata、actor 和 probe 的 SHA-256 分别为 `0b6d526df9ee0cba6f46c9b515080d9d8f2177b794272afd8f2c1657e1fce8e1`、`261f9f98f2b1d7fb9734c725d6bf13fe9a5b7ec077bf43315ca07e59034dc30d`、`f4985f4ded460124984baf8b183617d1e79926c3bc859fd0923c0e363746f39b`、`4d44d7428bc77e90f5217245dda44b6d6c4c1cf7f6506d1a87bf01426f7658f4`；Python 脚本入库后仅作格式与导入整理，整理版尚未在客机重跑。测试后扩展停用、配置恢复 `@as []`，移除本次安装的四个包并清理临时文件，客机正常关机、容器退出 0。此实验没有覆盖 GNOME 46 Wayland、其他控件、异步焦点竞态、真实程序及最终包。

进一步审查 [Mutter 的 ClutterInputMethod 实现](https://github.com/GNOME/mutter/blob/main/clutter/clutter/clutter-input-method.c)：`commit()` 构造输入法事件后调用 `clutter_event_put()` 入队，而不是在该调用中同步确认目标已接收。因此即使在同一 Shell 回调中先检查 `currentFocus` 再执行 `commit()`，焦点仍可能在事件处理前改变；检查失败可以确定本次未调用提交，调用后却不能确定是否送达或安全重放。需要在隔离实验中安排检查后立即切换自建窗口、覆盖事件排队与取消，并验证不同 Mutter 版本；该竞态实验本轮尚未执行，不应据此启用自动路由。

### 同一回调提交后切焦点的竞态对照

2026-10-28 在独立 Ubuntu 26 / GNOME 50 / 原生 Wayland 客机进一步验证。临时扩展的同一 D-Bus 方法中，先检查 `Main.inputMethod.currentFocus`，非空时调用 `Main.inputMethod.commit('甲')`，随后立即激活自建 XWayland simple 窗口；在返回前检查 Mutter 活动窗口已是该目标。两次执行时，提交前原生 GTK 文本框均为焦点、方法返回已调用且已切换（`true, true`），两个窗口均未收到字符。对照方法不切换焦点，两次各收到一个甲（累计甲甲）；切到原生按钮或 simple 之后，currentFocus 为假，方法拒绝且不调用 commit。所有窗口是自建，读取的仅固定合成字符；没有读取用户正文。本次使用直接 Clutter commit，并非 IBus panel 调用，不能将其结果扩大成对所有 IBus 路径或版本的验证；事件在 Shell 回调尚未返回时入队，回调内已确认目标改变，观测与源码中异步分发导致丢失一致。

验证代码在 `experiments/ibus-gnome-shell/wayland_race_probe/`；客机实测的原始代码还保存在 `build/ime-feasibility/wayland-race/`，extension、metadata、actor、race probe、control SHA-256 分别为 `0f9d3711c989a003ba4db93dc87132c591eea2a36391ca7cb0f3cf397ce5c1dc`、`261f9f98f2b1d7fb9734c725d6bf13fe9a5b7ec077bf43315ca07e59034dc30d`、`f4985f4ded460124984baf8b183617d1e79926c3bc859fd0923c0e363746f39b`、`a33232be5f38ddfceffe28cfae9a0529f404fe56951c8c44c3883cc8059942e8`、`eff41efaf8d0b8804bee5384e96bf2e958ea1634176a08bddb2fe564998e7145`。入库 Python 版本仅经格式化和导入整理，未经客机重跑；实验扩展停用、设置恢复 `@as []`、临时目录和扩展移除，虚拟机正常关机，容器退出 0。此对照说明检查为真、调用提交后不能声称已交付或确认未发送；自动 IBus 继续关闭，歧义字符不重放。
