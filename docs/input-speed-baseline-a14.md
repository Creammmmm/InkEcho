# a14 输入速度基线与 OpenLess 源码比较

2026-10-17。实际a14本机基线已由唯一操作者串行执行并经主 Agent 核验：原生路径
约7.0码点/秒，直接X11后端对照约13.8码点/秒。两侧各3次100码点精确读回、取消
与恢复均通过。本轮不修改产品、等待常量、包、配置或稳定入口。
这是固定文本的**单次 insert 输入后端基线**，不是 ASR、润色、SSE 或语音端到端测试。
已有双系统包验收与部署状态见[a14 报告](a14-dual-ubuntu-validation.md)。

## 受验产物与计划

- 产品版本 a14，源码 `43c20edcd652020bfe51b959b85f2f90d8b75059`。
- 实际包 SHA256：`bce09c895d51c01c11c73b67aef709632a7514545f0a7fdb6114748c70c8cc96`。
- 包内解释器/产品 origins/full inventory 与43个冻结源文件须匹配；不以源码覆盖包。
- 依赖冻结 manifest：`build/a14-acceptance-preparation/frozen-r2-manifest.json`，
  SHA256 `28e6d011aec783bebdce951743577435bf2a6c950dd79a67f4bfec0d7d9ac2a3`。
- benchmark：`build/a14-input-benchmark-preparation/input_speed.py`，SHA256
  `d4e6aea0f0591d705357488010d7b3d4d6b36988eb0ba9364c1c340d5c37161c`。
- 6个纯指标控制测试已由主 Agent 审查通过；不等于桌面实测。
- 已审 `preview-r1.json` 记录两个完整 argv、环境增量与原 owner 保留策略，SHA256
  `23632d23ea0e146b7ed1311e8cfa79159efd8e48f16e6d1702e6f3a78282f377`。
- 实际桌面为本机 Ubuntu26 GNOME Wayland；原生 Chrome 与 XWayland Chrome 分开测。
- 每种后端各3次正常样本，每次新建自有字段，再单独取消于第8次成功按下。
- 固定100个 BMP 码点，含41个中文及 English、数字和标点，不使用私人正文；UTF-8 SHA256
  `92a3e661ef711faaf474ced4b3c6418aa06d3242333a976a87ed1328d1f9387d`。
- 无云请求、录音、真实密钥、剪贴板、系统输入法；已运行用户实例不受控制。

## 指标定义与观察误差

`start` 在字段就绪、连接与授权完成之后，紧邻一次 insert/输出 scope 之前取得；
因此不包含建窗口、连接、授权或 ASR。所有时钟为本机 `time.monotonic`。
XWayland 的 output_session 在这一次 insert 外结束；原生由 insert 自身结束事务。

| 指标 | 定义 | 不能解释成什么 |
| --- | --- | --- |
| start→first press | 首次成功按下事件时间减 start | 屏幕首字出现或云端首字延迟 |
| first→last press span | 末次减首次成功按下时间 | 全部清理已完成 |
| start→insert return | insert 返回时间减 start | X11外层 output_session 已返回 |
| start→output scope return | 完整输出 scope 返回时间减 start，包含该scope恢复 | fixture关闭或所有进程清理耗时 |
| start→DOM exact observed | 首次观察自有字段完整等于样本的时间减 start | 字形渲染时刻或用户所有应用均确认 |
| 全程吞吐 N/total | N个成功按下 / start→output scope return秒数 | 只算按键之间的稳态速度 |
| 稳态事件率 (N−1)/span | 99个间隔 / 首末按下跨度秒数，正常N=100 | 带启动/末尾恢复成本的全程吞吐 |
| 按下间隔 | 相邻成功按下间隔的min/median/max | 对未来负载的范围保证 |

原生按下时点取实际 worker 返回的 `sent_at`；first-sent callback 携带该时间戳，
不是 callback 在父进程运行的时刻。XWayland在原始发送成功返回后透明记录按下时间。
20ms DOM轮询另叠加约50ms fixture状态更新、IPC和调度，不能称观测误差最多20ms。
读回证明当前字段的文字一致，不是逐帧字形显示测量。

新建自有目标的 PID/start/focus guard、状态采样和透明计数成本包含在结果中；
没有改生产 map/send/等待。正常样本N=100；取消N=8，只验证取消，不加入正常速度中位数。
每种后端3次的中位数只描述这次样本，不构成p95、可靠性分布或跨机器承诺。

## 实际结果

各指标取三次正常行各自的中位数，时间单位ms：

| 后端 | 首次按下 | 首末按下跨度 | scope返回 | DOM exact观测 | N/total码点/秒 | 稳态事件/秒 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 本机原生Wayland | 68.128 | 14040.063 | 14210.386 | 14124.500 | 7.037 | 7.051 |
| 直接X11后端→XWayland | 22.916 | 7156.286 | 7225.467 | 7183.512 | 13.840 | 13.834 |

每次新字段，以下每行均为100/100 exact，时间单位ms：

