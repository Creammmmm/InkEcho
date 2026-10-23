# 自适应输出节流：阶段验证记录

记录跨度：2026-10-23 至 2026-10-24。阶段 0 原始实验日期为 2026-10-23。状态：**首轮源码原型实现完成，实验验收未完成**。
基线 HEAD 为 `9875e0a8de8f765fcc08bf2f7cd53a4109a93a4a`，应用版本仍为
`0.9.1`。本轮修改保留在工作树，没有 commit、push、版本递增、打包、安装或发布。
用户于 2026-10-24 后续授权 GitHub release，本实现现以 0.9.2 准备提交；本文的 0.9.1 实验及“未提交、未发布”表述记录原始实验时点，不改变其源码 SHA、结果与限制。
本文不能作为新版 AppImage 或跨系统支持声明。结论是保留可审查源码原型和测量结果，
不是宣称用户故障已全面修复。短句候选有超过预定门槛的结果，当前 VM 的 `.18` Mutter
未重现历史 `.15` 环境卡顿；Ubuntu 26.04、XWayland DRAW、第三方应用、实际焦点切换
和负载矩阵仍未验证。不靠增加尾部固定停顿或放宽 200ms 门槛将其包装为验收通过。

## 目标与当前范围

按用户交接文档开发统一自适应节流控制器，改善最终确认文字输出时长时间不重绘的体验。
不优化云端识别，不输入未确认草稿，不使用剪贴板或系统输入法，不修改第三方窗口帧同步。
输出跟随当时光标；焦点变化不取消，主动取消、过期及替代必须停止后续正文，状态不明的
输入不得重放。

统一控制器位于 `src/inkecho/platform/output_pacing.py`，能力明确区分：

| 反馈等级 | 可用于调度的事实 | 本轮状态 |
| --- | --- | --- |
| NONE | 无有效反馈，有界保守节奏 | 控制器离线覆盖；桌面降级矩阵待验 |
| INPUT | 请求/ACK、映射设置和读回的输入链路进展 | 原生 Wayland 已最小接入；26.04 实测待验 |
| DRAW | 外部可见的目标绘制进展提示 | 24.04 Xorg 外部观察初门通过；生产适配器与键盘集成已实现；38 字候选已实测，但未通过全部预定目标 |
| 呈现 | 合成器提交或实际呈现进展 | 本轮没有实现或取得第三方目标此级能力 |

控制器具有有界在途预算、反馈合并、超时退让、映射成本区分、固定绝对 deadline 和
代际隔离。弱绘制提示不等于任何字符已显示，不能将光标闪烁或动画累计成未来的发送额度。
目标代际替代使用独立 `PacingScopeChanged`，不得冒充任务取消；主动失效、真实取消和
deadline 仍保持硬停止。后端必须在等待后重新检查任务与当前路由，再实际发送。

X11 生产适配器 `src/inkecho/platform/x11_feedback.py` 与 `keyboard.py` 的集成已经完成，
**已取得一例 38 字候选实测，但尚未通过全部性能验收目标**。适配器在同一事件循环线程使用键盘驱动现有
Display，串行复用 `driver._checked()` 错误捕获，不另设线程或长期全局 X error handler。
优先使用第二个扩展 XSync counter 的自有 Alarm，允许只有计数器或只有 Damage 的弱
DRAW 提示；能力缺失则返回 NONE，不改目标 counter 或窗口管理器协议状态。

观察器只在自身连接选择所需 mask：顶层窗口结构/属性、root active-window 属性及当前
子窗口焦点事件。焦点 revision（包括离开后回到同一窗口）使旧等待代际失效；事件只影响
调度，实际接收位置仍由每次当前焦点决定。每次最多处理 64 个排队事件，仍有积压时
丢弃反馈并降为 NONE，避免埋在积压后的焦点事件导致旧窗口进展被当作新窗口额度。
结束/失败/取消释放自有 Alarm、Damage 及自身连接的监听 mask，清理异常不阻挡按键和
映射恢复。此实现不等于已验证所有目标销毁或负载情形。

键盘路径在映射前节流，避免先改映射再等由该改动阻塞的绘制而自锁；只对实际映射改变
支付 MAP settle，真实缓存复用不再支付虚构的映射等待。首映射 100ms、实际后续映射
至少 20ms、按下/释放各 10ms 底线仍保留。无观察能力的 NONE 采用有界保守映射间隔，
默认 60ms；它不是“每个字符固定 60ms”，也不是基于硬编码 60ms 即宣称自适应成功。
缓存与实际映射成本分别处理，绘制提示无效时有限超时降级，不能永久等待或重发正文。

