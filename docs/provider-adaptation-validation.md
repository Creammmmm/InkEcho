# 云供应商与协议适配记录

## 范围与独立实现

参考本地OpenLESS提交`63be178b43e3e8084d09ff082a42dbdcbaf74d2b`的供应商目录和协议行为，其根许可证为AGPL-3.0；InkEcho为MIT。本任务不复制、翻译移植Rust实现，不链接其库；Python实现以各供应商官方协议为依据。目录不是云端可用性证明。首期不增加本地模型、OAuth账户接管、剪贴板或IME。

以下18项覆盖参考项目的完整云ASR范围；分批仅用于审查，不缩小目标。所有新族在本页记录验证前均为pending，不宣称已支持真实账户、模型权限或云服务。既有Qwen实时和整句收尾重叠必须回归。

## ASR矩阵

| 供应商/参考ID | 线协议 | 凭据 | 实施与验证状态 |
| --- | --- | --- | --- |
| 火山/volcengine | gzip/二进制序列WebSocket，大模型ASR | API key或app/access/resource组合 | pending，专属节奏/负末包/长度校验 |
| ElevenLabs | multipart speech-to-text，xi-api-key/model_id | API key | 批1实现中，pending本地协议测试 |
| 百炼/bailian | run-task/binary PCM/finish-task WS | API key | pending，与Qwen协议分开 |
| 百炼Qwen realtime | session/append/commit/finished WS | API key | 已有实现，待本轮回归 |
| 百炼fun-asr-flash | multimodal-generation HTTP JSON | API key | 已有实现，待本轮回归 |
| SiliconFlow | audio/transcriptions multipart | API key | 批1实现中，pending |
| StepFun | ASR专用realtime WS；HTTP按官方能力另列 | API key | pending，不将对话语音回答作转写 |
| Zhipu | audio/transcriptions HTTP | API key | pending官方字段与模型限制 |
| MiniMax | speech_to_text multipart | API key | pending专属endpoint/响应 |
| Groq | audio/transcriptions multipart | API key | 批1实现中，pending |
| OpenAI/whisper | audio/transcriptions multipart | API key | 批1实现中，pending |
| OpenRouter | audio/transcriptions JSON input_audio或multipart | API key | 批1实现中，pending；官方支持两种 |
| OrcaRouter | 待核官方音频chat请求 | API key | pending，不由网关名称推断协议 |
| ZenMux | audio/transcriptions JSON input_audio | API key | pending官方请求校验 |
| openai-compatible | 显式自选协议+端点 | API key | 批1 multipart基础，unknown模型未验证 |
| MiMo | chat/completions input_audio/asr_options JSON | API key | 批1实现中，pending |
| 讯飞/iflytek | HMAC-SHA256签名WS，status0/1/2与替换结果 | appID/API key/API secret | pending，多字段SecretStore bundle |
| 腾讯/tencent-cloud | HMAC-SHA1签名WS，voice_id/index/final | appID/secretID/secretKey | pending，40ms/1280B@16k节奏 |

## 润色矩阵

| 族 | 参考供应商范围 | 状态 |
| --- | --- | --- |
| Chat Completions | OpenAI/DeepSeek/Ark/SiliconFlow/AtlasCloud/MiMo/CometAPI/OpenRouter/Requesty/API Route/Orca/AlibabaCoding/CodingPlanX/MiniMax/StepFun/OpenCode/TencentTokenHub/custom | 既有基础，后续preset/字段白名单与SSE验证pending |
| Responses | 支持该协议的显式自定义服务 | pending，独立事件解析/终态，不能按厂商名假定 |
| Messages | 支持Anthropic Messages的显式服务 | pending，专属headers/system/SSE/stop理由 |
| Gemini | 官方generateContent/streamGenerateContent | pending，专属模型发现/内容与终态 |

OAuth与本地LMStudio不在本轮云API-key适配范围，不读取Codex凭据。跨族不自动重发POST或将部分结果整段重放。

## 模型、凭据与UI门

