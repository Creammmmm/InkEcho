# Noble 官方云端配置 A/B 有限验收 — 2026-10-17

在同一个真实 Ubuntu 24.04 Noble Xorg guest、同一 a13 实际包中，一次固定公开语音
样本的 A/B 均通过官方识别、润色和新建 GTK 字段的真实键盘投递。A 为 HTTP 完整
识别与同步润色，B 为 Qwen WSS 实时识别与 SSE 润色。停止录音到首字实际发送为
**1972.286 → 855.314 ms**。这是单样本、同版本的配置组合对照，不是普遍性能、
版本升级收益或识别准确率结论。A/B 生成长度不同，完整输出耗时不能全部归因于流水线。

## 授权经过与执行次数

早期将指定公开 WAV、官方 Qwen 目的地与存储密钥组合使用的试验，曾因人类指令
未明确覆盖该组合被自动审批拒绝，命令没有执行；当时没有换路径上传或重试。
独立生成静音协议、Noble 本地 TLS、匿名管道假密钥交接等检查随后分别按各自范围
完成，均不能替代这次音频/目的地/凭据授权。历史失败保留在
[总览](performance-validation.md)、[实时协议报告](performance-realtime-validation.md)
和[准备报告](performance-noble-live-preparation.md)。

完整准备与 keyless guest 验收后，人类在本对话明确允许使用密钥。主 Agent 结合
此前已明确列出的固定公开音频、Qwen/DeepSeek 官方目的地、最多四次请求及必要的
临时 VM 联网，认定该次组合授权成立，再由唯一桌面操作者执行一次正式命令。
原执行记录 **13229 自然退出 0**。A/B 各一次 ASR 与一次润色，共四次 API 请求，
没有重试、预热、模型发现或补跑。主 Agent 后续只重验元数据、`safe_result` 和
`accept`，没有再次请求云端。计划指纹或 `--live` 本身不是授权来源。

## 固定来源、样本与配置

| 项目 | 本次固定值 |
| --- | --- |
| 工具来源 clean HEAD | `da59cde2dd455775b87c887f31ad79bd5a0ff70b` |
| 实际产品 | `eeb2d0ce8f8c5a6690b0ab54e0196da4254eb767` / `0.1.0a13`，没有修改产品或重打包 |
| AppImage | `dist/InkEcho-0.1.0a13-x86_64.AppImage`，108907000 bytes |
| AppImage SHA256 | `8dce4eedee71373a27e0e6507592b1240617412a8a6f114230b9a53f4d286a89` |
| 实际 guest AppDir | `/home/inkecho/inkecho-a13-runtime-r1/squashfs-root` |
| live 计划 | `afc62ab0f059419f189c54ac3a921357b5fa5f047ec7039a3c14d3cb4aa0f5f8` |
| controller 源码 SHA256 | `778e075e4c21d976b692924191af5a19f6f907ff7429b2341ad7d9432cc2fd96` |
| 公开 WAV SHA256 | `0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf` |
| 原始音频 | 571456 文件字节；282322 帧，16000 Hz / mono PCM16，17.645125 秒；没有重新编码 |

guest 为 Ubuntu 24.04.5、内核 6.8.0-142-generic、GNOME 46.0、独立 Xorg 会话 20，
不是 Ubuntu 26.04 主机的 XWayland 或私有 Xvfb。执行前只读检查见
`build/performance-noble-authorized-preflight-r1`：原容器/QEMU/GNOME 身份不变，
未锁屏、没有其他验证 producer、原网络为空。没有真实麦克风或物理快捷键动作；
固定音频通过应用的录音接口按原时间线回放，B 录音中分块发送，A 停止后提交原 WAV。

完整 a13 清单的 3958 文件、1048 链接及九个实际导入模块再次匹配原包 inventory：
`inkecho.app`、`inkecho.performance`、`inkecho.providers`、`inkecho.realtime`、
`inkecho.polish_stream`、`inkecho.streaming_output`、`inkecho.platform.keyboard`、
`inkecho.runtime`、`inkecho.security`。
包内解释器和依赖来源受审计，没有源码覆盖或候选恢复策略。预算包装器核对原始
请求并计数，内层仍为真实 HTTPX/WSS 传输；live 没有端点改写、host 代跑 API、
代理或 TLS 绕过。
九份验证工具源码和原 12 文件快照也匹配已审计划。