| 后端/轮次 | 首次按下 | scope返回 | N/total码点/秒 | 按下间隔中位数 |
| --- | ---: | ---: | ---: | ---: |
| 原生1 | 68.128 | 14148.678 | 7.068 | 140.895 |
| 原生2 | 71.252 | 14221.643 | 7.032 | 141.731 |
| 原生3 | 68.093 | 14210.386 | 7.037 | 141.152 |
| X11→XWayland1 | 23.339 | 7146.563 | 13.993 | 71.028 |
| X11→XWayland2 | 22.887 | 7225.467 | 13.840 | 72.184 |
| X11→XWayland3 | 22.916 | 7242.586 | 13.807 | 72.165 |

实际图形桌面为Ubuntu26/GNOME Wayland、图形logind会话已核验、未锁屏；两侧包审计
均为18个实际origins。原生典型按下间隔约141ms，X11对照约72ms，均含自有目标guard
开销，不能把超过固定等待的差额全部归因D-Bus或某一次调用。

两侧独立取消行均精确8字符、8次按下/释放、input_cancelled，继续观察0.5秒无尾部。
所有行guard拒绝0、fixture错误空、mapping_restored为真、目标自然退出0；原生
map/group/modifiers前后相同，四个worker均原owner观察exit0。X11正常每行101次
mapping writes/1次restore调用，取消9次write/2次restore调用，按键平衡且映射恢复。

原始 `build/a14-input-benchmark-preparation/native-result-r1.json` SHA256：
`dbb6735d0c8a62a4f0fc95c16752fdc9c5dab68e2f30e51405e491b263b98375`；
`xwayland-result-r1.json` SHA256：
`1cbf5f9d2476090ed48dfaa6dd3791400e16d887db5b3e04297c51999b1ebf51`。
原benchmark owner689639/start43324703与692780/start43330015均自然exit0；原生四个
worker身份依次为689654/43324751、690641/43326391、691559/43328036、692462/43329674，
均自然exit0。各原target/worker终态、逐次按下时间与安全字段保留在原始行/工作目录。
全程0 ASR、润色、云请求、录音与真实密钥访问，不使用剪贴板或系统输入法。

## 源码已能解释的逐字等待

| a14路径 | 固定主动等待 | 仅由等待推导的上限（不是实测） |
| --- | --- | --- |
| X11/XWayland | 映射、按下、释放后各20ms | 60ms/码点，至多约16.7码点/秒，另有API/guard开销 |
| 原生Wayland普通字符 | 设置映射后50ms、释放后50ms | 100ms/码点，至多约10码点/秒，另有D-Bus/worker成本 |

见 `platform/keyboard.py:456–474`、`platform/wayland_worker.py:471–513`。
X11当前实际使用XSendEvent、刷新当前窗口和state0；不是XTest全局事件队列。
原生换行不需要同样的映射等待，不能把普通字符公式套到任意文本。
**实际路由限定：** `platform/wayland_keyboard.py:14–20` 的 `keyboard_for_desktop()`
在GNOME Wayland固定返回WaylandKeyboardInput，不按焦点目标选择后端。本次约13.8
码点/秒是验证工具直接创建KeyboardInput的受控对照；用户仅把Chrome改为XWayland，
当前默认应用仍走原生后端，不会自动获得该速度。当前默认路径应以约7码点/秒理解，
也不承诺任意应用/机器均相同。尚未实现自动路由，不能称产品已提速约两倍。

R8的X11任务范围映射复用已减少片段间恢复；它没有删除每字三次等待，也没有
使原生worker自动获得同一优化。流式队列合并同样不消除底层逐字等待。

历史[初始键盘对照](performance-keyboard-validation.md)中，默认20ms的四目标
约65.93–67.17ms/码点；[a13 Noble云端A/B](performance-noble-cloud-validation.md)
输出阶段约67.372/66.772ms/码点。这些不是本次a14新测量，不能回填上表。

## OpenLess：项目已定位，机制不能直接等价比较