语音发现列表只显示当前协议可用的ASR输入/文本输出候选，排除TTS、纯文本、图像、embedding、rerank及协议不匹配项。audio模态不等于该ASR协议。保留手填未知ID，明确未知不等于verified；已知不兼容在能力调用/输出前阻断。切换供应商/协议重过滤，异步响应有revision门。无通用发现接口只显示内置列表，不报告连接成功。

预设只修改编辑草稿，须显式保存；不读取/显示旧密钥。单key_ref继续兼容，多字段仅以SecretStore内部JSON值保存，普通配置仅ref，不要求用户在参数JSON填密钥。错误/日志不含凭据、音频、正文、签名URL。使用原httpx池、TLS校验、有限音频/响应/队列、取消与绝对超时；仅幂等发现可重试，付费POST不自动重发。

## 官方依据

- [Groq speech-to-text](https://console.groq.com/docs/speech-to-text)
- [SiliconFlow transcription](https://siliconflow.readme.io/reference/createaudiotranscriptions)
- [ElevenLabs create transcript](https://elevenlabs.io/docs/api-reference/speech-to-text/convert)
- [OpenAI create transcription](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create)
- [MiMo API recognition](https://mimo.mi.com/docs/en-US/api/audio/Speech-Recognition)
- [MiMo speech recognition](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/audio/Speech-Recognition)
- [OpenRouter STT](https://openrouter.ai/docs/guides/overview/multimodal/stt)
- [MiniMax ASR console](https://solutions.minimaxi.com/debug/asr)
- [StepFun realtime](https://platform.stepfun.ai/docs/zh/guide/realtime)
- [火山大模型流式ASR](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelstreamingautomaticspeechrecognitionAPI?lang=zh)
- [讯飞语音听写](https://static.xfyun.cn/doc/asr/voicedictation/API.html)
- [腾讯实时ASR](https://intl.cloud.tencent.com/document/product/1118/53937?lang=en)
- [ZenMux transcription](https://zenmux.ai/docs/zh/api/openai/create-audio-transcriptions.html)

## 验证记录

本轮仅使用合成WAV、localhost TLS及离屏UI测试，不读取真实密钥、麦克风或访问认证云端。批1回归初次沙箱运行因socket EPERM产生环境错误；提权同命令结果另记，不能写成已过。后续各协议的真实本地请求、取消、超时、无POST重试、模型过滤/UI凭据门结果待填。本页为源码适配证据，不包含新打包、部署或已发布版本变更。


批1当前本地组合：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_provider_catalog.py tests/test_http_asr.py tests/test_providers.py tests/test_provider_capability.py tests/test_ui.py --tb=short`，211 passed/12.28s（允许本地socket的运行环境）。新增四协议真实TLS上传、请求路径/鉴权/文件或base64字段、最终解析；MockTransport补充无POST重试、取消和超时。旧UI“全模型红色标注”断言按新过滤要求改为仅协议兼容项，保留手填选择/未保存配置/过期响应门；一处新增测试误修改冻结Provider导致失败，改为dataclasses.replace后通过，未修改产品约束。供应商预设创建新ID/ref，不复用旧供应商凭据。单字段仍保存裸API key；bundle工具仅用于后续多凭据适配，不把JSON传给旧Qwen/润色。上述是本地模拟协议证据，不是认证云端可用性或完整任务验收。

MiMo两份已读官方文档（usage更新2026-07-16、API更新2026-07-17）明确请求地址`https://api.xiaomimimo.com/v1/chat/completions`，支持Bearer或api-key鉴权；预设依据此地址，不猜测迁移域名。OpenAI协议核查使用OpenAI Docs技能与上述官方API reference。

批1最终组合加入`tests/test_config.py`，263 passed/12.39s；最后显式测试Qwen实时→Groq→Qwen预设草稿重置HTTP/WSS，不复用原ref。配置层补拒绝api_secret/secret_key/secret_id/access_key/app_key及nested字段，普通region/resource_id保持可用。尚无真实账户云测试。
