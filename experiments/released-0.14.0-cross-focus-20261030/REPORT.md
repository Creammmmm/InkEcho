# 已发布 v0.14.0：Wayland 下原生 / XWayland 跨窗口实际包跟进

2026-10-30。只测试已发布同一 AppImage，不构建、不修改产品源码，不更新稳定入口，不发布。结论是限定目标的输出能力与安全边界，**不是任意应用、任意焦点切换已经全部支持**。

## 绑定及方法

发布源 `0a13b3af12c764992e09622fa6a745067f70cd1d`；`InkEcho-0.14.0-x86_64.AppImage`，104425976B，SHA256 `a79ed5409e6d935ac1d4f4420f06e5ec6bc454fc20bdfe04c6db1e8ed6def055`。本轮只读 GitHub release API 的资产 digest、来源和正式发布状态与之相符，见 `raw/release-identity.json`；每个客机重新验证实际包版本/源码清单/模块来源。模块始终从真实 FUSE APPDIR/packages 导入，没有源码覆盖层。

Ubuntu24 GNOME46 Wayland、Ubuntu26.04.1 GNOME50.1 Wayland 两客机顺序启动；停止快照及父链只读，独立 RAM 写层、无外网，不操作宿主设置或用户应用。完整原始记录、父链身份及停止子盘归档保存在 `dist/released-0.14.0-cross-focus-20261030`；不是新的 Ubuntu Xorg 登录测试。

跨窗 fixture 使用两个独立 Chrome 154 进程/新 profile 和本地自有 textarea，分别真实 Ozone Wayland 和 X11（后者在 Wayland 桌面中即 XWayland）。程序二进制及 sandbox 文件逐项审计，命令未使用 `--no-sandbox`；本轮没有重复 renderer seccomp 取样。Chrome 显式 `--gtk-version=3`，输入模块为 IBus；native 另有 `--enable-wayland-ime --wayland-text-input-version=3`。不是原封不动的用户 Chrome 配置，也未进入 DeepSeek/Codex。

实际包 `DefaultAutoOutputRouter(keyboard_for_desktop())` 在创建目标之前 prepare。一个 output_session 分三段发送固定公共文字 `甲é`、`Ω\n`、`乙丙`。第一段后自然打开另一协议的新窗口，第二段后正常关闭新窗口让原窗自然恢复焦点；没有 OS 强制激活、假 DOM focus 或剪贴板。期望两个窗口最终分别 `甲é乙丙` / `Ω\n`。切换期间夹具主动暂停下一段，等待真实焦点、身份和协议证明；所以这是受控分段跨窗，不是无暂停吞吐、任意切换时点或真实录音/ASR/润色全链路。

X11 每次真实按下前核对自有 PID/焦点；native 使用既有生产 Guardian 的测试 remote 注入 seam，沿用 parent/PID-start/协议/焦点和250ms新鲜度守卫。额外拒绝诊断只观察原守卫结果，不改变允许条件。仅在输出期间观察自有控件，产品没有新增焦点锁定策略。

## 实际结果

### Ubuntu24：限制明确保留

- `wayland/suite-keyboard-xwayland-baseline-*`：真实 XWayland GTK 基线完整22码点混合Unicode/换行，切到第二自有窗口且旧窗空；部分取消1字、1.3秒无迟发、清理通过。这是实际包 Session/本地固定服务/生成音频 pipeline，不是真实麦克风或云端。
- `keyboard-x-native-r2`：同一 keyboard task 在 XWayland Chrome 收到 `甲é` 2码点；切 native 后 `unsupported_compositor`，native 窗零字，无重放、无迟发、X map恢复。
- `auto-owned-native-x-r1`：显式安装并启用本包七资产后，auto 首选 owned IBus，native 窗收到 `甲é`；切 XWayland 后 `ibus_delivery_unknown` / attempts2，新窗零字，停止且不重放。**没有完成 native→X 的连续全部输出。**
- `auto-owned-x-native-r1`：XWayland 起始时选 keyboard，先收2字；到 native 仍因 GNOME46 原生键盘能力限制停止。
- `auto-fcitx-zero-x-native-r1`：owned disabled，真实 Fcitx 返回 `no_target` / accepted0 / uncertain=false / offset0，auto 确实转 keyboard；X窗先收2字，native 阶段因上述能力限制停止。只能称零发送回退发生，不能称24跨后端全部通过。

