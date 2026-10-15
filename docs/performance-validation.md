# 性能优化验收总览 — 2026-10-16

本轮完成分段计时、HTTP 连接复用、已核实模型的思考控制、Qwen 实时识别的协议接入、
流式润色与串行增量输出，以及经过实际应用验证的 X11 键盘等待调整。
**已经测得的实际提速限于当前 Ubuntu 26.04.1 主机的 XWayland 输出：
四种独立目标的每字符输出耗时降低约 48%–49%。** 尚无 Ubuntu 24.04 桌面数据，
也没有真实语音从停止录音到首字输出的云端前后对照；不能把该输出指标写成
完整语音链路提速承诺。

本轮基线为 `96b3b5d424b60b98070ef6c311e830ecdc9cd4a6`，工作分支为
`codex/latency-pipeline`。实现按独立模块提交；本次授权不包含推送、发布或部署，
现有用户的快捷键、供应商配置和密钥未由本轮测试改写。包级最终验收单独记录，
不能用源码测试替代。

## 模块、证据与边界

| 模块 | 实际完成 | 证据及适用范围 |
| --- | --- | --- |
| 分段计时 | 单任务录音停止请求、音频就绪、ASR、润色首段/完成、首字发送、输出结束；取消/失败也保留已观测部分 | [计时验证](performance-timing-validation.md)。固定名称、结果和数值；缺失项为 null，不以开始 `insert()` 冒充首字 |
| HTTP 生命周期与思考控制 | 应用持有一个连接池，角色独立超时，退出正确关闭；仅对已核实的官方地址/模型默认关闭不必要思考 | [供应商验证](performance-provider-validation.md)。实际本地 TLS 三次请求从三个连接变为一个；未知网关/模型不猜参数，未测得云端思考开关收益 |
| Qwen 实时 ASR | 独立 WSS 手动提交协议；录音中分块发送，停止后只接受最终结果；录音中断网及时停止麦克风 | [协议验证](performance-realtime-validation.md)、[编排验证](performance-pipeline-validation.md)。本地 TLS/WSS、本机麦克风和官方纯生成静音的手动协议通过，真实语音准确率待验 |
| 流式润色 | 严格 SSE、UTF-8、结束事件和用量解析；只向下游交付正文增量 | [SSE 验证](performance-polish-stream-validation.md)。本地真实 HTTPS 夹具通过；另有一次固定公开短句的官方 DeepSeek 实测，见下文 |
| 串行增量输出 | 有界 Unicode 队列、跨段 CRLF、偏移校验、最终尾部、背压、取消与部分输出失败保护；可显式关闭流式 | [编排验证](performance-pipeline-validation.md)。合成对照显示生成与输出可重叠，不能据此声称实际云端或 Ubuntu 24.04 提速 |
| 键盘等待与真实首发时间 | X11 三次等待各从 40 ms 改为 20 ms，统一可打印字符的 Unicode 映射；两种后端提供实际发送时点 | [初始键盘验证](performance-keyboard-validation.md)、[Qt 流式跟进验证](performance-x11-stream-validation.md)。真实 XWayland 四目标及 native Wayland 跨窗口验证通过；Wayland 两个 50 ms 等待未变 |

阶段 0 和平台范围继续以[可行性记录](feasibility-report.md)、
[当前光标输入验收](current-cursor-input-validation.md)、
[原生 Wayland 验收](native-wayland-parent-validation.md)为准。本轮不是对所有 Linux
发行版、桌面、应用或 Unicode 字符的新增兼容承诺。

实际 Qt 联调另修复了流式资源回收问题：qasync 0.28 原有循环未登记 Python 异步
生成器，功能结果正确时仍可能出现 `GeneratorExit` 清理失败。统一循环适配和显式
流迭代器关闭现已通过真实 Qt + 本地 TLS 测试，未屏蔽告警。初始失败日志保留，详见
[Qt 资源回收验证](qasync-stream-cleanup-validation.md)；该修复不以普通
`asyncio.run` 测试冒充实际 Qt 生命周期通过。

## 实际测量与未通过项

### 真实桌面键盘输出

环境：Ubuntu 26.04.1、GNOME/Mutter 50.1、Chrome 154.0.8037.97、GTK 3.24.52、
VTE 0.84.0。所有字段、浏览器配置、GTK 窗口与终端原始字节收集器均由测试新建；
没有向用户页面、文档或命令行 shell 输出。每次按下事件均核实测试窗口所属进程及
当前目标；释放事件始终执行。这些额外焦点限制只属于测试保护，不改变产品的
“输出到当时光标”语义。

