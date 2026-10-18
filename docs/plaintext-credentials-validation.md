# 配置目录明文凭据验证

2026-10-19 用户明确要求不再使用系统密钥环，改为在配置中直接保存明文认证字段。本页记录源码修订及本机项目依赖清理；旧发布包不因源码修改而变化，新候选包的双系统验收与稳定入口更新须另行记录。

## 存储与升级行为

`FileCredentialStore(config_root)` 只使用调用方明确指定配置目录的 `credentials.json`。文件结构为 `schema_version: 1` 和 `credentials` 引用到字符串的映射。普通 API Key 保持原字符串，多字段 App ID/API Secret/Secret ID/Access Key 等保持现有 bundle 字符串格式；全部为明文，不是加密存储。普通供应商 JSON 仍只保存引用，参数中的秘密字段仍被拒绝，切换供应商预设不复用旧引用。

配置目录收紧为 0700，文件为 0600；检查所有者、普通文件、硬链接及符号链接，使用目录描述符限定路径和原子替换。格式错误或异常文件不覆盖，不把正文带入异常或日志。保护范围只限专用目录和文件，不递归限制 `/tmp` 等祖先目录。

Session、供应商表单、实际云诊断入口均绑定其 ConfigStore/显式配置根。没有默认凭据目录的无参数构造，也不会读取、迁移或删除旧系统密钥环条目。旧引用在新目录无值时清楚提示重新填写。`--config-dir` 同时隔离配置和凭据。

## 实际源码验证

所有凭据均为一次性合成值，未读取用户真实配置、密钥环或密钥，没有麦克风与云端请求。

- 首轮存储/目录权限/供应商目录/Session/UI 关联测试：169 passed，6.37 s，原句柄 58406 正常退出。
- 新增实际 Session 保存/重读/删除与双根隔离；实际 ProviderPage 的 Volc App/Access bundle 落文件、普通参数无秘密、重新加载不显示秘密、切 Groq 不复用引用。
- 最终组合：428 passed，23.99 s，原句柄 3520 正常退出。命令：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_application.py tests/test_ui.py tests/test_security.py tests/test_config.py tests/test_provider_catalog.py tests/test_performance_live_comparison.py tests/test_performance_noble_live.py tests/test_polish_stream_probe.py tests/test_realtime_silence_probe.py tests/test_performance_cloud_comparison.py`。
- `scripts/validation/credentials_probe.py` 仅在临时目录运行：实际读、更新、删除均精确成功，`real_credentials_or_keyring_accessed=false`。
- 供应商页私有合成配置截图 `build/plaintext-credentials-preparation/provider-page.png` 已由 root 实际查看：新保存说明及旧凭据重填提示排版正常。

保留开发中间结果：新增线程回调测试在受限运行环境挂起，两自有 pytest 经明确识别正常中断后仍未退出，最终终止收据为 exit 143；允许本地 socket 的环境下同一真实 Session 测试通过，不修改产品绕过。扩展组合先后出现 201 passed/4 failed（Noble 诊断 fake 缺显式 config_root）和 422 passed/6 failed（离线比较的私有 Store 缺 root），补齐临时根契约后得到上述 428 passed。这些是诊断接线修正，不隐去原结果。

## 本机依赖清理

`uv.lock` 只移除 11 个密钥环专用分发，保留其余依赖版本不变：keyring、SecretStorage、jeepney、jaraco.classes、jaraco.context、jaraco.functools、more-itertools、cryptography、cffi、pycparser、pywin32-ctypes。

root 审核 metadata-only 计划后，`uv sync --locked` 原句柄 53135 正常退出，实际从项目 `.venv` 卸载其中已安装的 10 个；Windows 专用 pywin32-ctypes 原本未安装。全部 10 个模块后置查询均不可导入。项目 editable 元数据同时由原本过时的 0.1.0a10 刷新为当时源码 0.3.1；没有升级其它分发。计划及结果保留在 `build/plaintext-credentials-preparation/dependency-cleanup-{plan,result}-r1.json`。

未卸载系统 GNOME Keyring、系统包或共享服务，未读取/删除旧条目或其他应用凭据。历史 AppImage 保留原始依赖和行为。当前稳定 0.3.0 尚未被本轮修改替换；不能把项目虚拟环境清理当作安装包已更新。

## 后续交付门

本轮普通源码提交版本为 0.3.2，不创建新 GitHub release。提交经完整检查后，构建独立候选，并以同一 SHA 在 Ubuntu 26.04 与 24.04 验证本地凭据文件、Session/UI、基本输入、九页及候选 FUSE，保全真实配置及旧包。只有实际验收通过并获 root 审阅后才更新本机稳定入口；不控制或重启用户正在运行的实例。
