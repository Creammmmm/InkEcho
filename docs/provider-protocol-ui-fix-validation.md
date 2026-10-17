# 模型协议提示刷新修复 — 2026-10-17

本模块只修复供应商页的本地模型标注，不改变 HTTP/WSS 请求、协议支持范围或用户
配置。修改文件为 `src/inkecho/ui/providers.py` 和 `tests/test_ui.py`，起始检查点为
`8594179e5f05d9bc433698d1de0cb1fb8aac589b`。没有部署、安装、改版本或再次访问云端。

## 已确认的问题

模型发现原来用当时的配置运行 `validate_provider_protocol`，把所有 ProviderError
都计入“协议尚不支持”。因此默认 HTTP 下的 `qwen3-asr-flash-realtime` 会被误读成
应用全局不支持；自定义服务缺少 WSS、请求参数错误等配置问题也可能把整表标红。
此外，颜色与 tooltip 只在发现时生成，切换协议、URL 或 JSON 后不会更新；即便主提示
已显示“已选择边录边识别”，列表仍可能保留旧红色与“不支持”汇总。

这是当前源码中独立存在的 UI 缺陷，不是 Ubuntu 26.04 的协议禁用判断。另由唯一
操作者完成的入口核查显示，桌面稳定别名仍是旧 a9，检查时没有应用进程；旧 a9 没有
实时模块或选择器。源码支持实时与旧入口已经获得新功能是两回事，本模块没有替换
稳定入口，也不据此声称已完成 a14 或两个 Ubuntu 版本的实际包验收。

## 修复行为与保留的边界

现有 `update_model_hint` 集中触发轻量本地标注刷新：先清除每项旧颜色和 tooltip，
再按当前配置重算。现有模型、协议、URL、JSON 变化信号都会经过此入口，没有新增
状态机或异步请求。配置无效时只显示既有配置/JSON 提示，不把它算成模型协议不支持。
有效 HTTP / Qwen 实时配置之间切换，原列表立即重绘，无需再次获取列表。

标红仅表示与当前转写方式不匹配：实时模型提示手动切换 Qwen 实时后测试能力，
HTTP 模型提示切回 HTTP；filetrans 和尚未实现的 streaming 协议明确说明未实现。
发现汇总保留总模型数和“尚未验证模型能力”，不再保存会过期的“不支持 N 个”数量。
列表在信号屏蔽下重建并恢复原选中值，再统一刷新，避免内部填充造成重复表单编辑。

标注逻辑不更改模型、协议、参数 JSON、采样率、密钥或配置文件；坏 JSON 原文与
未知字段仍保留。用户主动操作协议控件的原有 JSON 合并行为不变。HTTP 不能直接
使用实时模型的预检、实时 16 kHz 限制、URL 安全校验及 save 前不读写密钥的顺序均
未放松；有效实时能力测试仍走实际 Qwen WSS 适配器。模型列表成功不等于能力通过，
本模块也不自动触发能力测试。原 revision 检查继续阻止迟到请求覆盖新表单。

## 可复现的本地结果

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_ui.py
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_ui.py tests/test_providers.py tests/test_application_realtime.py tests/test_provider_capability.py tests/test_realtime.py tests/test_polish_stream.py
.venv/bin/ruff check src/inkecho/ui/providers.py tests/test_ui.py
.venv/bin/ruff format --check src/inkecho/ui/providers.py tests/test_ui.py
```

离屏 UI **52 passed，4.59 秒**；六文件相关回归 **344 passed，14.05 秒**；Ruff
lint 和格式检查通过。TLS/WSS 测试在获准绑定本机回环服务的环境执行，只使用生成
音频、测试证书和假密钥；没有真实系统凭据读取、麦克风采集、云请求或可见桌面操作。

新增回归覆盖：

- HTTP → 实时 → HTTP 的颜色/tooltip 可逆变化，filetrans 仍明确未实现；不重新联网，
  原模型、未保存密钥、采样率及已保存 JSON 字节不变。
- 修改 Base URL、WSS 地址、模型或高级参数造成配置错误时，清除旧标注；手动修正后
  恢复当前方式的正确标注。首次发现时缺少自定义 WSS 也不把所有模型标成“不支持”。
- 直接编辑 JSON 同样刷新；坏 JSON 在 URL/协议控件变化后仍原样保留，修复后重新
  标注，不偷偷改采样率或删除用户字段。
- 发现请求 await 期间切换协议或 JSON，旧模型列表和旧状态不会落入新表单。

现有回归同时保留能力预检在 key/mic/network 之前拒绝错误协议或采样率、显式实时
能力路由且不注入正文、实际本机 WSS 的分帧/最终结果/取消/超时清理，以及 SSE 的
协议边界。这里的离屏与本地 TLS 结果不冒充真实账户能力、实际包双系统或全平台支持。
后续打包和实际 Ubuntu 24.04 / 26.04 验收由独立阶段记录。

本模块提交后的完整检查结果以 `.git/validation/<HEAD>.json` 绑定本报告的精确提交
记录为准；不提前声明新提交、完整工作流、安装或发布已完成。
