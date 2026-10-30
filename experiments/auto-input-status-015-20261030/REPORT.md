# 自动输入状态文字验证

变更：自动输出状态文字列出 Fcitx5 与 GNOME IBus 输入桥，并说明条件不满足时可能使用键盘或停止。这只修正提示，不改变后端选择、输入或兼容范围。

2026-10-30 本地源码验证：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_explicit_owned_ui.py`，2 项通过；`.venv/bin/ruff check src/inkecho/ui/information.py tests/test_explicit_owned_ui.py` 和 `.venv/bin/ruff format --check src/inkecho/ui/information.py tests/test_explicit_owned_ui.py` 均通过。测试使用 offscreen Qt 和测试会话，验证设置状态提示和已有显式选项；未运行真实桌面、键盘、输入法、录音或云端，不构成实际兼容性验收。
