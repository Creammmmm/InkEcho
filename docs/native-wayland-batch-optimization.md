# 原生 Wayland 双槽预映射：源码验收

2026-10-18，在 Ubuntu 26.04/GNOME 50.1/Wayland 的自有原生 Chrome textarea 中，100 字普通混合文本从基线均值 **10.058 秒降至 7.064 秒，耗时减少 29.766%**。这里采用两个已验证的空物理槽，一次只发送当前一个字符；下一字符只用于准备映射，不自动输出。没有降低 first-map 50ms、后续 map 30ms 或 release 30ms 等待。

本页记录构建新版本前的**冻结源码试验**，a16 包验收另页记录。这里使用原 a15 包的解释器和依赖，不能冒充新 AppImage 验收，不能替代同一新包在 Ubuntu 24.04/26.04 的双系统门。没有在本实验中读取密钥、录音、请求云端、使用剪贴板或系统输入法，也没有控制用户应用、修改用户配置或覆盖稳定入口。

## 采用的修改与边界

- `Keymap.prepare(current, hint)` 最多映射 current 和一个 hint：原有 AE13/xkb132（evdev124）与额外 AB11/xkb97（evdev89）。只使用原图全 group/level symbols 为空的槽；132 原槽占用仍拒绝，97 非空则退回原单槽，不覆盖其它键。
- parent 只从本次已完整预检的 insert 文本取紧邻一个字符作为 hint，不在 newline 请求或 newline 前发送 hint。hint 必须为一个支持的普通 BMP 字符，空串、超一字、换行、非 BMP、bool 和其它错误类型均在新输出前拒绝。
- Guardian 仅在当前 value 命中已确认映射表时省去 SetMap；每次真实字符仍执行原 source、两次 snapshot、group/map/modifier、取消和 deadline 检查，且 ACK count 永远为 1。hint 失配时，为当前字符及本次可选新 hint 重新准备映射，但只发当前字符，不重放任何已发送或未确认文字。
- 映射表最多保留两字；stop、错误和 `_clear` 清除它。finish 恢复原图，跨 native/X 后端先结束旧映射 scope，hint 不成为后台队列，也不触发额外输入。

没有采用下述第一阶段编译缓存或并行 refresh 候选；最终 worker 从基线串行逻辑改双槽，未附带无实测收益的复杂性。

## 来源与复现

基线为提交 `820ca56` 的完整 44 产品文件。候选为同一基线上三个模块的修改；两份 frozen source 位于 `build/native-batch-r1/source-{baseline,candidate}/src`，不是可变开发树。独立 registry/manifest 固定完整 44 文件及四关键模块 pin，运行时核 19 模块实际来源和原 a15 完整依赖 inventory。

| 来源 | SHA-256 |
|---|---|
| baseline manifest | `62f605c2976b7656d1cd646e05f46a433e85578c5b6f6c4f2c0436a625112bb5` |
| candidate manifest | `b5e8bd7f6be0eb2187d20326f742ffa59aecf0ecf09e07034edef63d21e1e204` |
| candidate wayland_keyboard.py | `211be9ad3d85571341e6dbf895df16d6326a2149eb7151b34a7270c820ef1f01` |
| candidate wayland_worker.py | `e5518948050e5a08c8106b9ba9345f881bd3b83370691a3ac203e6697aac3820` |
| candidate wayland_keymap.py | `aa9087a2b1f6224431c343fcc5ff94ad330a9a77ce89133dd0c571f13226501a` |
| a15 dependency AppImage | `b92ffd979f2faa979a22e9fd9a0be8cd187607009bd42313ef34fd91e660a598` |

每次先核工厂和真实 native 协议、私有目标 PID/start/父进程，再等待两份 fresh focused 状态，间隔约 100ms。在任何输出前把正式映射元数据保存到私有文件。所有原图均为 `6b19630e18f35206efdf196a5a5a36c9768b1b838e7862ff157610b02216c192`、group0、depressed/latched0；包、sidecar 和用户三个配置的测试前后哈希保全。

可复现入口在 `build/native-batch-r1/`：