对照与最终默认参数均使用相同的全 Unicode 映射、实际 Qt 事件循环和独立新目标，
各重复 28 码点样本五次、每个目标 140 码点。只有三次等待从各 40 ms 改为各 20 ms。
下表时间包括测试保护成本，不是字符可见时点；对照是相同修正映射下的 40 ms 参数，
不是把旧版本和新版本的其他差异一并归因于等待。

| 真实 XWayland 目标 | 旧参数，ms/码点 | 最终参数，ms/码点 | 输出耗时下降 |
| --- | ---: | ---: | ---: |
| Chrome textarea | 124.07 | 64.19 | 48.3% |
| Chrome contenteditable | 124.41 | 64.32 | 48.3% |
| GTK TextView | 124.74 | 63.96 | 48.7% |
| VTE 原始字节收集器 | 124.84 | 64.53 | 48.3% |

这组匹配对照共核对 **1120 个码点**，输出逐字/逐字节准确，按下/释放配对、键盘映射
恢复均通过。首字向传输发送的时点从约 42.04–45.33 ms 缩短至 21.23–25.24 ms。
数据来自 `build/performance-keyboard-unicode40-qt-four-targets.json` 和
`build/performance-keyboard-unicode20-qt-four-targets.json`。更早的独立
`asyncio.run` 与普通字符映射测量仍作为历史证据保留，不冒充这组最终 Qt 数据。

**10 ms 候选未获采用。** 它在私有 Xvfb 和第一轮主机测试通过，但第二轮新 Chrome
textarea 仅收到 139/140 码点，即便事件配对、映射恢复正常；该失败保留在
`build/performance-keyboard-host-candidate10-round2.json`。选择 20 ms 的依据包含
真实接收结果，不能只靠服务器接受按键或模拟测试。

完整 Qt 流式链路还揭示了独立测试未覆盖的文字失真：普通 ASCII/Latin-1 keysym 与
Unicode keysym 混用时，分段输出的 GTK 字段只有 **21/25** 码点，20 ms 和原 40 ms
等待都复现。仅将所有可打印字符统一映射为 Unicode keysym、保持 40 ms 的对照后，
25/25 通过。随后最终 20 ms 默认在三个独立进程、新 GTK 窗口中均通过真实麦克风 →
本地 WSS 固定识别 → 本地 HTTPS 三段润色 → 真实键盘输出，第二任务取消后总字符为
26、无尾部，按键配对和映射恢复正确。它们没有真实云端识别，也未改输入法设置；
客户端内部的预编辑机制未被直接测量，不声称找到了通用输入法绕过手段。失败和受控
修正详见[Qt 流式跟进验证](performance-x11-stream-validation.md)。

native Wayland 另行验收：同一个 26 字符输出中，5 字符到原生 Chrome、5 字符到
XWayland Chrome、16 字符回原生 Chrome，全部准确，映射/组/修饰键恢复，首发回调
只触发一次。回调收到时间比 worker 的实际提交时点晚约 52.07 ms，验证了首字计时
没有误用含释放等待的 ACK 时点。native Wayland 的等待和 BMP 字符范围没有放宽。

这些测试没有测独立 Xorg 会话、Ubuntu 24.04、其他目标或高负载下可靠性，也没有
测完整“录音停止 → 云端识别 → 润色 → 字符可见”的时间。

### 云端、音频与合成证据分别记录

- **真实麦克风，本机采集路径：** 0.7023125 秒、33 个完整样本分块，停止前已产生
  PCM；完整录音缓冲为空，停止时无 WAV 编码。未保存音频、未发云端。
  `build/performance-streaming-real-microphone.log`，复现见编排报告。
- **真实官方 DeepSeek，仅固定公开短句：** 一次已允许的短句请求通过，14 字符、
  7 个正文增量、首段 781.643 ms、请求完成 789.38 ms，用量可用且结果符合固定公开
  样本。`build/performance-sse-live.json`。它证明当前服务的 SSE 能力，不是速度前后
  对照，也不证明 ASR、实际键盘投递或思考开关的耗时收益。
- **指定公开 WAV 的云端试验：未执行。** 拟使用固定 SHA-256 的公开 WAV，但自动审批在命令
  执行前拒绝；没有读取该请求的凭据、连接云端或上传音频，未换路径重试。协议夹具
  和麦克风通过不能替代真实账户/模型的能力或准确率验证，详见实时协议报告。
