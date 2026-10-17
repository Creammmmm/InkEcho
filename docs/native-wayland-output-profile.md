# 原生 Wayland 输出耗时诊断（a15）

2026-10-18，本次仅测量和提出方案，没有修改产品代码、输入等待参数、包或稳定入口，没有提交或推送。

## 范围与方法

实测主机 Ubuntu 26.04、GNOME 50.1、Wayland；目标为自然启动的独立测试 Chrome 原生 Wayland textarea。使用实际 a15 包的解释器、依赖、`keyboard_for_desktop()` 工厂与 Guardian，包 SHA-256 为 `b92ffd979f2faa979a22e9fd9a0be8cd187607009bd42313ef34fd91e660a598`，产品来源提交 `27aef8c1ee6ac33cc152e8588cc83daa727d4533`。运行时审计包内 19 个模块来源；没有源码覆盖。

每例预备完整 100 字普通 BMP 混合文本，单次公开 `insert` 调用，不通过流式供给限速。另测 5 个字符各连续重复 20 次，和完整 100 字途中实际第 8 次按键成功后取消。正常例要求 DOM 精确回读、实际 press/release 平衡、守卫零拒绝、返回前及最终 native/X 映射恢复、0.5 秒无尾随输入、原 Chrome 正常关闭和原 owner 等待退出。仅操作自有测试字段；没有剪贴板、输入法、麦克风、密钥或云端访问。

`on` 使用测试专用的内存方法包装器和 `perf_counter_ns` 数值账本；`off` 使用相同测试工具而不包装内部计时方法。没有修改原方法参数、调用次数或等待时长。原 sleep 按实际 `_key`/`_release_key` code object 匹配，转发原 sleep。异步任务按实际 task 身份划分嵌套，避免 monitor 任务被算作 key 的子调用。正常时数值只在退出时落盘，不保存文本、按键值或映射正文；失败守卫才额外输出一次诊断数值。

互斥账本从父层公开 insert 起止区间裁切：每个 worker span 扣除同任务直接子 span，worker 区间取并集；父路由/诊断和请求余量只计 worker 并集之外的部分。父请求包含 worker 时间，不能再次相加。`refresh_snapshot` 指实际 EIS keyboard 解绑/重绑及重新等待初始状态，不是普通内存快照。SetKeymap ACK 仅指该 D-Bus 调用返回，不代表目标应用已经消费输入。

工具与原始数值位于 `build/native-timing-r1/`：`profile_entry_r2.py`、`timing_ledger.py`、`profile-preview-r2.json`、`profile-preview-r3.json`、各原 owner/terminal/preservation、各 `*-result.json`、`*-summary.json`。普通混合样本的摘要由 `aggregate_profiles.py` 与 `summarize_profile.py` 读取生成。这里测的是实际 a15 产品与依赖加测试包装器的执行，不能描述为未经插桩二进制的内部耗时。

## 测量结果

100 字普通混合样本当前需要约 **10.2 秒，约 9.8 字/秒**，所以能明显看到逐字跳出。下面是各次公开 insert 起止时间，包含 begin/finish、守卫和父层开销；不含浏览器启动、包审计和准备就绪时间。

| 样本 | on：插桩（ms） | off：不插桩（ms） |
|---|---:|---:|
| 普通 1 | 10375.815 | 10215.606 |
| 普通 2 | 10135.143 | 10224.323 |
| 普通 3 | 9980.276 | 10354.630 |
| 普通中位数 | 10135.143 | 10224.323 |
| 连续重复 100 字 | 4111.697 | 4135.899 |

普通 on 范围 9.980–10.376 秒，off 范围 10.216–10.355 秒；样本太少且时间交错，不能把 on 略快解释为插桩提升性能，也不能可靠估计插桩开销。on 的逐字 Guardian.key 中位数分别为 101.940、100.214、100.461ms；各样本 p95 为 115.176、110.133、109.624ms，首字发送为 81.088–94.014ms。逐字分布是同一事务内观测，不是独立事务分布。

三次普通 on 的互斥耗时如下。每列取各样本均值及范围，总平均 scope 为 10163.745ms；逐样本纳秒账都精确回到账面 scope，差额 0ns。表中不是嵌套 span 的简单累加。