24 未再强行测试 unsupported native keyboard 的跨窗取消；已有真实 XWayland 部分取消。没有通过缩小字符集、放宽守卫或替换传输来制造 native 成功。

### Ubuntu26：键盘可跨，owned 自动路径仍有边界

- 同包 XWayland GTK 基线完整22/取消1通过，环境仍是 Wayland，不能误写成 Xorg。
- `keyboard-native-x-r4`：native→X→native，精确6码点 `[甲é乙丙, Ω\n]`；native4/4、X2/2按下释放，0守卫拒绝。
- `keyboard-x-native-r4`：X→native→X，同样精确6码点；native2/2、X4/4，0拒绝。两例 native map/group/modifier 与 X map 均恢复、无迟发/清理错误。
- `keyboard-native-x-cancel`、`keyboard-x-native-cancel`：第一窗2字，切换后的第二窗仅 `Ω` 1字即取消，无尾部LF或第三段，按下释放平衡、0守卫拒绝、1.3秒无新增。
- `auto-fcitx-zero-native-x`：owned disabled，真实 Fcitx `no_target` / accepted0 / uncertain=false / offset0，auto 转 keyboard 后 native→X→native 6码点完整精确，映射恢复且无迟发。
- `auto-owned-native-x`：owned enabled，native 起始选 IBus，先收2字，切 X 后 `ibus_delivery_unknown` / attempts2、X窗零字，无重放/迟发；与24一样，**不能完成 owned 起始的跨后端连续输出**。
- `auto-owned-x-native`：owned enabled，但起始 XWayland 选 keyboard，X→native→X 6码点精确完成。两方向能力不对称来自本次真实路由/接收记录；本报告没有修改路由或宣称已修复。

所有“精确收到”只是自有控件的 DOM 回读，不是生产获得目标 ACK。IBus unknown、已发送内容不可撤回、不可自动重放的原有语义保持；本轮也没有把 producer 屏障或40ms等待当作呈现确认。

## 必须保留的失败与控制条件

1. 24第一次 SSH banner 超时，仍保持同一启动进程等待；没有因启动慢反复启动客机。
2. 24 `keyboard-x-native-r1` 在发送前因私有 fixture 错把 `_send` 取自 driver 而非 KeyboardInput，AttributeError、0输入；修正测试 seam 后在新目录 r2 实测，产品未改。
3. 26 keyboard r1两例、x-native-r2、r3两例被严格 native guard 拒绝，均不是完整PASS。新窗口创建后尚无首份 DOM snapshot，私有 monitor 的 assert 退出，guard停留在旧X窗/失焦状态；r2 额外拒绝metadata显示旧PID与 allowed=false/backend_confirmed=false，而 parent/start身份匹配。修正仅为未就绪时继续发布拒绝状态并监控，未放宽250ms或任何身份/焦点条件。r4通过。旧fixture及拒绝快照保留。
4. 生成 monitor 修正时一次宿主 Python 片段语法错误、未写入新代码；随后的 r3 标签误继续运行旧helper，因此仍失败。该生成错误只在工具响应中出现，没有伪造一份原始 stderr 归档。原始 r3 数据与修正前 fixture 都保留，不算修正后样本。
5. `auto-fcitx-zero-native-x-cancel` **没有建立名字所指的零发送前提**：实际首段被 Fcitx 接收并送达2字；切窗后没有可用目标，等待至任务期限后 `expired` / `partial_input_failed`，不回退、不重放、无迟发。第二窗的取消callback没有触发，不能称 fallback cancellation PASS。
6. `auto-knownzero-native-x-cancel-r2` 显式禁止 Fcitx `wayland,waylandim` frontends，但实际仍有可用Fcitx上下文、首段仍 accepted2，随后同样期限停止。该条件不够排除其他 frontend，未证明真正 no_target；停止进一步强造条件。**真实零发送回退的正常跨窗已通过、keyboard跨窗取消已分别通过，但它们不能合并推导“真实零发送回退后的取消”已在该样本验证。**