- **官方 Qwen 手动协议：纯生成静音通过，非语音准确率验证。** 获准探针仅在程序内
  生成一秒全零 PCM，不读取 WAV、麦克风或私有正文。最终回执为
  `protocol_finished_without_speech`：created、updated、手动 commit、ACK、finish
  和 session.finished 全通过，发送 **10 × 3200 bytes**，总耗时 **1241.349 ms**，
  配置哈希不变，没有非空转写正文。
  `build/performance-realtime-silence-optional-metadata.json`。它仅验证当前账户与
  `qwen3-asr-flash-realtime` 的这次手动 WSS 交互，不证明识别准确率、非空语音结果
  的所有形态或停止录音到首字的性能收益。
  联调修正了实测官方省略字段和非结果通知的顺序处理；此前 **六份失败/诊断回执**
  均保留，未冒充成功。可选元数据不替代本地任务、单连接/单手动提交、取消和过期
  隔离；提供的 ID 仍须有效且一致，提供的内容索引仍须为整数零。完整诊断、官方
  依据及 **205 项本地回归（含 63 项探针防护）** 见[实时协议报告](performance-realtime-validation.md)。
- **合成同步/流式对照：** 相同人工 ASR 等待、生成节奏和每字符等待，三样本中位数
  从停止到模拟首发 292.302 → 201.852 ms，停止到输出完成 1456.131 → 1367.123 ms；
  输出阶段本身 1163.829 → 1165.461 ms，没有提速。该对照只证明流水线重叠，JSON
  明确标注 `synthetic_headless`、desktop/cloud 均 false。
  `build/performance-synthetic-comparison.json`。

## 操作方式与安全边界

在转录服务显式选择 Qwen 实时 WebSocket，并选择该服务实际有权限的实时模型；
录音格式须为 16 kHz、单声道 PCM16。官方受支持地址可以推导 WSS 路径，未知网关须
提供其实际 WebSocket 地址。仅在模型列表看见名字不代表网关实现该协议；HTTP 同步
转写和文件转写不能靠修改 `stream` 参数变为实时接口。本轮没有替用户改选模型、
地址或录音设置。

协议、WSS 地址、流式开关及对应能力测试的界面和任务预检已分别验证，见
[供应商界面验收](performance-provider-ui-validation.md)。该界面测试使用独立配置、
offscreen Qt 和本地 TLS 夹具；实际包显示与云端能力仍分别验收。

润色的流式开关默认开启；对不支持 SSE 的网关可显式关闭，选择原有完整响应路径。
流式失败后不会偷偷重发一次同步请求。只有尚未尝试键盘投递时，才能按用户已有设置
回退原始识别文本；一旦进入过投递，即便无法确认发出多少，也不整段回放原文。

录音开始不捕获目标；录音、识别、润色和输出期间均可切换光标或窗口。后续按键发送到
那一刻的焦点。主动取消、任务过期、被新任务替代会停止尚未发送的正文并清理资源，
已交给桌面的事件无法撤回。每段、每次异步恢复及每个实际按键仍有任务/期限保护。
整个链路不使用剪贴板或系统输入法。

输出队列最多 4096 码点，加一个正在投递的 128 码点片段；完整结果校验前缀另有
128000 码点上限。跨片段 CRLF 只输出一次换行，重复文字按 Unicode 偏移处理，
最终完整返回值只用于前缀检查和补尾。队列背压计入供应商请求总超时；
`polishing_seconds` 因而不是纯服务端生成时间。

计时出现在原有统计与日志页面，对应私有轮转日志
`$XDG_STATE_HOME/inkecho/logs/inkecho.log`，通常是
`~/.local/state/inkecho/logs/inkecho.log`。性能字段仅含固定结果、名称、数值和缺失
标记，不含音频、正文、Prompt、模型名、任务 UUID 或密钥。首发表示传输成功提交，
不表示目标已经显示字符；缺失项保持 null，不能当作零延迟。

## 可复现验证顺序

1. 阅读本报告和各模块报告，核对主机与平台边界。在独立开发环境按 README 安装
   已锁定的开发依赖。先运行完整本地检查：

   ```sh
   uv sync --locked
   .venv/bin/ruff check .
   .venv/bin/ruff format --check .
   .venv/bin/python -m pytest -q
   ```

   本地 TLS/WSS 夹具需要能绑定 localhost；因沙箱拒绝回环地址而失败的运行不能当
   通过证据，也不能因此删测试。原始基线为 509 passed、2 skipped；各模块独立结果
   已在对应报告记录，最终集成结果须对应最终提交和验证记录。
2. 运行不访问云端、密钥或桌面的可控对照：

   ```sh
   PYTHONPATH=src .venv/bin/python scripts/validation/performance_baseline.py \
     --compare-streaming > build/performance-synthetic-comparison.json
   ```

   不改变人工延迟来声称提速；保留原始与流式各分支的完整事件和样本。