| 互斥归属 | 平均 ms/100 字 | 占总均值 | 三次范围 ms |
|---|---:|---:|---:|
| map settle 实际 sleep | 3043.057 | 29.940% | 3042.236–3043.795 |
| release 实际 sleep | 3022.386 | 29.737% | 3021.694–3022.928 |
| SetKeymap ACK：compositor 处理及 D-Bus 往返总时 | 2757.402 | 27.130% | 2634.423–2936.782 |
| 逐字 keymap 编译/序列化 | 312.645 | 3.076% | 292.454–325.777 |
| 初始 keymap 编译 | 7.744 | 0.076% | 7.256–8.008 |
| EIS refresh 解绑/重绑 | 194.115 | 1.910% | 172.161–207.648 |
| 普通 snapshot 自身 | 6.523 | 0.064% | 6.375–6.631 |
| wait_snapshot | 10.097 | 0.099% | 9.466–10.453 |
| refresh snapshot 扣除子调用后的余量 | 5.919 | 0.058% | 5.638–6.225 |
| source 查询 | 168.243 | 1.655% | 158.979–177.923 |
| press ACK | 155.398 | 1.529% | 152.110–159.434 |
| release ACK | 128.010 | 1.259% | 125.436–131.294 |
| SetMap memfd/调用前后准备 | 15.802 | 0.155% | 14.913–16.737 |
| 诊断 guard/count 文件 IO（互斥份额） | 112.538 | 1.107% | 111.644–113.664 |
| worker begin/key/finish 内部未细分余量 | 70.460 | 0.693% | 68.552–72.353 |
| Hybrid 路由（worker 区间外） | 44.569 | 0.439% | 41.689–46.868 |
| 父请求剩余，含 IPC/排队等 | 100.133 | 0.985% | 98.424–101.422 |
| 其余外层测试余量 | 8.704 | 0.086% | 8.550–8.821 |
| 总计 | 10163.745 | 100% | 9980.276–10375.815 |

**两种实际 sleep 合计约 59.7%，SetKeymap ACK 约 27.1%，是主要串行成本；EIS refresh 仅约 1.9%。** 每次普通样本实际 100 次逐字编译、100 次 map sleep、101 次 SetKeymap ACK（含最后恢复），没有相邻字符缓存命中。ACK 每次的中位数为 27.933–29.481ms、p95 为 33.111–39.996ms；这是 compositor 处理及 D-Bus 往返的总时，不能归因为纯总线延迟，尚未进一步区分 compositor 内部调度和执行。

等待常量没有改变，以下为实耗而非直接引用常量：三例各 1 次请求 50ms 的 map sleep 和 99 次请求 30ms 的 map sleep，合计实际约 3043ms；100 次请求 30ms 的 release sleep 合计实际约 3022ms。首例 map 30ms sleep 中位 30.213ms/p95 30.327ms，release 30ms 中位 30.212ms/p95 30.303ms。begin 与 finish 的包含式总时可在 summary 单独查看，不再叠加到上述互斥表。

连续重复样本实际只有 5 次逐字编译、5 次 map sleep、6 次 SetKeymap ACK；map sleep 170.868ms、SetKeymap ACK 152.518ms、release sleep 3022.282ms。这确认现有相邻重复缓存已经有效；4.112 秒结果不能推广为任意 100 字都能达到的速度。

取消例在完整 100 字请求中实际成功发送 8 字，905.235ms 返回：press/release 各 8、DOM 精确 8、0.5 秒无尾随、守卫拒绝 0、两 scope 及最终恢复通过。所有新 9 例均原 owner exit 0、正常 Browser.close、cleanup 空、保全哈希不变；最初 R1 的失败不算在这 9 个成功样本内。

并行 map settle/EIS rebind 的逐字可重叠量上限（每字取两者较小值再求和）只有 **201.500、195.829、166.480ms/100 字**，约 1.7–1.94%；还未扣除 join 后 fresh 校验的新增成本。因此该方案可研究，但无法解释或解决数秒级的大部分延迟。

## 复现入口

1. 核对上述版本化 AppImage SHA，以及 `build/a15-build-preparation/extracted-r1/squashfs-root` 的包来源；准备真实未锁定的主机 Wayland 会话，不用容器结果代替。
2. 查看 `build/native-timing-r1/profile-preview-r2.json` 的首个 on 例和 `profile-preview-r3.json` 的后续 8 例。每个 `modes` 项完整保存实际 `argv` 与 `environment_additions`；解释器是包内 `usr/bin/python3 -B`，入口是 `profile_entry_r2.py`，关键参数为 `--instrumentation on|off --sample-kind ordinary|repeat --runtime package --artifact ... --artifact-sha b92... --package-root .../packages --backend native --field textarea --work-root <fresh> --output <fresh> --run-reviewed`，取消例另含 `--cancel`（工具在实际第 8 次成功 press 后取消）。应使用 JSON 中的**完整 SHA 与完整 argv**，不能把此处省略号当命令。
3. 对新复测使用独立空的工作/输出路径，预先创建公共父目录；以预览的环境增量叠加实际桌面环境，由同一个 Popen owner 串行启动、正常等待。原 `run-profile-single-r2.py` 与 `run-profile-remaining-r3.py` 是本次精确 owner 实现，它们故意拒绝覆盖既有 cohort/收据，不能直接重复运行覆盖历史。测试仅让自有页面自然获得焦点；不激活用户窗口，不放宽 guard。
4. 正常完成后读取 `*-result.json`、`*-terminal.json`、`*-preservation-after.json`、`formal-baseline.json`、`worker-profile.json` 和 `parent-profile.json`。用 `.venv/bin/python build/native-timing-r1/aggregate_profiles.py` 重建本次聚合数值，或 `.venv/bin/python build/native-timing-r1/summarize_profile.py <某例-work>` 重建单例互斥账。本次聚合保存为 `aggregate-results-r3.json`。这些是本机 ignored 诊断材料，不是新产品功能或可从干净 clone 自动取得的发布验证器。

