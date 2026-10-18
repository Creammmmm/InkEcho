# 整句识别最终结果与协议收尾重叠

本页记录源码生命周期及本地协议验证，候选包的实际原生桌面闭环另行验收。

## 已存在的重叠与本次改变

实时识别本来就会在录音期间上传 PCM；`polishing_streaming` 默认及本次白名单读取的用户值均为 true。已有 SSE producer/consumer 有界队列会让润色增量与打字并行。本次没有重造这些功能，也没有修改用户配置。

剩余串行点是：已收到可信 `conversation.item.input_audio_transcription.completed` 整句最终结果后，仍要等 `session.finished` 才开始润色。本次增加一次性同步 completed 回调能力；仅在原有 ready/commit ACK/item/content-index/文本及一致性验证后通知 Session。支持该能力且启用流式润色时，可以提前启动原有整句润色/输出，同时监督唯一的 finish 任务。legacy adapter、不润色及关闭流式的路径保留原行为。

这是“整句最终转写后，与 ASR 协议收尾重叠”，不是边说边润色或多稳定段 ASR。自定义 prompt 仍接收完整整句上下文，不分句或截断。

最终成功必须等待润色、输出和 ASR finish 全部成功，并确认最终文本一致。finished 缺失仍超时；冲突或收尾错误取消并加入其它任务。任何输入尝试后禁止原文 fallback 或重放；尝试前的润色异常及缺密钥/预流异常也必须先确认 ASR finish 成功，才能按原设置 fallback。取消、过期、替换使迟到回调无效，焦点变化自身不取消。

协议依据：[Qwen manual 交互流程](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-interaction-process) 与 [服务端事件](https://help.aliyun.com/en/model-studio/qwen-asr-realtime-server-events)。维持单次 manual commit，不改变 VAD。

## 本地协议测试及限制

`tests/test_application_early_realtime.py` 使用合成 PCM、真实 QwenRealtimeSession/ProviderClient/Session 与验证 TLS 的 loopback WSS/HTTPS SSE，覆盖两个完成顺序；键盘在这些自动测试中为合成输入。

数值时序样例（ms，相对本地测试起点）：

| 完成顺序 | completed | 首次合成发送 | SSE 完成 | session.finished |
| --- | ---: | ---: | ---: | ---: |
| SSE 先完成 | 14.493 | 17.565 | 18.642 | 20.427 |
| ASR 收尾先完成 | 3.011 | 5.412 | 6.756 | 6.615 |

两种顺序均只在所有门完成后成功，真实本地网络不是云端延迟收益估算。还覆盖 ASR 早/晚错误、重复/冲突 completed、缺失 finished、取消/过期/替换、SSE 尝试前/后失败、预流失败 barrier、焦点语义和完整 prompt。独立关联组合检查为 245 passed；缺失 finished 的新增测试最初误匹配友好错误字符串，已仅修为断言 `ProviderError.code == 'timeout'`，未放宽产品超时机制。

实际原生桌面闭环准备为后续候选包 host 的三项附加门：真实 ManagedQtEventLoop/Session、本地合成 PCM WSS/HTTPS SSE、实际工厂和自有 Chrome，覆盖两个 closure/SSE 顺序与真实 cancel5。要求真实 first press < finished、最终 success >= finished、exact/balance/restore/原 owner wait。设计在 `build/release-pace-r1/native-pipeline-package-gate-r1.md`；本页不把尚未执行的实际键盘流水线门记为通过。

## 可复现入口

`.venv/bin/pytest -q -s tests/test_application_early_realtime.py -k actual_local`。关联测试包括该文件、`test_application_realtime.py`、`test_application_streaming.py`、`test_application.py` 和 `test_realtime.py`。本地 sockets/TLS 在限制环境需授权运行，不应改产品或测试绕过环境限制。

Root 对同一工作树的完整检查通过：Ruff/format（296 文件）通过，pytest 1605 passed、3 skipped / 39.70 s。这是源码工作树检查，不是 clean HEAD 验证收据或实际包验收。

[原生释放等待源码报告](native-wayland-release-pacing.md) 记录 30/20/10 ms 各 13 个有效门，共 39 项；选择 10 ms 后普通 100 字三轮均值 3350.912 ms，相比 30 ms 的 5486.926 ms 减少约 38.93%。初始 VTE raw PTY 回车读回失败和诊断保留；这是源码输入时长对照，不是本地协议或云服务耗时。
