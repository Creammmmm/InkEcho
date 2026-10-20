# 模型配置引导验证（2026-10-21）

## 本轮范围

模型配置表单上方新增紧凑引导卡。摘要和已核实的固定平台链接常显，详细中文步骤由按钮展开。新建时提示先选择服务平台；选择后说明服务开通、凭据获取、模型与协议、保存与连接检查。Qwen 实时提示 16 kHz 与模型/方式配对；讯飞、腾讯与火山显示各自组合凭据/资源；MiniMax 国内语音入口与海外入口分开。

引导是静态离线元数据，不查询模型、不访问凭据、不更改配置、不自动打开网页。用户主动点击链接才交给系统浏览器。页面始终不把用户输入的名称、地址或密钥插入 HTML。改变 Base URL 后立刻移除原官方链接；保存的未知模型不妨碍按角色、适配器、完整官方接入地址与合法协议识别平台。相同适配器的自定义网关没有官方密钥链接。

## 官方入口核实

2026-10-21 使用网页工具读取官方公开页面；以下为引导元数据的主要依据，非登录后账户或付费 API 验证：

- [百炼获取 API Key](https://help.aliyun.com/zh/model-studio/get-api-key)：读取了地域、Key 与地址的对应要求。
- [讯飞流式听写](https://www.xfyun.cn/doc/asr/voicedictation/API.html)、[腾讯实时识别](https://cloud.tencent.com/document/product/1093/48982)、[豆包语音控制台指引](https://docs.volcengine.com/docs/DoubaoVoice/console-guidance?lang=zh)、[方舟快速开始](https://docs.volcengine.com/docs/ark/quick-start?lang=zh)。
- [OpenAI 快速开始](https://developers.openai.com/api/docs/quickstart)、[Claude API](https://platform.claude.com/docs/en/api/overview)、[Gemini 密钥](https://ai.google.dev/gemini-api/docs/api-key)、[DeepSeek 快速开始](https://api-docs.deepseek.com/)。
- [Groq 快速开始](https://console.groq.com/docs/quickstart)、[硅基流动官方配置示例](https://docs.siliconflow.cn/docs/usercases/use-siliconcloud-in-trancy)、[OpenRouter 快速开始](https://openrouter.ai/docs/quickstart)、[ElevenLabs 认证](https://elevenlabs.io/docs/api-reference/authentication)。
- [阶跃星辰平台](https://platform.stepfun.com/)、[智谱平台介绍](https://docs.bigmodel.cn/cn/guide/start/introduction)、[小米 MiMo 平台](https://platform.xiaomimimo.com/)、[MiniMax 海外平台](https://platform.minimax.io/)、[MiniMax 国内平台](https://platform.minimax.cn/)。后三个为公开主页/文档入口；未猜测密钥管理深层路径。
- [ZenMux 快速开始](https://docs.zenmux.ai/guide/quickstart.html)、[OrcaRouter 官方帮助](https://www.orcarouter.ai/support)、[AtlasCloud 密钥文档](https://www.atlascloud.ai/docs/en/api-keys)、[CometAPI 快速开始](https://www.cometapi.com/quickstart/)、[Requesty 快速开始](https://docs.requesty.ai/quickstart)、[API Route 官网](https://www.api-route.com/)、[CodingPlanX 文档](https://codingplanx.ai/docs)、[OpenCode 文档](https://opencode.ai/docs/zen/)。

部分控制台仅返回登录页或需浏览器运行脚本，这里不声称已验证登录后的按钮或 Key 权限。TokenHub 未取得可核实的公开官方引导地址，因此界面明确提示以服务方提供的地址为准，不提供猜测链接。MiniMax 的尝试深层文档链接无法读取，最终只保留已能读取的官方主页入口。若控制台与文档入口相同，仅显示一个链接。

## 本地验证

运行：

```sh
.venv/bin/ruff check src/inkecho/provider_guidance.py src/inkecho/ui/providers.py tests/test_provider_guidance.py
.venv/bin/pytest -q tests/test_provider_guidance.py tests/test_ui_protocol_acceptance.py
.venv/bin/python build/provider-onboarding-20261021/screenshots.py
```

实际结果：Ruff 通过；57 项测试通过。覆盖全部 46 个平台/协议预设、凭据组、HTTP/实时说明、未选平台、保存的未知模型、恶意相似域名、带认证信息/查询参数地址、未选或非法协议不伪称实时，以及页面动态切换。页面测试只使用临时配置，不具备凭据读取或联网客户端，切换与展开前后 JSON 字节保持一致。

在隔离 offscreen Qt 环境生成 940×700 与 1120×850 两种尺寸、百炼/讯飞/DeepSeek 的折叠及展开共 12 张截图，目录 `build/provider-onboarding-20261021/`。已实际查看 940×700 百炼展开截图：引导在第一屏可见，正文换行与链接清晰，长表单通过原有滚动容器访问。截图属于源码离屏布局检查，不代表实际桌面或 AppImage 验收。

打包、双 Ubuntu 实际包验收、旧版替换记录由该轮独立包验收报告补充；本记录不替代其证据。