原生 Wayland 保持每 key 一个请求在途及既有首映射 50ms、后续映射 30ms、释放 10ms
底线。父进程只按 INPUT RTT 自适应拥塞退让，正常基线无额外等待；实际映射、缓存命中及
旧 worker 分桶学习，避免把正常映射成本当成拥塞。成功 ACK 的可选 `input_feedback`
只包含布尔值和有限非负秒数，不包含正文、映射内容或原生目标窗口 ID。非法辅助反馈
（包括 None、NaN、无穷和巨大整数）丢样本并重置学习，不改变已经成功交付的必需 ACK，
不重放。映射所有权、修饰状态、按键释放、迟到回复与清理边界保留。

**XWayland DRAW 本轮未启用、未验收。** Xorg 的计数器和 Damage 结果不能外推至
XWayland；原生 Wayland 的 INPUT ACK 不能外推为目标 DRAW。普通客户端不能借自身
`wl_surface.frame` 或 `wp_presentation` 观察其他应用。

## 阶段 0：独立进程外部观察

实际环境是现成专用 VM：Ubuntu **24.04.5**、GNOME 46、Xorg `DISPLAY=:0`，
GTK3 `3.24.41-4ubuntu1.3`，Mutter `46.2-1ubuntu0.24.04.18`。
这与交接历史实验的 Ubuntu 24.04.3 / Mutter `.15` 不同；不能跨环境拼接性能结论。
本阶段未操作主机用户桌面，未改系统配置或第三方程序。

独立观察进程有自己的 X 连接，核对自建目标 PID/start-time/XID，协商 SYNC 3.1 和
DAMAGE 1.1，读取两个 `_NET_WM_SYNC_REQUEST_COUNTER` 中的第二个计数器；创建和销毁
自己的 Alarm/Damage，只清自己的 Damage region。不修改目标计数器、窗口管理器 Alarm
或帧同步设置。内部 after-paint 仅用于受控实验对照，不充当生产外部能力。

每例从观察器就绪开始记录约 3 秒：

| 自建目标场景 | 文本 changed | 内部 after-paint | 外部奇/偶计数通知 | Damage |
| --- | ---: | ---: | ---: | ---: |
| 定时追加固定公开 16 字 | 16 | 21 | 21 / 21 | 22 |
| 空编辑框与光标 | 0 | 5 | 5 / 5 | 6 |
| 空编辑框与 GTK spinner | 0 | 2454 | 2444 / 2444 | 2445 |

定时文本准确；changed 到 after-paint 中位 0.632ms、最大 0.980ms，活动区间最大绘制
间隔 101.099ms；长度 1 至 16 均出现 after-paint。内部绘制与最近外部偶计数通知时间差
中位 1.084ms、最大 1.944ms。这只是时间接近，不是逐字符因果对应。

空目标和动画均产生大量进展，明确证实误报边界。通知数不是字符数、完整帧计数或物理刷新
频率。每例 Alarm/Damage 销毁的 X error 均为 0，连接关闭返回 0；先停止观察器再关闭
目标，六个原始目标/观察进程自然退出 0，stderr 为空。

初次 `raw-r1` 因 ready 审查时目标自然超时、缺少 GI Cairo converter 而无有效内部绘制
证据；目标销毁后 Damage destroy 有 1 个 X error。该失败保留，不能合并为无条件清理成功。
阶段 0 独立探针使用独立 XSetErrorHandler，不能直接复制到产品另一个线程。本轮生产
集成采用前述同事件线程、同 Display 串行复用 driver._checked 的协调方式；实际候选性能
和清理验收仍待后续实验。

## 未改生产 XTest 路径的 20ms 基线

`raw-keyboard-r3/mixed20-r2` 使用固定公开 38 字中文/ASCII/标点样本，生产 XTest
路径保持原 20ms MAP 等待；目标为自建 GTK3 控件。旧 0.9.0 AppImage 提供 Python 和
依赖，sender 明确加载冻结的基线源代码，**这不是旧包或新包的验收**。

| 指标 | 实测 |
| --- | ---: |
| sender begin 至首字 | 109.336ms |
| 首末字符发送跨度 | 1759.641ms |
| 字符间隔中位 / 最大 | 46.604 / 60.641ms |
| 最大 after-paint 间隔 | 139.218ms |
| 最终正文准确性 | 38 / 38 |
| sender press / release 调用 | 38 / 38 |
| 映射写入 / MappingNotify | 21 / 20 |

