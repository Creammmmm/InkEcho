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


## 批2：余HTTP与StepFun专用实时ASR

新增独立协议选择：StepFun同步multipart、Zhipu同步multipart（30秒前置限制）、MiniMax `speech_to_text`（language为受限header，不放form）、ZenMux JSON input_audio、OrcaRouter显式音频理解转写。Orca不是专用ASR，以官方模型页audio输入/text输出及OpenAI-compatible chat契约选择`google/gemini-2.5-pro`；其标准input_audio字段属该兼容契约推断，真实云端未验证，不将任意Gemini文本模型列为ASR。MiMo与Orca仅接受`finish_reason=stop`且message为dict，无tool_calls；length/filter/缺失或畸形终态一律response错误，不输出截断文本。未知namespace保留未知，但openai/gpt-4o、anthropic/claude等已知纯文本末段不再误放行。

官方Zhipu索引定位[语音转文本](https://docs.bigmodel.cn/api-reference/模型-api/语音转文本.md)：hotwords是最多100字符串数组。其[官方SDK multipart编码](https://github.com/MetaGLM/zhipuai-sdk-python-v4/blob/main/zhipuai/core/_http_client.py)使用`hotwords[]`；这里独立用httpx生成重复该字段，本地TLS按真实multipart逐项核对，不做格式fallback或额外POST。StepFun hotwords则按其文档发送JSON数组字符串，不能混同。

StepFun以[当前ASR专属WS](https://platform.stepfun.com/docs/zh/api-reference/audio/asr-stream)为准，地址`/v1/realtime/asr/stream`、model `stepaudio-2.5-asr-stream`，不同于参考项目旧`.ai/v1/realtime`对话端点。session.update明确PCM16k/16-bit/mono、不启用server_vad；一次manual commit，经committed item_id匹配后仅completed.transcript作为最终结果，不发送session.finish、不使用累计delta/stash兜底。官方append段写WAV而format字段明确PCM存在文档歧义；当前依据格式配置发送原始PCM，本地WSS检查实际字节，未宣称已通过认证云端。meta/session_id在出现时一致性校验；连接所有权、更新确认与item门始终存在，不将示例meta字段自行升为强制字段。

复用关系明确：`StepRealtimeSession`仅继承成熟Qwen的有界队列、单连接TLS `_open(config.url)`、JSON receive循环、deadline/active检查、finish等待_done和close；独立覆盖_event及_send_audio。其config.url不带Qwen model query；sender仅一次Step commit，无Qwen session.finish。禁用提前completed callback，Session用Step专属factory，Qwen原注入factory保持。cancel/active失效/绝对deadline在等待commit结果期间均清理全部任务、关闭连接、不重连，不输出部分文字。

官方依据补充：[StepFun同步](https://platform.stepfun.com/docs/zh/api-reference/audio/transcriptions)、[MiniMax当前文档](https://platform.minimax.cn/docs/api-reference/speech-to-text)（预设api.minimax.cn，旧调试页api.minimaxi.com不擅自重写用户配置）、[Orca chat](https://docs.orcarouter.ai/api-reference/chat/create-a-chat-completion)、[Orca音频模型](https://www.orcarouter.ai/models/google/gemini-2.5-pro)。

根对批1精确e58c798独立完整workflow：Ruff/306format、1662 passed/3 skipped，44.37s，未push。本轮后续提交仍需最终HEAD新收据。

批2冻结组合命令：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_step_realtime.py tests/test_http_asr.py tests/test_provider_catalog.py tests/test_providers.py tests/test_provider_capability.py tests/test_ui.py tests/test_application_realtime.py tests/test_application_early_realtime.py --tb=short`，284 passed/17.66s。根独立本批核心143 passed/12.13s。新增9个HTTP适配的实际TLS逐字段检查（包含base64、model、Orca文本+音频/no-asr_options、streamfalse、MiniMax语言header、Zhipu bracket-array）及Step实际WSS正常/可选meta/握手与收尾超时/早完成/错item/布尔index/empty/VAD拒绝/有界队列/取消与绝对deadline。新增Session测试证明Step走其专属factory且不调用Qwen注入factory，旧Qwen相关回归保持。第一次批2组合仅旧UI错误提示断言未随新多协议提示更新失败；后一次新增Step UI发现预设未显式选默认模型而空白，已修并加入默认ID断言，最终命令通过。无云认证、用户窗口或麦克风操作。余下DashScope任务WS、火山/讯飞/腾讯及Responses/Messages/Gemini仍待后续实现，不将此批当完整目标完成。


## 批3：百炼任务式实时与统一路由

`asr_streaming.py`为Session、录音能力测试、UI协议验证共用显式内置config/factory映射，禁止用户JSON指定import模块。Qwen保持原注入factory契约与成熟实现；Step和百炼不回退为Qwen。百炼默认Fun-ASR-Realtime及Paraformer-Realtime-v2，16k实现不列8k-only型号；QwenAudio streaming在未核同事件schema前不放行此新族。自定义WSS须显式填写并验证，运行时不拼model查询或复用Qwen append JSON。

依据[Fun客户端事件](https://help.aliyun.com/en/model-studio/fun-asr-client-events)、[Paraformer服务端事件](https://help.aliyun.com/zh/model-studio/paraformer-server-events)、[官方模型目录](https://help.aliyun.com/en/model-studio/asr-model)：run-task UUID与task-started/所有结果/finish-task/task-finished严格匹配；task-started前不发音频；二进制PCM帧至多3200字节，按16k单声道100ms节奏，预录探测同样限速。仅sentence_end=true汇总、heartbeat忽略；按begin_time排序，完全相同重复不增字、冲突重复或不同begin的区间重叠拒绝。未最终确认片段不能被task-finished提升为成功；task-failed/错ID/早关闭/取消/过期不返回部分结果。

第一轮WIP测试发现重叠检查未实际插入，以及保存未选realtime_url时模型门遮蔽了URL配置错误。两项已修：明确区间相交检查，所有URL先做对应协议构造校验，再能力门；四项旧secret-URL断言不变。相关实时组合255 passed/9.60s（修复后的本地TLS/WSS与离屏UI），补充测试结果随后记录；不作为真实云认证或整个供应商目标完成。

批3根独立R1为116 passed/5 failed（8.27s），R2保持旧断言不变后121 passed/8.13s。新增empty与两个未选WS URL门的补充组合首次106 passed/2 failed，错误在测试于事件循环外调用page.run；改为async scenario内await，产品代码未为此改变，最终108 passed/7.96s。原255 passed/9.60s实时组合与此补充门分别保留，不虚加成独立可靠性样本。