汇总19份跨窗原始结果见 `raw/summary.json`；其中成功、能力限制、夹具失败和前提未成立均单独保留。所有公开固定文本只来自自有目标，不读取用户周边正文。Fcitx环境提示在每例末尾恢复；没有真实供应商凭据或云端请求。

## 源码身份、复现和剩余范围

成功r4及相应 keyboard-cancel / 正常fallback的 fixture SHA 是 `561aef50de6ef9cb1ab96803eb2542bc04e34c8532142c1d59c9449e365ab74d`。附 `reproduction/vm26/input/cross_runner-r4.py.txt`，已根据原始结果 hash 逐字节核对；最终含frontend控制的 runner另存 `cross_runner.py`，其 SHA 记录在后续原始结果中。早期24/r1失败未在结果内提前保存fixture hash，不将后来的文件冒充这些运行的密码学快照；附初始/修正前文件说明演变。

按 `raw/vm24/*.json` / `raw/vm26/*.json` command 字段顺序、`reproduction/control.py` 和 launch/QEMU/wrapper 配置复现。只能在新隔离目录/唯一容器名中运行，不并发两个桌面。先核对a79产物、冻结0a13源码、只读父链SHA；guest脚本实际 `/mnt/input/frozen` 对应该提交，不导入后来主分支。依赖父盘/停止快照以及Chrome资源在持久dist/既有build目录，不能仅凭此补丁独立重建整个系统。

新报告不覆盖真实DeepSeek/Codex、contenteditable跨窗、任意第三方应用/输入引擎、无暂停流式竞争、跨窗时每个可能取消点、真实麦克风/物理快捷键、真实供应商云端、20/40/80ms专项或非BMP字符。默认auto保持安全停止不代表已经满足用户所有当前焦点连续输入目标；尤其 owned native→X 的缺口和24 native keyboard限制仍然存在。

## 恢复与归档

两客机均恢复原完整V5七文件（逐字节hash比较）、原三项Shell设置、Wayland会话、stockMutter加载路径与 `xkb:us::eng` / `[('xkb','us')]`。最终审计无候选进程/cap/虚拟音频/held key，锁free、Fcitx无owner、FUSEgone。正常poweroff，QEMU/container退出0、PID0/OOMfalse；完整停止子盘gzip均全流解码核验，身份在各 `output/ram-overlay-archive.json`。guest `/tmp`、`/run` 为tmpfs时不会出现在磁盘归档；必要结果已写持久output，不声称整个RAM均归档。

`pins.json` 记录所附文件的原位置、bytes、SHA；带尾空白的日志副本采用确定性gzip，另记decoded原路径/bytes/SHA，`gzip -dc`可恢复。原dist日志不改。没有修改共享工作树、推送、发布或替换稳定入口。

## 关联功能及最终源码检查

随后实现的[显式 GNOME-owned R5 选择与源码桌面证据](../explicit-owned-r5-desktop-20261030/REPORT.md)单独记录原生 Chrome、取消、预编辑保护和安全清理回归。该功能不改变本报告所测发布包，也未消除 owned 起始切到 XWayland 后的 unknown 停止边界；旧 `ibus` V2 只保留配置路径，本轮未完成其成功桌面协议验收。关联功能独立通过 201 项针对性测试及 Ruff/格式检查，完整工作流应在包含两项变更的最终干净提交上执行，不能据此宣称新版本已经打包或发布。