root 已实际检查长度 12、25、38 的自建窗口中间像素前缀。此例保持可见推进，
**没有复现历史“整句集中出现”**；不能据此声称问题已消失或自适应优于基线。
映射逐项恢复；sender、observer、owned target 按本例清理记录自然退出 0，观察器
Alarm/Damage 销毁错误均为 0。GTK widget 层记录到 press 8、release 38，
不是原始键盘事件全量观测，不能用它判定按键不平衡或替代 sender 的调用计数。

## 同环境 60ms 保守基线补记

随后完成同一 VM、相同冻结生产源码与 38 字混合样本的
`raw-keyboard-r3/mixed60-r1`，仅在实验进程内将 MAP 等待设为 60ms，未改生产文件。
下表的首字以 sender `begin` 至第一次 press 为口径，发送跨度为第一至最后 press：

| 指标 | 20ms：mixed20-r2 | 60ms：mixed60-r1 |
| --- | ---: | ---: |
| 首字延迟 | 109.336ms | 103.755ms |
| 发送跨度 | 1759.641ms | 3456.273ms |
| 字符间隔中位 | 46.604ms | 93.589ms |
| 最大字符间隔 | 60.641ms | 107.737ms |
| 最大 after-paint 间隔 | 139.218ms | 103.983ms |
| 最终正文准确性 | 38 / 38 | 38 / 38 |
| sender press / release 调用 | 38 / 38 | 38 / 38 |
| 映射写入 / MappingNotify | 21 / 20 | 21 / 20 |

root 已实际检查 60ms 例的 25 字像素前缀，并审阅原始 sender-process 和 observer
cleanup JSON。sender 4599、observer 4598、owned target 4451 的原始 wait 为 0，
stderr 为空，映射精确恢复，own Alarm/Damage 清理 X error 为 0，连接关闭返回 0。
这些 PID 只用于识别历史记录，不能在后续发送时复用。GTK 控件层仍仅观察到 press 8、
release 38，不能冒充原始按键平衡数据。

两例基线均有顺滑推进。20ms 相对 60ms 的发送跨度缩短 **49.1%**；以相同发送数量除以
发送跨度计算，吞吐量提高约 **96.4%**。两者是不同指标，不能把跨度缩短百分比称为吞吐
提升。这是各一例的固定等待基线对照，不是自适应候选结果，也没有复现历史整句卡顿，
不能据此宣布修复或完成候选验收。

## 额外固定基线控制：缓存复用与无外部观察器

同一冻结基线追加两例，仍不是自适应候选：

| 场景 | 首字 | 发送跨度 | 间隔中位 / 最大 | 至最终正文的最大绘制间隔 | map / notify |
| --- | ---: | ---: | ---: | ---: | ---: |
| repeat20-r1，重复 38 字、有外部观察器 | 103.785ms | 1778.560ms | 47.599 / 52.925ms | 52.878ms | 2 / 2 |
| mixed20-noobserver-r1，混合 38 字、无外部观察器 | 107.978ms | 1755.624ms | 46.441 / 66.537ms | 64.789ms | 21 / 20 |

两例正文均精确 38 字，sender press/release 均 38/38，映射恢复。repeat sender/observer/
owned target 原始 wait 均 0；无观察器例仅 sender/target 原始 wait 为 0，其 observer
字段为 null，不能写成观察器退出 0。两例没有通过 GTK widget press 计数推断底层平衡。
最终正文首次 after-paint 分别发生在最后 release 前约 5.971ms、9.231ms，负差值表示该
受控接收器绘制早于最后释放，不是负处理耗时或物理呈现确认。

混合文本无外部观察器时仍有绘制推进，故本次基线顺滑不能归因于外部观察器“治好了”
卡顿；单次差分也不能量化它在所有负载下的性能影响。重复字符减少映射写入，但基线
仍逐字支付 20ms MAP 等待，不能据此代替新生产缓存路径的验收。

## 自适应候选 38 字：已实测，未通过全部预定门槛

`build/adaptive-output/raw-candidate-r1/adaptive38-r1` 绑定冻结 source manifest
`9542931fed56dccde19b57ec08ebc090ab4202a33f52c843f3b5154fedfa8505`，
keyboard SHA-256 为 `0591a43fb66bbbe05060bd7064d9c7aac69bd3bb678455e8a398b66a333a1362`。
实际生产 DRAW 使用第二 counter + Damage，bind 耗时 0.396ms；没有拿测试窗口内部
绘制回调驱动控制器。root 已实际检查 12/25/38 字像素前缀。

