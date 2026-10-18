# 云供应商与协议适配记录

## 范围与独立实现

参考本地OpenLESS提交`63be178b43e3e8084d09ff082a42dbdcbaf74d2b`的供应商目录和协议行为，其根许可证为AGPL-3.0；InkEcho为MIT。本任务不复制、翻译移植Rust实现，不链接其库；Python实现以各供应商官方协议为依据。目录不是云端可用性证明。首期不增加本地模型、OAuth账户接管、剪贴板或IME。

以下18项覆盖参考项目的完整云ASR范围，润色覆盖四种显式线协议；各批已完成下面列出的源码与本地合成协议验证。目录、mock服务与单元测试不等于真实账户、模型权限或云服务可用性。既有Qwen及整句收尾路径保留；精确源码全检和同SHA双Ubuntu新包内协议/桌面证据见[实际包验收](provider-dual-ubuntu-validation.md)，本地协议通过仍不等于云认证。

## ASR矩阵

| 供应商/参考ID | 线协议 | 凭据 | 实施与验证状态 |
| --- | --- | --- | --- |
| 火山/volcengine | gzip/二进制序列WebSocket，大模型ASR | API key或app/access/resource组合 | 批4本地WSS/二进制界限通过，云认证未验 |
| ElevenLabs | multipart speech-to-text，xi-api-key/model_id | API key | 批1本地TLS通过，云认证未验 |
| 百炼/bailian | run-task/binary PCM/finish-task WS | API key | 批3独立任务WS本地通过，云认证未验 |
| 百炼Qwen realtime | session/append/commit/finished WS | API key | 源码回归及两OS实际包local-wss/Qwen Session终态通过；真实云认证未验 |
| 百炼fun-asr-flash | multimodal-generation HTTP JSON | API key | 源码回归及两OS实际包local-wss的HTTP wire通过（固定fixture模型）；真实型号权限/云认证未验 |
| SiliconFlow | audio/transcriptions multipart | API key | 批1本地TLS通过，云认证未验 |
| StepFun | ASR专用realtime WS；HTTP按官方能力另列 | API key | 批2专用ASR WS/HTTP本地通过，云认证未验 |
| Zhipu | audio/transcriptions HTTP | API key | 批2本地TLS/30秒限制通过，云认证未验 |
| MiniMax | speech_to_text multipart | API key | 批2本地TLS通过，云认证未验 |
| Groq | audio/transcriptions multipart | API key | 批1本地TLS通过，云认证未验 |
| OpenAI/whisper | audio/transcriptions multipart | API key | 批1本地TLS通过，云认证未验 |
| OpenRouter | audio/transcriptions JSON input_audio或multipart | API key | 批1显式JSON本地TLS通过，官方支持两种；云未验 |
| OrcaRouter | 显式audio chat请求 | API key | 批2本地TLS通过；兼容字段推断，云未验 |
| ZenMux | audio/transcriptions JSON input_audio | API key | 批2本地TLS通过，云认证未验 |
| openai-compatible | 显式自选协议+端点 | API key | 批1 multipart基础，unknown模型未验证 |
| MiMo | chat/completions input_audio/asr_options JSON | API key | 批1本地TLS通过，云认证未验 |
| 讯飞/iflytek | HMAC-SHA256签名WS，status0/1/2与替换结果 | appID/API key/API secret | 批4本地WSS/bundle通过，云认证未验 |
| 腾讯/tencent-cloud | HMAC-SHA1签名WS，voice_id/index/final | appID/secretID/secretKey | 批4本地WSS/40ms分帧通过，云认证未验 |

## 润色矩阵

| 族 | 参考供应商范围 | 状态 |
| --- | --- | --- |
| Chat Completions | OpenAI/DeepSeek/Ark/SiliconFlow/AtlasCloud/MiMo/CometAPI/OpenRouter/Requesty/API Route/Orca/AlibabaCoding/CodingPlanX/MiniMax/StepFun/OpenCode/TencentTokenHub/custom | 批5显式供应商预设/旧Chat SSE本地通过，云认证未验 |
| Responses | 支持该协议的显式自定义服务 | 批5原生请求/状态绑定/终态本地TLS通过，云认证未验 |
| Messages | 支持Anthropic Messages的显式服务 | 批5专属headers/system/块顺序/SSE终态本地TLS通过，云认证未验 |
| Gemini | 官方generateContent/streamGenerateContent | 批5原生模型发现/思考过滤/STOP终态本地TLS通过，云认证未验 |

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


## 批4：讯飞、腾讯与火山实时语音