## 可行优化方向（未实施）

1. **事务内有界编译结果缓存。** 当前相邻相同字符已有复用；可进一步以事务原映射、group 和字符为键缓存编译字节，减少非相邻重复字符的编译成本。缓存不得跳过每次 source、映射、group 和 modifier 检查，不得跨不匹配事务复用。收益上限受实测每 100 字约 0.31 秒的编译时间约束，对每字不同的文本帮助有限；有合适非相邻重复时也只是约 0.1–0.3 秒量级的候选收益，必须另测，不能宣称已经提速。
2. **在 SetKeymap ACK 后并行等待 map settle 与 EIS refresh。** 按键仍须同时满足原 30/50ms 等待和刷新完成，并在 join 后执行最终 fresh modifier/map/group/source 边界校验，release 30ms 保持不变。潜在收益上限是这两个阶段可重叠的较小者；取消时必须使旧刷新结果失效并完成清理，不能把 observer ready 当成应用消费 ACK，不能重放未确认输入。此方向须实验证明而不能直接减少等待。
3. **多个安全空槽的批量映射，属于新的阶段 0 可行性验证。** 它可能减少 SetKeymap 和 map settle 次数，因而比父层微优化更有潜力。但当前只有 AE13/132 被验证可用；历史多槽 20/28 方案失败，不能认定已可用或承诺翻倍。须逐槽验证 native Chrome、GTK、VTE 的物理 keycode 行为、空槽状态、Unicode、取消及精确恢复，再评估有限批量方案。

不建议依据本次结果直接降低原等待。历史已有丢字证据，SetKeymap 返回与 EIS ready 均不足以证明应用已经消费按键。父进程约百毫秒级余量也不应被当成十秒级输出的主因。

## 失败与恢复记录

最初 R1 的未插桩首例在实际首字发送前守卫拒绝：press/release 均 0，guard rejection 1，随后 `cleanup_pending`，没有有效性能样本。整组立即停止，未将失败重试计作通过。正常 Browser.close 关闭自有 Chrome；一次正常停止信号未使自有 Guardian 退出。只读观察真实 depressed/latched 均为 0；gdb attach 被系统 ptrace 权限拒绝。经明确的失败清理授权，仅对该自有诊断 worker 强制清理，原 owner 实际等待并记录 worker -9、parent/cohort 1；这不属于正常产品恢复成功。

清理后发现本次占用的 AE13 槽仍在。仅在内存移除唯一且精确匹配本次首字符的 AE13 块后，编译出的候选 SHA 与此前 a15 实包验收的原映射 SHA **逐字节完全匹配** `6b19630e18f35206efdf196a5a5a36c9768b1b838e7862ff157610b02216c192`。经有限恢复审查，再核当前映射及 0 depressed/latched 后仅 SetKeymap 一次恢复该精确基线；新的独立只读会话再次确认同 SHA、group 0、空槽兼容、正常关闭。没有修改用户 input-sources、gsettings 或模拟释放用户键。原失败和所有异常清理收据保留。

失败原因尚未完全定位，不能仅凭现象认定是锁屏、焦点或生产逻辑故障。检查时 ScreenSaver.GetActive=false，实际 Wayland session 的 LockedHint=no。后续新样本仅增加 scope 外两份 fresh focused 状态、间隔 100ms 的就绪确认，并把正式基线元数据在输入前保存；没有取消或放宽守卫。

## 限制

这是单台主机、单个原生 Chrome 字段的小样本性能诊断；普通样本 3×100 字并非 300 次独立应用可靠性试验。未据此验证其他应用、GTK/VTE、物理快捷键、麦克风、云端或 Ubuntu 24.04 的性能。未实施优化，未产生新包。稳定/a14/a15 包、sidecar 和用户 3 个配置文件的哈希在测试前后检查保全；恢复事项须与通常成功例的自动清理区分。