| 候选指标 | 实测与门槛判断 |
| --- | --- |
| 首字 | 107.110ms；低于 200ms，较 20ms 基线未增加 |
| 发送跨度 | 2271.080ms |
| 字符间隔中位 / 最大 | 35.180 / 149.100ms |
| 最后 release 至首次完整 38 字 after-paint | 173.563ms |
| 37 字 paint 至完整 38 字 paint | 约 204.35ms，**超过预定 200ms 最大绘制间隔目标** |
| 正文 / sender press / release | 38 字准确；38 / 38 |
| map / MappingNotify | 21 / 20 |

绘制停顿统计覆盖到最终完整正文，不能只截到末字输入后 100ms，把最大间隔报告成约
149ms 并称通过。原始 37 字 after-paint 时间为 2653.685626293，首次 38 字为
2653.889977710（同机 monotonic 秒），相差 204.351417ms。

相对同环境 60ms 基线，候选发送跨度缩短约 **34.29%**；相对 20ms 基线跨度反而增加约
**29.1%**。因此不是所有性能目标均已通过，不能把相对保守基线的加速概括为修复完成。
本例结束正文稳定观察约 1.250s，是普通成功任务的尾部观察，**不是取消测试**。
后续长句和首字后取消结果在下文独立补记；切焦点及负载情形仍待验证。

sender 5659、observer 5658、owned target 5512 原始 wait 为 0，stderr 为空；映射
精确恢复，自有观察对象清理错误为 0、连接关闭返回 0。与固定基线相同，GTK widget
press 8/release 38 不是底层事件平衡的全量证据。没有操作真实用户目标或声称跨应用兼容。

## 114 字候选与 60ms 基线

同一冻结 source manifest 的 `raw-candidate-r1/baseline114-60-r1` 和
`adaptive114-r1` 使用 114 字公开混合样本；root 已实际检查候选 38/76/114 字像素前缀。
候选生产 DRAW 为 counter + Damage，bind 耗时 0.358ms。

首字有两个不同起点，不能混用：`begin` 标签在连接完成、实际 `insert()` 调用之前，
并非启动全部输出准备之前；`prepared` 标签更早，涵盖其后的连接等准备。以下同时列出，
与前述 38 字基线比较的“首字”均使用 begin→第一次 press 口径：

| 指标 | 114 字 60ms 基线 | 114 字自适应候选 |
| --- | ---: | ---: |
| begin 至首字 | 102.782ms | 115.360ms |
| prepared 至首字 | 103.670ms | 116.276ms |
| 第一至最后 press 跨度 | 10553.752ms | 6514.576ms |
| 字符间隔中位 / 最大 | 90.417 / 113.001ms | 33.001 / 143.257ms |
| 至首次完整 114 字的最大绘制间隔 | 110.096ms | 143.838ms |
| 最后 release 至首次完整正文 paint | -9.399ms | -9.751ms |
| 正文准确性 | 114 / 114 | 114 / 114 |
| sender press / release | 114 / 114 | 114 / 114 |
| map / MappingNotify | 58 / 57 | 58 / 57 |

本候选相对同长度 60ms 基线的发送跨度缩短 **38.27%**，只有各一例；并不是重复性或
不同负载下的保证。114 字候选的 143.838ms 最大绘制间隔低于 200ms，但没有同长度
20ms 基线，不能用 38 字首字对照代替长句首字增加量门槛，也不能让此例覆盖 38 字候选
已观察到的 204.35ms 超标。最后 paint 的负时间差表示正文在最后 release 前已绘制，
不等同显示器实际呈现。

两例原始 sender/observer/target wait 均为 0、stderr 为空，完整映射精确恢复，自有观察
对象清理错误均 0、连接关闭返回 0。记录中的 GTK widget press 24/release 114 依旧不是
原始键盘事件平衡证据。剩余焦点、反馈失效、负载和跨应用矩阵继续待验。

## 首字后取消：无后续正文

`raw-candidate-r1/cancel38-r1` 使用实际生产 DRAW，首字回调触发取消发送任务；
这是输出取消测试，**不是物理 ESC 或全局取消快捷键实测**。root 实际检查最终自建目标
只保留首字符「这」。