新增独立签名/二进制协议，复用Qwen仅限有界队列、active/deadline、finish等待与连接清理；各自覆盖_open/_send_audio/_event，火山另覆盖二进制_receive，不调用Qwen session.update/append/commit/session.finish或model-query。提前completed回调禁用，不将片段绕过完整终态。共享asr_wire只做direct TLS连接、受限凭据解码及精确分帧节奏，不自动重连/重发。

讯飞按host/date/request-line HMAC-SHA256签名，40ms/1280B@16k分帧，status0带配置、status1音频、status2一次收尾。60秒累计PCM上限前置拒绝，不自动拆成多次付费连接。只取每词首候选；apd/rpl闭区间修订，已处理sn摘要保留，重复不复活已替换片段、冲突拒绝。首sn可0或1，随后新sn必须连续；WebSocket本身有序，缺口/乱序失败而不猜重建。sid第一响应锁定，后续可省略、出现则一致，最终status2必须在已发送收尾后。

腾讯按官方HMAC-SHA1排序查询签名；握手code0及voice_id匹配后发送40ms二进制PCM，重组capture的3200B块为1280B帧及最后余尾，总字节精确不填充。只聚合slice_type2的indexed最终分句，去重/冲突/缺片/pending检查，最终final1且已发送一次end后才返回。目录仅旧WS实际engine类型，不把TokenHub的Hy-ASR HTTP型号冒充此族。