| 配置 | 识别 | 润色 |
| --- | --- | --- |
| A | `https://ws-viafqlzm0ma8r2at.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions`；`qwen3-asr-flash`，完整响应 | `https://api.deepseek.com/chat/completions`；`deepseek-flash`，同步完整响应 |
| B | `wss://ws-viafqlzm0ma8r2at.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime?model=qwen3-asr-flash-realtime`；一次手动提交 | 同一个 DeepSeek 地址/模型，SSE 正文增量 |

两组使用相同固定公开 Prompt、`thinking: {type: disabled}` 和真实硬上限
`max_tokens: 128`。Prompt 虽请求至多 80 个 Unicode 码点，实际输出为 143/122；
它没有严格执行这一文字长度要求，不能把该 Prompt 当作硬字符上限。
每组一个新 cold HTTP client，原生产 TLS 证书/主机名校验、无环境代理、无重定向
保持不变。四请求预算只约束工具 API，临时接通 bridge 也可能使 guest 后台服务联网，
不能称整台 VM 只产生四次网络请求。

## 实际指标及解释

时间单位为毫秒；停止指 `recording_stop_requested`，首发指传输成功提交首个按下事件，
不代表字形已显示。字段来自正式 `handle.json` 的两组安全计时记录。

| 指标 | A：HTTP / 同步 | B：实时 / SSE |
| --- | ---: | ---: |
| 停止 → 首字实际发送 | 1972.286 | 855.314 |
| 停止 → 首次观测 GTK 缓冲非空 | 2005.753 | 916.844 |
| 停止 → 输出完成 | 11606.427 | 9001.440 |
| 首发 → 输出完成 | 9634.141 | 8146.126 |
| 实际投递 / 确认 / 读回码点数 | 143 / 143 / 143 | 122 / 122 / 122 |
| 输出阶段耗时 / 码点 | 67.372 | 66.772 |
| 停止 → ASR 完成 | 914.922 | 188.761 |
| ASR 阶段总长 | 904.896 | 17835.123 |
| 润色开始 → 首正文段 | 1020.889 | 634.372 |

本次首发差为 **1116.972 ms（56.63%）**，只描述这个公开样本的配置组合观测。
B 的 ASR 总长包含约 17.6 秒录音期重叠，不能直接与 A 停止后才开始的 904.896 ms
相比。B 的首发比润色完成早 **23.696 ms**，A 则在润色完成后首发，实际验证了这次
增量路径的重叠；没有单独隔离模型、实时 ASR、SSE、服务波动或思考开关的因果收益。

完整输出差为 2604.987 ms，但 B 少输出 21 个码点。两组键盘实现和 20 ms 等待
相同，上表每码点结果不能称键盘自身又变快；早期 40 → 20 ms 的匹配键盘实验属于
独立证据，不回填到本组。只有 A/B 各一次，没有随机顺序、重复样本、分布或置信区间。

GTK 缓冲使用 20 ms 配置步长轮询读回，还包含 IPC 与调度成本，不是屏幕字形渲染
测量，也不保证观测误差最多 20 ms。`exact_readback` 证明服务输出与实际接收一致，
没有人工参考转写逐字评分，不证明识别或润色的语义准确率。

## 预算、身份、资源和数据保留

原始安全元数据目录为
`build/ubuntu24-perf-vm/output/live-comparison-noble-cloud-r1/live`：

- `controller.json` SHA256：
  `4982835dfbf8a965e3f804d921c71960d7903fba1f8848b75a4ab24b85464294`。
- `handle.json` SHA256：
  `3528a8c20a6d52b3a1af359a462deb7f0aa984e13ae44e2aae211681bf0aecf2`。
- A 的 ASR/润色预算为 1/1，B 为 1/1；最终 diagnostics 均为空，未确认输出为 false。
  精确读回、确认数、实际发送数一致；无尾部或重放、按下释放配对、映射恢复、
  driver 关闭、目标退出和最终 cleanup 均通过。此次正常 A/B 没有主动取消；取消保护
  来自既有独立验收，不能把正常样本写成新增取消实测。

| 原 owner 观察的进程 | PID / start ticks | 终态 |
| --- | --- | --- |
| SSH | 664813 / 42595053 | 自然退出 0 |
| 实际 a13 worker | 59055 / 15872026 | 自然退出 0 |
| A 新 GTK | 59078 / 15872459 | READY、close ACK、自然退出 0 |
| B 新 GTK | 59104 / 15875523 | READY、close ACK、自然退出 0 |