sender 仅 1 press/1 release，map 写入 3 次、MappingNotify 2 次，receiver 最终长度 1、
`exact_prefix=true`、`exact_text=false`；后者符合未发送完全文本的取消预期，不能当作正文
错误或将其改成全句成功。取消后的 sender 尾部观察为 1.250101s；独立 receiver
记录 131 次 heartbeat，时间跨度约 1.363702s，长度始终不超过 1，没有尾部正文。

sender 6580、observer 6579、target 6436 原始 wait 为 0、stderr 为空，映射精确恢复，
实际 DRAW bind 与正常关闭的自有观察对象清理错误均为 0，连接关闭返回 0。此结果
验证该一次首字后主动取消的输出边界，不外推成所有等待时点、任务替代、ESC 或新目标
切换均已实际通过。

## 仅探针尾部 hold 诊断：不能作为修复因果证据

`raw-candidate-r1/tailhold38-r1` 使用未改变的候选 source manifest `9542931…fa8505`，
只更换实验 sender `tail_hold_output_sender.py`（完整 SHA 在下表），在 insert 返回后
额外保持 output scope 约 250ms。此 hold **没有加入生产代码**，也没有引入生产 finish
等待或修改预定 200ms 目标。

本例正文 38 字正确，begin 至首字 114.902ms（prepared 至首字 115.829ms），发送跨度
1999.081ms，最大绘制间隔 137.286ms，sender 38 press/38 release、21 map/20 notify，
映射及观察对象清理正常。但首次完整正文 paint 时间为 3239.372623967，已经发生在
hold begin 3239.392820336 **之前约 20.20ms**，也早于最后 release 约 9.846ms；
hold 实际约 257.8ms。因此不能把此例顺滑归因于 hold，它只是延长了 scope 清理时点。
单次差异不能推翻前一 38 字候选的 204.35ms 失败门。

## 预先冻结的探索目标与尚缺对照

后续自适应候选必须同时检查正文正确、按键与映射恢复、无取消尾部及资源清理，并探索：

- 最大绘制间隔不超过 200ms，持续出现中间可见进展；不要求每字一帧。
- 首字延迟不超过 200ms，且比同环境 20ms 基线增加不超过 25ms。
- 同环境吞吐量相对 60ms 保守候选提高至少 15%。

这是在候选运行前冻结的实验目标，**当前 38 字候选未全部达到**。交接文档中的 60ms 历史结果来自不同
环境，不能直接跨环境比较；本页新增的同环境 60ms 基线可作为后续对照，但不代表候选
已经实施成功。固定基线已有重复字符一例；候选已补长句一例与首字后取消一例，重复字符、重复运行、负载及其他取消边界
仍待补充。不得挑一次成功或只看 JSON passed=true 作为平滑性验收。

还须验证焦点切换/新旧代际、取消、替代、目标销毁、无计数器/Damage、光标与动画干扰、
反馈丢失以及自然清理。Ubuntu 26.04 原生路径与 XWayland 新机制实测均未完成。

## 证据定位与固定摘要

以下 `build/` 证据被 Git 忽略；路径不是发布产物，可能在清理后失效。
对应摘要用于辨别本次冻结证据，不能替代保存原始文件。