1. `preview-first-r1.json` 与 `run-first-r1.py`：首候选 100 字；`preview-remaining-r1.json` 与 `run-remaining-r1.py`：后续 14 例。完整 argv/env、依赖包、frozen source/manifest 及工具 SHA 都在 preview。使用实际包内 `usr/bin/python3 -B`，参数明确 `--runtime source --source-root ... --manifest ... --manifest-sha ... --package-root ...`；不能使用 `--runtime package` 描述此试验。
2. `preview-cancel7-r1.json` 与 `run-cancel7-r1.py`：完整 100 字请求中实际第 7 次成功 press 后取消。测试 probe 仅将其原 [:8]/<8/!=8 三处阈值改为 7，产品源不变。
3. `preview-mixed-r1.json` 与 `run-mixed-r1.py`：两个方向的受控 native/X 正常与 cancel14。`source_factory_mixed.py` 复用已审 factory helper，仅改真实冻结 source 审计、就绪稳定与正式基线保存。
4. 检查每个 `*-result.json`、原 `*-owner.json`/`*-terminal.json`、`*-preservation-after.json`、`formal-baseline.json`、`actual-operation-counts.json`。`aggregate-r1.json` 记录前 15 例汇总。所有 runner 都禁止覆盖旧路径；新复测必须使用新工作/输出路径、重新固定 preview，同一个原 Popen owner 正常等待，失败立即整组停止。

这些 `build/` 文件是本机 ignored 的实验材料，完整命令与哈希可检查；它们不是已发布的可从干净 clone 自动获取的工具。正式产品模块及有意义的纯测试在 tracked 源码中。

## 实际结果

每次预备完整 100 字普通 BMP 文本，公开 insert 只调用一次，没有流式供给限速；测量从 insert 开始到返回，包含 begin/finish、父层和真实守卫。只记录数值计数/时长/公开合成样本哈希；编译和 SetMap 包装器转发原方法一次，不改变等待、映射或输入语义。没有沿用原互斥 profiler 跨任务计时来拼新结果。

| 普通 100 字 | baseline ms | candidate ms |
|---|---:|---:|
| 第 1 次 | 9947.866 | 7111.282 |
| 第 2 次 | 10256.148 | 6971.330 |
| 第 3 次 | 9969.547 | 7109.463 |
| 均值 | 10057.854 | 7064.025 |
| 中位数 | 9969.547 | 7109.463 |

普通样本每轮实际 compile **100→50**，SetMap ACK（含最终恢复）**101→51**；候选真实成功 press 的 evdev code 为 `[124,89]×50`，每个请求仍只发送一个字符。候选范围 6.971–7.111 秒、约 14.06–14.34 字/秒，基线范围 9.948–10.256 秒。小样本不能给出跨应用或跨主机的固定提速承诺，也不能把 300 字当作 300 次独立可靠性试验。

非相邻五字符循环控制组各一次：baseline 10015.363ms，candidate 6852.239ms，均精确 100 字。候选仍逐字符 release 30ms，因此不代表输出已瞬间完成。

| 候选兼容性/取消门 | 实际结果 |
|---|---|
| Chrome textarea 100 字 ×3、cancel8 | 100/8 精确；press/release 平衡，guard0 |
| Chrome contenteditable 100 字、cancel8 | 100/8 精确；normal 6976.945ms |
| 原生 GTK TextView 100 字、cancel8 | 100/8 精确；normal 7288.347ms |
| 原生 VTE raw PTY 100 字、cancel8 | 100/8 精确；normal 7238.048ms；没有启动 shell |
| Chrome cancel7，完整请求仍为 100 字 | 7 精确，7 press/7 release；compile4、SetMap5（含恢复），第 8 字仅为未发出的 hint |
| native→X 正常 / X→native 正常 | 两字段分别 10+13 / 10+13 精确，总数23，未重放 |
| native→X cancel14 / X→native cancel14 | 分别 10+4 精确，总数14，未发出剩余字符 |

GTK/VTE 的匿名 socket 读回包含约 5ms polling 成本，这两行只作兼容性门，不能直接与 Chrome 横向比较速度。所有取消例都有 0.5 秒无尾随观察。

混合后端使用**实际第 10 字 ACK/受控前缀边界暂停，启动新的自有目标并等待就绪后再继续**，不是无暂停竞态、任意焦点变化原子性或切换吞吐证明。样本第 5 字为 newline，不占物理映射槽；第 10 字会预映射尚未发出的下一 hint。此时 scope 转换仍恢复原图，再由真实新后端只输出对应后缀。普通无 newline 样本的奇数 cancel7 另覆盖“有未发出 hint 时取消”。