官方项目为 [Open-Less/openless](https://github.com/Open-Less/openless)。公开branch页面
查询到beta提交 `de072a88373a222280a8c22948092a260880196c`，以下链接固定该版本。
这是源码机制比较，没有安装或实测OpenLess，不声称它比a14快多少倍。

| OpenLess路径 | 已读源码事实 | 与本项目约束的差异 |
| --- | --- | --- |
| Linux默认 | fcitx5插件整段/增量commitString，默认允许剪贴板回退 | 使用系统输入法；捕获目标，不是输出时自由选择当前光标 |
| macOS | CGEventKeyboardSetUnicodeString/CGEventPost，每码点1ms | OS原生Unicode事件；不能把该等待移植成Linux保证 |
| Windows | SendInput(KEYEVENTF_UNICODE)，每字符1ms，每16字符另等12ms | 无Linux逐字改映射，但批次与原目标重新激活也不是本项目逐字语义 |
| 流式调度 | 每轮flush前等待12ms，再提交积累正文 | 是刷新策略，不是测得的字符吞吐 |

Linux默认接线见[backend.rs#L225](https://github.com/Open-Less/openless/blob/de072a88373a222280a8c22948092a260880196c/openless-all/app/linux-egui/src/backend.rs#L225)，
捕获/提交见[fcitx5.rs#L500](https://github.com/Open-Less/openless/blob/de072a88373a222280a8c22948092a260880196c/openless-all/app/linux-egui/src/fcitx5.rs#L500)及
[插件#L420–432](https://github.com/Open-Less/openless/blob/de072a88373a222280a8c22948092a260880196c/openless-all/scripts/linux-fcitx5-plugin/openless.cpp#L420)。
macOS见[unicode_keystroke.rs#L93](https://github.com/Open-Less/openless/blob/de072a88373a222280a8c22948092a260880196c/openless-all/app/src-tauri/src/unicode_keystroke.rs#L93)；
Windows见[同文件#L434–446](https://github.com/Open-Less/openless/blob/de072a88373a222280a8c22948092a260880196c/openless-all/app/src-tauri/src/unicode_keystroke.rs#L434)、
[逐字/批间等待#L495–519](https://github.com/Open-Less/openless/blob/de072a88373a222280a8c22948092a260880196c/openless-all/app/src-tauri/src/unicode_keystroke.rs#L495)。
原目标重新激活见[core_adapters.rs#L3135](https://github.com/Open-Less/openless/blob/de072a88373a222280a8c22948092a260880196c/openless-all/app/src-tauri/src/core_adapters.rs#L3135)。
12ms策略见[streaming_insert.rs#L5](https://github.com/Open-Less/openless/blob/de072a88373a222280a8c22948092a260880196c/openless-all/app/crates/openless-core/src/streaming_insert.rs#L5)及
[api.rs#L1937](https://github.com/Open-Less/openless/blob/de072a88373a222280a8c22948092a260880196c/openless-all/app/crates/openless-core/src/api.rs#L1937)。
上述等待常量不是它在目标应用内的实测速度；也不能据批次发送认定相同取消粒度。
当前Windows源码注释还记录无逐字间隔会丢字，说明它也不依赖“零延迟必然可靠”。
本地旧63be178/feat/wayland_ibus另有Portal剪贴板粘贴，不作为当前beta已发布功能。

## 提速方向与必须保留的负例

1. 先研究安全后端router：对XWayland目标使用X11路径，原生目标仍走原生路径。
   必须实测同任务native↔X11切换、每次发送时当前光标、任务/epoch取消、映射事务
   独立与正确恢复；投递已尝试后不能换后端重放。它是候选，不是本轮已实现优化。
2. 评估任务级原生映射事务复用，使多个SSE片段不反复begin/finish；不等待未来
   片段，不捕获焦点。取消/过期/替代/异常/EOF/关闭仍释放按键并恢复自有映射。
   本次单insert没有片段间重复成本，不能据它量化此候选收益。
3. 实测有界空键位预映射或安全cache，减少每字映射编译、上传和刷新；可用空槽与
   Chromium兼容性未证明。不能为缓存删除所有权/外来变更检查或覆盖第三方改动。
4. 分别评估映射、按下、释放等待候选值，保持其他条件相同；先验证精确读回、
   新窗口、切窗、取消及恢复，再讨论速度，不承诺比例或直接把常量改成零。

X11历史10ms候选第二轮新Chrome textarea只有139/140，丢字位置未保存，不能说
“首中文”“两次”或猜根因。[原生混合窗口诊断](native-wayland-mixed-private-diagnosis.md)另有30ms×2
contenteditable混合切窗丢Latin首k的明确记录，50ms×2才通过；这是独立负例。
XSync/发送成功不等于应用已消费文字，不据此宣称可无损整批立即发送。
OpenLess采用AGPL-3.0；只比较公开机制，后续实现不得直接复制其源码到MIT产品。

## 复现与后续记录

实际执行的精确argv/环境增量以已审preview-r1.json为准，重复须独占桌面且用新目录。
归档入口为 `scripts/validation/a14_input_speed.py`，仅依赖目录改为仓库相对冻结r2；
实际原始回执仍绑定上述d4e6…脚本，不把路径迁移冒充重新测量或产品修改。
模板选择固定受验a14、其包内解释器/packages与匹配冻结src；不是自动选择stable旧包。

```sh
# 使用已审包环境与原preview中的全部artifact/origin参数；两后端逐项执行，不并发
"$appdir/usr/bin/python3" -B scripts/validation/a14_input_speed.py \
  --artifact "$artifact" --expected-sha "$sha" --package-root "$appdir/packages" \
  --frozen-source-root "$frozen/src" --backend native \
  --work-root "$qa/native-work" --output "$qa/native.json" --run-reviewed
```

XWayland单独改backend和独立work/output，不修改生产等待。本轮只建立速度基线与有限分析，
没有实施候选优化。完整clean-HEAD检查由主 Agent在提交后按精确receipt记录。