| 证据 | SHA-256 |
| --- | --- |
| `build/adaptive-output/result-summary-final.json`（最终不可变证据入口：9 例双首字起点、阶段、wait 与清理） | `221da614af94ac69551393f8c2bcf21bd9898ad343be9fecf610aa135051ccc2` |
| `build/adaptive-output/FINAL_EVIDENCE.md`（最终复现与证据索引） | `686cf3676340aa5ac190633c837eb02ea12e3c0b9bc4e431eb65334944dba331` |
| `build/adaptive-output/PASSIVE_RESULT.md` | `ebf86e400c2c41a9f88cbee5c5ba81ec41d468ec4e75e40c293f69d74f10dca2` |
| `build/adaptive-output/NATIVE_REVIEW.md` | `c5a5ef33cd5f8bf722b3a1281105d65df5b660ab9f8871de4cac213b27b39529` |
| `build/adaptive-output/raw-r2/summary.json` | `1b27e68365bab7dd6dbec208321f4a34b2a29a20445b6e3638bd95efaa7f7a29` |
| `raw-r2/owned_gtk_feedback_target.py`（同上 build 前缀） | `f63e3927702dd13725b8db04566050e2d4b247a2efffd22e42af61471f19cb54` |
| `raw-r2/x11_feedback_observer.py`（同上 build 前缀） | `cef7f12bd098570bd231789de854b2fff93a697e50ab711b2e85ff2bee6190ed` |
| `raw-keyboard-r3/mixed20-r2/sender.jsonl`（同上 build 前缀） | `a49f816e32b5313e079e228bd04fdf71cc3d63fd3dc00d4a2254e5ff41d98c15` |
| `raw-keyboard-r3/mixed20-r2/groundtruth.jsonl`（同上 build 前缀） | `a65eceb5d926b2c903c85acef6e32e36535aab61a8e449f27c460ebfe11a2c16` |
| `raw-keyboard-r3/mixed20-r2/external.jsonl`（同上 build 前缀） | `94c72aa0cb466b32bcf4064a12393a6f762c7abf8454709f63ba00dce4625792` |
| `raw-keyboard-r3/mixed60-r1/sender.jsonl`（同上 build 前缀） | `99721881240dc568a901bcc641ba86728fa2d2f7ba8582465a312d86df05abf3` |
| `raw-keyboard-r3/mixed60-r1/groundtruth.jsonl`（同上 build 前缀） | `561f030d8e80ec01646de63d2b4c4a551c11024e46e753f3bcd180b14a08e1de` |
| `raw-keyboard-r3/mixed60-r1/external.jsonl`（同上 build 前缀） | `d16478a318fc5c84fd4f2a3fc29da057e741e81adfd86dc817ebd5d9646e17c7` |
| `raw-keyboard-r3/mixed60-r1/sender-process.json`（同上 build 前缀） | `8ced4eebc43f3163bbd1642ac8b1ad381428170e2e33aad8f53d45250e85fb51` |
| `raw-keyboard-r3/repeat20-r1/sender.jsonl`（同上 build 前缀） | `608f34fc62521c1b7f14088699832a2813bfc19f08418732b587266fe78b63a0` |
| `raw-keyboard-r3/mixed20-noobserver-r1/sender.jsonl`（同上 build 前缀） | `679bbede9d69962c8ff7860f31435b8da7e546a79f22abdcbd948886f13da695` |
| `raw-candidate-r1/adaptive38-r1/sender.jsonl`（同上 build 前缀） | `f7717f7bfafbe8af55f363f5ce781df3000cee6b13f292e61cff6b853805760c` |
| `raw-candidate-r1/baseline114-60-r1/sender.jsonl`（同上 build 前缀） | `5944bac10a13fd99928e0065faac583d5e917de8bf4bb2d91eaf8bfa073d5819` |
| `raw-candidate-r1/adaptive114-r1/sender.jsonl`（同上 build 前缀） | `3acc0c31f7f8e15837bc9730c6507e1f56b700de5e60b3357d05bb5bb6b8b286` |
| `raw-candidate-r1/cancel38-r1/sender.jsonl`（同上 build 前缀） | `ad748b548cd1216874bd021fb555180ed0080a0afed9388aad0f0c3491a89661` |
| `build/adaptive-output/result-summary.json`（含尾部 hold 的最终汇总时点） | `0fc95b625c3651879e6547fef7121df924b2924e18157a7b66aafc494b08ad25` |
| `build/adaptive-output/cancel38-summary.json` | `ed7af254b20c1b16c62adf84a1b102d277e643a3ead6fc0083bbeda3a0352cfc` |
| `raw-candidate-r1/tailhold38-r1/sender.jsonl`（同上 build 前缀） | `b9985324d6b77a4ac7e912159239828d29867ce04c95d7198a7b3ac297ff4530` |
| `build/adaptive-output/tailhold38-summary.json` | `ea77ce6d3bf8e7c5d2f47d17efd0a90f0743316c4c05c16e77fb9decb7b44f4c` |
| `build/adaptive-output/final-pytest-r2.log` | `1a857ad31aad350ada16675eea1a717cffc7a9d50c4d2d092a0ae448d0a0320d` |

固定原始 JSONL/截图与可变汇总分开：上表 raw sender 的 SHA 不因后续摘要计算而变化。
`result-summary.json` 曾在 long/cancel 补记时为
`db5eb8fe60e8909ae0535af48cc67dd3a4148c93ec4f6c66330f2ffe7716e7f6`，加入 hold 后
变为表中 `0fc95b…ad25`；旧摘要不是同一份最终文件，不混用。原始逐例日志才是复核依据。

复现 helper 完整 SHA-256（均在 `build/adaptive-output/`，不是产品或发布文件）：