worker 凭据/READY FD 为 3/6；GTK 通道 FD 分别为 20/29。两组 GTK 的 XID 同为
44040195，是顺序销毁后重用，不能只按窗口号把两个进程身份混为一谈。
host controller 自身 PID/start 未由工具持久化；其可用证据为原执行 13229 自然 0，
不补造身份。成功退出依据是原 Popen owner 的 terminal 记录，不是事后“找不到 PID”。

host 在 READY 与完整计划重验后，才懒读取系统凭据的 `provider/qwen` 和
`provider/deepseek`，每次查询再核计划。API Key 与原音频仅经加密无 PTY SSH stdin
及匿名 FD 在内存交接；识别/润色文本与 GTK 接收值只在内存比较，未把正文、音频或
密钥新增到证据、argv、环境或普通配置文件。两日志为零字节，记录/日志 0600。
原固定 `/tmp/inkecho-public-asr-fixture.wav` 在测试前已存在并只读使用；这里的
“未新增持久化”不表示 host 原本没有这份公开 WAV。
这不是 Python 字符串密码学清零或抵御 OS swap/特权内存检查的证明。

controller 的 `passed`、`experiment_passed`、`producer_terminal_and_clean` 均为 true。
`network_phase=restored_none`，原容器
`0582fbea0288c17e40759c823892d60c750f51b43d1de17722cabf33bd136a2f`
及 QEMU PID 1/start 26717597 不变，执行前后 Networks 均为空。资源清理和实际终态
确认后才归还网络，没有强杀进程、提前断活跃网络、重启任务或重置预算。

主 Agent 又独立验收只读收尾记录
`build/performance-noble-authorized-preflight-r1/post-live-preservation.json`，SHA256
`e6548e0d531d2f88c05021e37a130ea44c36cf4f97195ac305d7af56ad68a36b`：
同一容器/start/host PID 517799/QEMU 身份、Networks 空，无仍存活的旧 PID/start 或
其他验证 producer；三份用户 JSON、六个既有 AppImage、九份 staged source 和完整
12 文件快照哈希不变，0 pyc/符号链接/额外文件。三个只读收尾 owner 均自然 0，stderr
为空：container owner 665416/start 42613391、QEMU owner 665426/start 42613392、
SSH owner 665476/start 42615194。它们只读元数据，没有新增 API、密钥、音频/正文、
GUI 或网络变更。

## 复现入口与范围

以下是本次受审命令模板，供核对来源与参数；实际 r1 输出为独占目录，不能删除证据
后把同一指纹当作无限次调用授权。再次云端执行须有相应授权、新独占计划与目录。
完整准备与 keyless 路径见[准备报告](performance-noble-live-preparation.md)。

```sh
.venv/bin/python scripts/validation/performance_noble_live.py --plan
.venv/bin/python scripts/validation/performance_noble_live.py --mode live --live --accept-plan-sha afc62ab0f059419f189c54ac3a921357b5fa5f047ec7039a3c14d3cb4aa0f5f8
```

实际入口为 host → 原容器内 SSH `-T` → 固定 guest launcher → 包内 Python `-B`
worker；不是 host 代跑 API。worker 在 ManagedQtEventLoop 中使用真实 Session、
ProviderClient/QwenRealtimeSession 和当前光标语义的键盘输入；新 owned GTK 和额外
焦点保护属于测试，不替代产品在任意应用中的兼容验收。

此次没有真实麦克风、物理快捷键、准确率评分、长时间/负载分布、所有用户网关或
其他平台测试；这些是范围限制，不是本次有限 A/B 失败。Noble 七项和 Ubuntu 26.04
主机检查仍按各自报告记录，旧 a11/a12 反例不改写。稳定 a9 入口、公开 v0.1 的 a8
附件和用户配置未替换，没有部署、推送或发布。

准备 checkpoint `da59cde` 的 clean workflow 已通过 1369 passed、3 skipped，36.35 秒，
但它不替代新增文档提交的验证。后续精确 HEAD 结果以 `.git/validation/<HEAD>.json`
绑定本报告的记录及 `build/performance-noble-cloud-clean-workflow.log` 为准；不提前
宣称新提交或完整检查已完成。预定命令为：

```sh
.venv/bin/python scripts/validation/workflow.py run --module performance-noble-cloud --evidence docs/performance-noble-cloud-validation.md
```