火山依据[大模型ASR原始帧](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelstreamingautomaticspeechrecognitionAPI?lang=zh)、[新版双向ASR](https://docs.volcengine.com/docs/DoubaoVoice/bidirectional-streaming-automatic-speech-recognition-websocket?lang=zh)、[错误码](https://docs.volcengine.com/docs/DoubaoVoice/error-code-query?lang=zh)：init为JSON/gzip，音频为raw/gzip，100ms分帧。无逐帧ACK等待，兼容async无新识别时不返回。末包按flags2/3判断，不把sequence符号当唯一条件（示例正sequence3也测）；压缩前后长度、gzip eof/尾随数据均有限额。只最终result.text返回，不拼接累计delta。原始payload示例是result/audio_info；不误把SDK解析包装层字段当必需。若payload显式含code，只接受0或20000000，不沿用旧协议1000。API Key或app/access鉴权头分别测试，资源ID显式填授权值，Request/Connect ID独立生成，不猜默认资源。

界面为每字段密码输入；单API key仍保存裸值兼容旧Qwen/润色，多字段完整bundle只存SecretStore。全留空保留整组，部分填写在任何写入前拒绝；切换火山凭据模式必须完整新组并分配新provider/ref，旧服务不覆盖。预设仍只改草稿。资源ID专用输入、静态目录明确未联网验证，不访问凭据或伪造连接成功。

本批真实本机WSS由测试服务器独立解析原始header/PCM及重算HMAC，另固定date/nonce/path排序和篡改向量，覆盖两种火山鉴权、错identity/remote error/close、取消/active失效/deadline、gzip炸弹/截断/尾随、sn修订及60秒门。`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_signed_asr.py tests/test_ui.py tests/test_provider_catalog.py tests/test_application_realtime.py`，136 passed/10.33s。历史WIP：三正常用例最初仅因测试错误要求_socket=None而失败，改为验证已await关闭的close_code；未改成熟Qwen。app/access测试首次夹具仍选API模式导致1失败，修夹具选择后39 passed/4.88s；60秒测试首次无eventloop调用生命周期导致135 passed/1 failed，改async测试后136通过。尚无云账户、麦克风、桌面输出或新包验证；Responses/Messages/Gemini等润色族仍继续实现。

根对同组合独立复测136 passed/10.28s。最后补充畸形JSON类型门（Tencent模型与Volc凭据模式）及静态发现汇总：同role/adapter/protocol聚合兼容内置模型，Paraformer不再误显示仅Fun列表，仍不读密钥、不声称连接成功。最后UI/catalog 86 passed/5.62s，纯边界选定16 passed/0.11s；这些补充与完整组合分列，不累加作独立样本。


## 批5：四种润色线协议及供应商目录

Chat Completions继续复用既有有界SSE和Session producer/consumer，不重造识别/输出流水线。新增`polish_protocols.py`独立实现Responses、Messages、Gemini的原生请求/完整响应/SSE状态；ProviderClient只按显式adapter分派。所有POST单次、不重定向、不因网络或部分输出自动重试。回调仍await背压，已发前缀不可撤回；截断、错误、提前EOF不变成正常成功、不整段fallback重放。

Responses请求`instructions`与整句input，`store=false`。依据[官方流事件](https://developers.openai.com/api/reference/resources/responses/streaming-events)，输出前必须登记assistant message与output_text part，核item_id/output_index/content_index、连续分片及前片闭合；reasoning/tool/refusal伪装delta不能先发再靠终态拒绝。output_text.done不是任务完成，只有response.completed/status=completed、登记输出项/分片闭合且完整文本一致才成功；incomplete/failed/error拒绝。sequence_number严格前进。

Messages请求专属system/messages/max_tokens，官方用x-api-key及anthropic-version。依据[流式事件](https://platform.claude.com/docs/en/build-with-claude/streaming)与[停止理由](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons)：先message_start，块index连续且前块闭合；只text_delta可输出，thinking/signature不输出，tool/refusal拒绝。message_delta可多次且usage累计覆盖、不相加，进入尾段后拒新正文；end_turn后message_stop且所有块闭合才成功。max_tokens/context_window_exceeded/tool_use/pause/refusal都不是正常润色完成。

Gemini依据[generateContent原生API](https://ai.google.dev/api/generate-content)和[header鉴权](https://ai.google.dev/gemini-api/docs/api-key)：systemInstruction/contents/generationConfig，x-goog-api-key不放URL；单次移除models/前缀后严格限制模型path字符，拒双路径、../?/#。模型发现只列supportedGenerationMethods包含generateContent的项，header鉴权分页最多10页且响应有界。仅text且thought非true可输出；STOP才完成，MAX_TOKENS/SAFETY/CONTINUATION等失败，不发送function/binary内容。

请求参数仅允许各协议明确数值控制，有限值与类型前置门（bool不当数字、JSON层也拒NaN/Infinity）；stream单事件/累计字节/累计文字沿用既有限额，非流式也限制200000字符。模型发现与调用使用该协议headers，无秘密query，无新增tools/OAuth/本地模型能力。

Chat目录覆盖OpenAI、DeepSeek、Ark、SiliconFlow、AtlasCloud、MiMo、CometAPI、OpenRouter、Requesty、API Route、Orca、百炼通用API、CodingPlanX、MiniMax、StepFun、OpenCode Zen、Tencent TokenHub及自定义；模型ID保留手填/显式发现，不把预设或静态型号称认证可用。参考AlibabaCoding在[当前官方FAQ](https://help.aliyun.com/en/model-studio/coding-plan-faq)限定交互AI编程；应用润色默认提供百炼通用API，保留该参考差异，不读key前缀或封锁用户显式自定义URL。OpenCode[官方协议表](https://docs.opencode.ai/docs/zen/)按模型分Chat/Responses，提供两个显式预设。

目录官方出处补充：[AtlasCloud](https://www.atlascloud.ai/docs/llm-protocols)、[Requesty](https://docs.requesty.ai/)、[API Route](https://www.api-route.com/)、[CometAPI](https://www.cometapi.com/quickstart/)、[CodingPlanX](https://codingplanx.ai/docs/dify)、[TokenHub](https://cloud.tencent.com/document/product/1823/130079)、[Ark](https://docs.volcengine.com/docs/ark/chat-api?lang=en)。MiniMax以[当前OpenAI兼容文档](https://platform.minimax.io/docs/api-reference/text-openai-api)的api.minimax.io为默认（不擅自重写旧用户域名）；官方主机+精确M2/M3型号默认reasoning_split=true并拒false，避免其content包含思考，不给未知gateway/未来型号猜参数，不全局剥除用户正文里的think标签。另[官方Messages](https://platform.minimax.io/docs/api-reference/text-anthropic-api)提供独立preset，按其/anthropic/v1与Bearer示例窄处理，原生Anthropic仍x-api-key。

UI预设每次分配新provider/ref，原配置与凭据不覆盖；润色提示明确所选线协议。语音协议combo按adapter禁用不兼容选项（Qwen只有HTTP/Qwen实时）；旧未知/非法JSON保留并明确报错，不默默迁移。无联网目录不声称连接成功。

验证：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_polish_protocols.py tests/test_polish_stream.py tests/test_runtime_streaming.py tests/test_application_streaming.py tests/test_providers.py tests/test_ui.py tests/test_provider_catalog.py`，368 passed/19.53s，允许本机TLS的运行环境；包含三族实际TLS非流式/完整SSE/headers/body、错终态/HTTP200 error/EOF/部分取消/首字早于final及timeout不重发、分页/模型路径/数值限额、Chat各预设同族wire、现有Session partial-no-replay回归。此前核心350 passed/18.34s、旧Chat+三族130 passed/6.74s分别为逐步证据，不加作独立可靠性统计。首次扩TLS夹具在requests记录新增headers破坏一旧exact断言，改独立headers记录后68通过；数值坏例NaN/Infinity最初6项被更早ConfigError阻断，测试按实际层次断言，无放宽产品。根早期独立组合96 passed/4.71s。尚未认证云账户、实用模型权限、麦克风/桌面输出或新AppImage，不继承v0.2.0包证据。


批5最终审查补：Responses跨output_item同样在回调前要求前项done，实际TLS交错第二项不发出；未注册item、错item/part gap实际TLS均0callback。Messages has_more=true但last_id缺失/空/非str明确失败，不把截断模型列表报成功。最终同关联命令376 passed/19.79s；根独立此前368 passed/19.29s，最新三族/Chat156 passed/8.30s，diff检查通过。预设、协议顺序、异常类型及模型发现为源码本地证据，最终当前提交全检/实际新包和同SHA双系统尚待后续门。

最终集成首轮完整检查精确b35937a：Ruff/format318通过，pytest为1896 passed/1 failed/3 skipped，63.34s。唯一失败是tests/test_application.py仍断言旧“连接方式与模型协议不匹配”文案；实际新提示明确模型能力/协议及所选供应商转写方式，diagnostics=[protocol]、禁止权限/key/audio前置门均通过。仅更新该提示断言并补具体供应商/模型/转写方式提示检查，未改产品或安全门。关联`tests/test_application.py tests/test_provider_capability.py`为73 passed/0.54s；当前提交完整检查结果后续另记，不将首轮失败抹为通过。

## 最终源码与包诊断准备

根对修正后的clean `2e5f1d8910e10b17ed91566b42b9ab0c2109fafb`完成正式完整检查：Ruff/format318通过，1897 passed/3 skipped，63.26s，receipt evidence SHA-256为`8fa90643ba27a68511c67fdc089c6bb4380d5118257b3fc87dcbefad8b07d93d`。前述b359首轮文案断言失败仍保留。本轮后续诊断/规范提交各自改变HEAD，最后仍须精确最终HEAD的新完整收据。

新产品树55文件（旧44+本轮11）与新协议来源审计须全部进入实际包门。`artifact_scope`显式加入十一模块，连Hybrid为30项；每个origin要求在实际包内并匹配inventory。另比较实际`packages/inkecho`与冻源完整文件集合及逐字节hash，拒缺失、额外源、单边冻源修改、包与inventory一并改写但不符冻结来源的情况，排除__pycache__且拒source symlink。mixed验收要求完整模块集合和冻源绑定，旧19/44不能直接通过；不以放宽计数冒充新模块已验。

薄`provider_package_probe.py`只用于后续实际包：真实AppDir Python `-I`、独立pytest配置、不加src overlay、固定五个协议测试模块及精确node IDs；框架pytest/pluggy/iniconfig/packaging/pygments按distribution文件清单另行冻结，仅为诊断例外，不进入AppImage。禁自动插件并清用户pytest环境；前后audit+所有实际加载inkecho.*与runtime dependencies的origin/inventory必须包内，框架与namespace路径也核独立hash/目录。任何失败停、不自动重跑，当前尚未运行新包，不将此工具的纯测试称作AppImage结果。

signed本地WSS夹具现在经共享streaming_config/create_streaming_session实际工厂选路，独立服务端断言不变；根复测45 passed/4.90s。诊断最终关联命令`.venv/bin/pytest -q tests/test_provider_package_probe.py tests/test_artifact_acceptance_controls.py tests/test_package_factory_mixed.py tests/test_signed_asr.py`为115 passed/5.02s，包括完整源set/hash、缺新module同计数替换、未知extra origin、源码预加载来源、框架overlay/namespace与清单篡改拒绝。无新build、GUI、stable变更或推送；下一步固定同包双Ubuntu实际验证，旧冻结工具不改写。

诊断框架实际失败保留：初次准备R1因pytest distribution含顶层`py.py`而停止；R2错误推断它是未用compat shim而显式排除。随后实际`18b6ad26a39032d930a2f319cd497641639910f69cb3402da8ac75ee7d2a63bd`的0.2.10包Python `-I`首次host协议运行，在`_pytest.compat`导入`py`时ModuleNotFoundError，原子进程及外层owner均终态1，0测试/无协议请求/无GUI或输入；`protocol-host-r1`原始stderr、terminal与57保全记录保留。Host环境collect-only成功不能证明隔离框架齐全，不能写为包协议通过。旧包、55产品源和frozen-r1没有修改或重建。

最小修正仅诊断工具：允许pytest distribution-owned顶层`py.py`，不允许另一个`py/`包；`py.error`/`py.path`别名必须仍指向冻结`_pytest/_py`文件并逐hash核。增加真实包可用的显式`--collect-only`，结果标识`execution_kind=collection_only`且call passed=0，绝不冒充226实际测试；下一次先用包`-I`完成隔离收集，再经审核原owner运行同ID集合。纯controls关联72 passed/0.21s，根独立pyshim相关15 passed/0.08s。这是诊断后继修复，产品协议/0.2.10产物不变；后续新helper与framework独立pin，旧失败材料不改。

第二次实际包隔离收集R2保留为失败：226个ID已收集、0个测试调用，但后置来源审计将PySide6内嵌模块的虚拟`shibokensupport/...py`当作物理文件，触发FileNotFoundError，原owner终态1；未进入协议测试。`protocol-host-r2-collection`原始输出及保全收据保留，不改旧包或冻结来源。

修复仅限诊断来源门：精确PySide6.support别名必须绑定真实signature_bootstrap.EmbeddableZipImporter、原模块身份和_mod2path，嵌入zip必须与其16段base64向量一致；每段均须存在库存逐hash验证的实际libshiboken载体，其SHA-256为`2b3d9767d69da0afabe4a383dc241a110fac4c0bb63cdeb3d01314e9c702241e`。记录logical origin、member/archive/carrier hash，不开放其他虚拟或外部来源。实际0.2.10包Python `-I`只读验证`build/provider-acceptance-preparation/verify-embedded-origin-r1.py`终态0，结果`verified-embedded-origin-r1.json`为11个嵌入alias、17个runtime origins全部通过；这不是226协议测试通过。嵌入archive为44302字节，SHA-256为`366442b9b65c9f6d1af0109aaedd553429e93183e4a5e3b5a6c290d36798f428`。关联三个诊断测试文件80 passed/0.20s，Ruff/format通过；根独立controls23 passed/0.09s。下一轮用独立helper/provenance及fresh路径继续同一产品包的隔离收集与协议测试，旧R1/R2不改写。

实际包Host R3已通过隔离收集（226 IDs、0call测试）及随后独立226协议测试：226 passed/0 skipped/0 failed，20.61s，原两owner均wait0；30 before/after origins、55产品源、286实际加载依赖（含精确嵌入来源）、57保全及413冻源一致。原始材料位于`build/provider-acceptance-preparation/protocol-host-r3-{collection,tests}`，helper来源a6f34da，产品仍de504c6/0.2.10/18b6ad26，不把后继诊断版本称产品版本。

桌面Host R1首UI门原wait1并停整批，其余24项未执行；旧诊断要求不兼容模型仍在列表并有tooltip，实际新需求已将其过滤，因而两个旧tooltip检查为false，私有保存/重载检查为true、stderr空。保留results-r1原始失败，不归为产品模型过滤失败。更新诊断检查实际HTTP/实时协议切换无需重新发现就重过滤，固定发现同时加入纯文本与TTS负例；仍仅一次发现、不写真实凭据、手填实时模型后正确协议保存/重载。新增真实ProviderPage私有ConfigStore回归，关联新诊断测试与UI为72 passed/6.15s；产品、旧冻源与AppImage不改。


## 同包双系统最终交付

实际0.2.10包固定来源de504c6、SHA-256 `18b6ad26a39032d930a2f319cd497641639910f69cb3402da8ac75ee7d2a63bd`，在Ubuntu26.04.1/GNOME50.1 Wayland+XWayland及Ubuntu24.04.5/GNOME46实际KVM Xorg分别完成实际包隔离收集、相同226项本地协议测试和25/9桌面门。两系统九页由主Agent逐页视觉审阅通过，协议/guard/取消/映射恢复及原owner终态均核验。随后版本化候选实际FUSE启动核3970files/1048links/55源码/9页/原wait0通过，主Agent审定后只更新稳定AppImage及sidecar；其他57路径与用户配置/集成均保留。完整复现材料、诊断来源与失败历史、产品0.2.10和后继报告版本区分、未测云账户等限制见[实际包验收](provider-dual-ubuntu-validation.md)。最终源码推送和主分支合并由主Agent在精确最终HEAD完整检查后执行，不为外部终态再制造报告提交。