3. 需要采集验证时，按编排报告显式运行 `INKECHO_TEST_MICROPHONE=1` 的本机测试。
   麦克风采集结果与云端识别结果分开记录；无需上传录音来验证本机分块。
4. 按键盘报告在新建且受保护的目标中复测原参数与最终默认参数，并独立复测 native
   Wayland 的跨窗口输出。测量前协调桌面使用，不能向用户现有页面或文档打测试文字。
5. 在实际获准的平台、服务与自建空字段中测完整语音路径。记录会话、模型协议、
   样本数、首发和总耗时、准确接收、取消及映射恢复；日志不保存正文或音频。真实云端
   请求必须遵守数据传输授权，不能把被拒绝的上传改头换面重试。
6. 构建并运行实际 AppImage，再核对来源、依赖、许可、界面及任务链路。包验收应
   区分真实采集/桌面、本地协议夹具和真正云端，不以解包后文件存在冒充运行成功。

## 最终本地检查与包验收

| 检查 | 当前实际结果 | 证据 |
| --- | --- | --- |
| 定稿前源码/工作区集成检查 | 产品 `b963879` 与 observed-order 包探针工作区；全仓 Ruff lint/format **204 个 Python 文件**通过；**935 passed、3 skipped，17.81 秒** | `build/performance-final-integrated-source.log`；不是最终 clean HEAD 的正式记录 |
| 最终 clean HEAD 工作流 | 按开发规范在本文定稿并提交后执行；正式结果以 `.git/validation/<HEAD>.json` 为准 | 记录绑定当时提交与本报告哈希；不复用前一检查点或未提交工作区的结果 |
| 最终 a10 AppImage | r2 独立包验收通过；版本 0.1.0a10，108907000 bytes | `dist/InkEcho-0.1.0a10-x86_64.AppImage`；SHA-256：`5c515dd0e3ceb8eb910baa45f392d8be28bfda109c5e1d59865e5a0733b7d55a` |
| 包内容与来源 | 产品 `b963879` 的 43 个源码哈希前后不变；3958 文件哈希、1048 内部符号链接、websockets 15.0.1 的两份 BSD 许可核对通过 | [完整包报告](performance-package-validation.md)，正式验收记录随 `aad9280` 提交 |
| 实际包任务链路 | 包内解释器与模块运行；真实麦克风 → 本地模拟 WSS/SSE → 真实 XWayland GTK：25 字符准确，取消只增加 1 字符，无预览输出、无尾部，按键配对和映射恢复 | `build/performance-a10-package-live-mic-r2.{json,log}`；模拟识别/润色，不是真实云端识别 |
| 实际包 UI/退出 | native Wayland 和 offscreen 各 9 页、IPC show/toggle/cancel/quit、异常配置保留通过；图像已人工核查 | `build/performance-a10-ui-{native,offscreen}-r2/`；包链路和主机 UI 日志无异步资源清理错误 |
| Ubuntu 24.04 用户态 | 固定容器、非 root、无网络/主机 home/显示/音频；启动与 9 页包 UI 通过 | `build/performance-a10-ubuntu24-r2.log`；缺少音频后端提示符合隔离环境，不是 Ubuntu 24.04 桌面或麦克风通过 |
| 部署与远程 | 主验收复核三份用户 JSON、a9 与稳定别名的哈希未变；本轮未部署、未推送或发布 | 稳定入口 a9、公开 v0.1 附件 a8 继续分别保留 |

包内真实麦克风链路的本地固定 25 字符夹具，从停止到首发 **28.628 ms**，到输出完成
**1793.176 ms**；只衡量该本地模拟服务，不是云端延迟或语音识别准确率。包探针没有
读取用户凭据，也没有发云端请求。官方静音协议通过属于另行记录的源码连接检查，
不是从这个包执行的云端请求。包的独立依赖/来源、所有早期检查点及限制见
[a10 包验收](performance-package-validation.md)。

要试用本地预览包，先从正在运行的旧版托盘菜单正常退出，再启动 a10。否则单实例
通信可能只唤起旧 a9，不能据此判断 a10 功能是否生效：

```sh
./dist/InkEcho-0.1.0a10-x86_64.AppImage
```

本次保留原有稳定入口、自启动和公开 release；独立包已验证不等于已替换用户正在
运行的版本。后续部署、推送或发布须使用各自的实际验收和授权范围。

自动审批拒绝的是将指定本地 WAV 发送给外部 ASR 服务的试验，理由是当前人类指令
未明确批准这份音频、该目的地及所存凭据的组合使用。因此这份公开语音的云端识别
验收仍待相应授权；独立生成静音检查已获准且最终通过手动协议，但不能用它替代语音
识别准确率验收。已完成的本地协议、麦克风和键盘验证不受此限制影响。