计数范围：首组 **baseline4 + candidate11 = 15**，再加 candidate cancel7 一例、mixed 四例，合计 **20 个成功源码 case**。全部 guard rejection0、press/release 平衡、精确回读、返回前 native/X scope 恢复、最终映射恢复、原 worker 与自有 target 等待退出0、cleanup 空、保全哈希不变。原失败未计入其中，也没有失败重试洗成通过。

## 前置研究与未采用方案

[原 a15 耗时诊断](native-wayland-output-profile.md)测得两种 sleep 约 59.7%、SetMap compositor 处理及 D-Bus 往返约 27.1%，EIS rebind 约 1.9%。据此先尝试了事务内 32项/4MB 编译缓存和 ACK 后并行 sleep/refresh，并保留 join 后新 source/snapshot 检查。

该阶段 `build/native-opt-stage1-r1/` 的 13 例源码对照全部输入正确和恢复通过，但没有证明 wall 提速：普通均值 baseline10195.264ms / candidate10141.677ms（约 -0.53%）；非相邻重复均值 baseline10019.271ms / candidate10074.473ms（约 +0.55%）。compile 分别 100→66、100→5，但 SetMap 仍101。决定**不采用**，候选源、测试快照、patch、13例 raw 和 `aggregate-r1.json` 保留，最终双槽实现不包含它们。

## 空槽阶段 0 与失败历史

只读枚举原图在 xkb code8–255 内的 17 个空槽，确认 97/AB11、103/JPCM、132/AE13 的全 group/level symbols 为空。`physical_evdev_name` 是 XKB 名称，枚举本身不是 Chrome 兼容证据。旧多槽 Chrome20/28 与 GTK28/28 的实验包含不同 Unicode/物理分支，不能替代本次直接 keycode 验证。

本次对 baseline820 仅把 `COMPATIBLE_CODES=(132,)` 一行改为 `(97,)` 的 44文件冻结源，在 Chrome、GTK、VTE 分别实际验证 100 字和 cancel8；六个有效门均通过，真实成功按键只用 evdev89。103 未阻塞此路径，也未声明兼容。

旧 VTE normal 首次输入其实已 exact100、计数平衡和映射恢复，但正常 close 的 target **exit -11**，整个 case 失败并停止，未执行当时的后续取消。其旧 raw 与原 owner 记录保留；提权只读确认旧 target/raw child 此后不存在，但没有旧 child 独立原 wait 收据，不能补写其退出0。最小 fixture 修正去掉额外 `widget.set_pty(None)`，让正常 window.destroy 负责释放；新 R2 两次空输入启动/close 均原 wait0，再执行新 VTE100/cancel8 均通过，未覆盖旧失败。不能据此认定某个 C 层双重释放根因已被直接证明。

此前 profiler R1 的 guard 拒绝及异常 Guardian 清理、精确 baseline 恢复记录保留在原诊断报告。新测试 seam 对**在调用 compositor 前已知未发送**的 press 拒绝，只抑制精确对应的未尝试 release，单独计 `suppressed_unattempted_release`；不增加成功 release。真正尝试远端后的未知失败仍发真实 release，没有修改生产的未知投递恢复门。另一次启动审批超时明确未执行，按工具允许仅重试一次，不属于输入失败或槽不兼容证据。

## 纯测试与未验范围

有意义的纯测试覆盖非法 hint 完整预检、最多两槽/去重/第二槽占用退单槽、所有实际 min/max keycode 的全部 group/level symbols 及结构不变、hint 不自动发出、提示失配、表命中仍检查真实状态、取消/过期无尾随、跨 native/X 恢复与不重放、stop/finish 清表、测试 seam 的已知未发送与真实尝试失败区别。相关 focused 组合 248 项由主 Agent 独立通过；真实 keymap 全边界比较21项亦单独通过。主 Agent 另在本工作树执行完整自动回归：Ruff check 全过、format 290 文件通过、pytest **1574 passed / 3 skipped，40.23s**。这是源码阶段工作树检查，不是某个 clean HEAD 的验证 receipt；提交后仍须按正式 workflow 生成当前提交收据。最终新包双系统门在具体产物上另记，不能用纯测试替代桌面证据。

未由本报告验证：其它主机/桌面、未列目标、真实麦克风、物理全局快捷键、真实云端、无暂停任意焦点竞态，以及新包的 Ubuntu24.04/26.04 交付。用户开始录音不捕获目标、输出按当时光标、焦点变化本身不取消的既有语义保持；bounded hint 不绑定将来的窗口，也不授权重放。