| Helper | SHA-256 |
| --- | --- |
| `run_passive.py` | `8f81dc2cfcc6f7b07413995e73da3c7ab53378e16a17a83918a98a4de78a278d` |
| `owned_gtk_feedback_target.py`（冻结 r2） | `f63e3927702dd13725b8db04566050e2d4b247a2efffd22e42af61471f19cb54` |
| `x11_feedback_observer.py` | `cef7f12bd098570bd231789de854b2fff93a697e50ab711b2e85ff2bee6190ed` |
| `owned_gtk_output_target.py` | `53342320d636d9db4fdf499948add34f2dc8bb676a8879da7e28c30caa2edf5d` |
| `owned_gtk_candidate_target.py` | `4d28dba87e51611fcf48de40191214423f76ebb67a34e403c3e4e232e3c7e82a` |
| `production_output_sender.py` | `bb753cedb10aef2e60d56b4696a25dc203c8ae35d7ca38d88fe678037b7670ed` |
| `adaptive_output_sender.py` | `33259d6dc2a7d21e866c317db379b40a13fea7415b788a339d4d6a1dde6db11b` |
| `tail_hold_output_sender.py` | `087af9849c67cbdd6f0e5a7d69057bcf3e0258a0107481c346d0f7f637cc23d0` |
| `summarize_output.py` | `fa99232f936ca5dddc6046b2e2b59f3b2022bfee4c24a4196790889277bd27cf` |

`PASSIVE_RESULT.md` 是阶段 0 被动观察时点的记录，其末尾“键盘尚未运行”是当时事实；
后续 mixed20-r2 结果按本页独立补记。`NATIVE_REVIEW.md` 的 235 项联合通过为原生适配
审查时点的离线结果，不等于此后 controller 改动的最终全量检查。

## 复现步骤与依赖

只在经 root 审查的隔离 Xorg 桌面运行探针，使用新工作目录，重新取得 PID/start-time/XID，
不能复用表内旧进程号。宿主机用户桌面不得直接运行以下输入实验。目标/观察器依赖系统
Python、GI GTK3、libX11、libXext（SYNC）、libXdamage；sender 另需 PySide6 和项目依赖。
未安装新系统包，不降低安全设置。现有 Python GI 缺 Cairo foreign converter，故用
frame-clock after-paint 对照而非 Python draw 回调。

最小复现形态如下；大写路径变量由被审查的实际冻结 source、依赖 runtime 和新工作目录
填入，不是可以向任意当前窗口直接粘贴执行的命令：

```sh
/usr/bin/python3 owned_gtk_output_target.py --mode manual --sample mixed --seconds 120 --work "$WORK"
/usr/bin/python3 x11_feedback_observer.py --xid "$OWN_XID" --pid "$OWN_PID" \
  --start "$OWN_START" --seconds 120 --stop "$WORK/observer-stop" \
  --output "$WORK/external.jsonl"
QT_QPA_PLATFORM=offscreen "$DEPS_PYTHON" production_output_sender.py \
  --source-root "$FROZEN_SOURCE" --ready "$WORK/ready.json" \
  --output "$WORK/sender.jsonl" --sample mixed --map-ms 20
```

候选改用支持长度/取消且检查 source manifest 的 helper，仍先独立启动目标与观察器、
完成 root ready 审查后才启动 sender；示例为 114 字正常输出：

```sh
/usr/bin/python3 owned_gtk_candidate_target.py --mode manual --sample mixed \
  --length 114 --seconds 120 --work "$WORK"
QT_QPA_PLATFORM=offscreen "$DEPS_PYTHON" adaptive_output_sender.py \
  --source-root "$FROZEN_SOURCE" --source-manifest "$FROZEN_SOURCE/manifest.json" \
  --ready "$WORK/ready.json" --output "$WORK/sender.jsonl" \
  --sample mixed --length 114 --case normal --adaptive
```

取消例使用新空目标和新工作目录，长度 38、`--case cancel-after-first`；60ms 基线显式
`--map-ms 60`，不能同时指定 `--adaptive`。尾部 hold 只使用单独 probe helper，不能修改
上述产品源码来复现其结果。所有路径、样本和 SHA 必须在实验前固定并审查。

