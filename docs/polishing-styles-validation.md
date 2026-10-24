# 润色模板与当前风格高亮验证

## 变更与参考

参考本地 OpenLess 仓库 `/home/lth/github/openless`，提交
`63be178b43e3e8084d09ff082a42dbdcbaf74d2b`：

- `openless-all/app/crates/openless-core/src/style_packs.rs`：通用规则、轻度整理、结构化与正式表达。
- `openless-all/app/crates/openless-core/src/prompts/style_chat.md`：聊天消息的口语、短回复与少标点。
- `openless-all/app/crates/openless-core/src/prompts.rs`：了解模板与调用封装的边界。

采用结构化中文规则、场景差异、明确改口、技术符号保护与上下文纠错思路。
没有引入其热词占位符、上下文或 XML 封装，没有改变调用协议。没有照搬会强化
“可能”为确定结论或添加落款的示例。InkEcho 明确保留不确定性，不补充事实。

四个内置 ID 不变：忠实整理最小修改；社交聊天保留自然口语并减少标点；
编程智能体只整理要求、不执行开发；正式邮件克制书面化、不虚构称呼或承诺。
共同规则保护有意义的“嗯嗯／哦／好”、半句话、技术标识与完整版本号，
并结合上下文处理同音、近音、近形及断词错误；有歧义则保留。

当前应用的模板卡片使用浅蓝背景、深蓝边框及白字“✓ 当前使用”标记，
描述和按钮保持深色文字，标题与标记并列，不额外占用整行。颜色与文字双重提示适用于内置和自定义模板。
打开详情、复制或保存个人副本不会自动切换当前模板；仍需“设为当前模板”。
未选中的可访问名称使用“非当前风格”，避免误示模板被禁用。

## 离线功能检查

在项目虚拟环境运行：

```sh
.venv/bin/pytest -q tests/test_config.py tests/test_ui.py \
  -k 'builtin or style_highlight or copying_and_deleting'
.venv/bin/ruff check src/inkecho/config.py src/inkecho/ui/prompts.py \
  src/inkecho/ui/widgets.py tests/test_config.py tests/test_ui.py
.venv/bin/ruff format --check src/inkecho/config.py src/inkecho/ui/prompts.py \
  src/inkecho/ui/widgets.py tests/test_config.py tests/test_ui.py
```

结果：7 项通过（127 项未选取），Ruff 检查及格式检查通过。
检查覆盖：保留内置 ID、现有自定义正文和选择、读入内置新版规则时不重写设置、
编辑和保存副本不改变当前高亮、选择自定义后重新打开仍正确、删除当前自定义回到
忠实整理、删除非当前副本不改变当前选择，以及内置模板不可删除。

另一次较广检查 `.venv/bin/pytest -q tests/test_config.py tests/test_ui.py` 在后段停滞，
人工中断（退出 130），不计为通过。使用 `-vv -o faulthandler_timeout=30` 定位复现：
`test_provider_page_persists_bundle_in_own_config_file` 在 `tests/test_ui.py:1179`
的 `asyncio.run` 清理阶段等待，栈为 `asyncio.runners.close` →
`run_until_complete` → `selectors.select`。诊断日志保存在忽略目录
`build/polishing-styles/focused-ui.log`，诊断运行同样人工中断（退出 130）。
本次没有修改或跳过该测试，也没有将该次较广检查记为成功。

主 Agent 随后在正常执行权限下单独运行上述供应商测试：1 项通过，耗时 0.27 秒，
原始进程正常退出 0，日志 `build/polishing-styles/provider-isolated-check.log`。
在同样权限下重新运行 `tests/test_config.py tests/test_ui.py`：134 项通过，
耗时 6.88 秒，原始进程正常退出 0，日志 `build/polishing-styles/config-ui-check-r2.log`。
没有修改、跳过测试或变更供应商代码。前述停滞发生于受限执行环境；这里只记录两种
执行环境的实际差异，不据此断言停滞的根本原因。最终完整检查仍由主 Agent 单独完成。

## 界面查看

使用 `QT_QPA_PLATFORM=offscreen`，1080 × 860 的独立滚动页面，
临时 ConfigStore；未创建真实录音会话、读取用户配置或连接云端。
截图生成入口为忽略目录中的 `build/polishing-styles/capture.py`：

```sh
QT_QPA_PLATFORM=offscreen PYTHONPATH=src \
  .venv/bin/python build/polishing-styles/capture.py
```

生成 `builtin-grid.png`、`social-selected.png`、`custom-selected.png`、
`long-editor.png`，位于 `build/polishing-styles/`。检查初始卡片、切换聊天风格、
选用个人副本及展开另一内置长模板：仅实际选用卡片显示蓝色和标记，详情编辑器
可滚动，保存、选用、复制、删除及收起按钮保留。
主 Agent 已实际查看初始卡片、自定义选中及其他详情截图，验收紧凑的标题与标记并列布局、
当前风格高亮，以及编辑其他模板时不改变当前风格的表现。

这些是源码与离屏界面验证，不代表 Ubuntu 24.04／26.04 桌面或 AppImage 验收。
未调用真实模型，模板契约检查不能证明模型的实际纠错准确率；不同模型仍可能
不遵循规则。本次未打包、发布或替换本机安装。