上述三个角色分别启动并保留原始 wait 结果；sender 只能在 root 审查 ready 身份、空白
owned target 和有界输入窗口后启动。保留实际 backend、导入来源、源代码和 helper hash，
依赖 AppImage 如需 PYTHONHOME/库路径应限定该私有进程，不修改桌面环境。每次 press 前
身份校验和 keys_held 防护不得绕过；观察器先停并自然退出，随后正常停止目标，核对完整
原始日志、恢复和 owned 进程清理。截图仅限自建窗口，不读取用户正文。

离线原生适配检查（不发真实输入）：

```sh
.venv/bin/pytest -q tests/test_wayland_keyboard.py tests/test_wayland_worker.py \
  tests/test_hybrid_keyboard.py tests/test_output_pacing.py
```

此检查在原生审查时点 235 passed in 5.11s，四个 native owned 文件 Ruff lint/format
通过；该数量是历史子集，不是当前最终检查。随后 controller 和 X11 集成新增审查修订，
root 已完成全仓 Ruff lint、332 个文件格式检查。全量检查保留以下诊断历史：
受限环境首次约 50% 停顿后以 TERM 结束（143）；允许本地 IPC 的诊断运行在约 99%
出现 7 个失败并在 teardown 停顿后 TERM 结束（143）。其中旧测试的时间 mock 未覆盖
新增等待，相关测试修订后 focused 18 项通过。随后完整运行得到 1 failed、2046 passed、
2 skipped（58.23s）；残留项是新增输出 scope 使幂等 restore 调用计数由 1 变为实际 2，
对应测试修订后，root 最终重跑自然退出 0：

```sh
.venv/bin/pytest -q -o faulthandler_timeout=30
```

允许本地 IPC 的最终完整结果为 **2047 passed、2 skipped，58.31s**，日志和 SHA 在证据
表内；全仓 Ruff lint、332 文件格式及 diff 检查通过。HEAD 及三处版本仍为上述基线与
0.9.1，没有提交。历史失败和中断保留，不冒充自然完成，也不把最终离线检查通过当成
尚未完成的桌面实验矩阵通过。取消/迟到 ACK/非法辅助
遥测的离线通过，不能替代目标桌面或真实应用实测。


## 协议和实现主来源

以下链接用于复核反馈语义，不是本项目已适配的兼容性证明：

- [X.Org DAMAGE 1.1 协议](https://xorg.freedesktop.org/archive/current/doc/damageproto/damageproto.txt)：
  监视 drawable 绘制影响的区域；不是文字、逐字符或呈现回执。
- [X.Org SYNC 3.1 协议](https://xorg.freedesktop.org/archive/current/doc/xextproto/sync.html)：
  Counter、Alarm 和事件语义；本应用只创建自己的观察资源。
- [GNOME GTK 3.24.41 gdkwindow-x11.c](https://github.com/GNOME/gtk/blob/3.24.41/gdk/x11/gdkwindow-x11.c)：
  对照扩展更新计数器与帧同步代码；内部回调可用不等于外部观察可行。
- [Wayland 官方核心协议](https://wayland.freedesktop.org/docs/html/apa.html)：
  surface/frame 是客户端自身 surface 的接口，不是获取其他应用正文或绘制回执的接口。
- [wayland-protocols 官方 presentation-time XML](https://gitlab.freedesktop.org/wayland/wayland-protocols/-/blob/main/stable/presentation-time/presentation-time.xml)：
  官方源码入口；本次网站访问受限，未从该网页取得额外实际能力结论。


## 隔离环境收尾

本轮只正常启动并使用原先已停止的专用 Ubuntu 24.04 VM，结束后在 guest 执行正常
`systemctl poweroff`，没有强杀或使用 docker stop。`vm-normal-poweroff.json` 记录命令
退出 0；`vm-original-wait.json` 明确转录原始工具的 docker wait 返回 0（不是另起等待
冒充原始 owner receipt）。最终容器状态 `exited`、ExitCode 0、Running/OOMKilled/Dead
均 false。该收尾不能替代逐例 sender/target/observer 自然 wait 的证据。

| 收尾证据（`build/adaptive-output/`） | SHA-256 |
| --- | --- |
| `vm-normal-poweroff.json` | `ee41fcc3588c4bce6d44ef8c0fb8e58ec4fdd1ed1d62f66680b47c481f899c4a` |
| `vm-original-wait.json` | `16ab5dc48f22de8cb3097e8bb241804e72c8ed7fc0a661f05b1931098e34745d` |
| `vm-final-state.json` | `6f29b564a6eb62fd1856ad0af7098de6574c69730271c612584fe0bccf95732b` |
