# XFCE Xorg Fcitx 自动检测：缺少 GNOME schema 的候选修正

候选仅在用户会话实际报告 `XDG_CURRENT_DESKTOP=XFCE`、`XDG_SESSION_TYPE=x11`、`XMODIFIERS=@im=fcitx` 且查询 GNOME 输入源失败时，进一步要求 `gsettings list-schemas` 成功且非空、未列出 `org.gnome.desktop.input-sources`。随后仍需 toolkit 提示一致、系统 Fcitx owner 身份、插件安装状态及运行版本检查；输出时保持现有焦点、预编辑和取消保护。命令超时、程序不存在、schema 已安装但读取失败、未知桌面及 GNOME/Wayland 均不进入该例外。此阶段没有修改 IBus 自动选择。

本地 2026-10-30：`TMPDIR=/var/tmp .venv/bin/pytest -q tests/test_framework_detection.py tests/test_fcitx_preedit_guard.py tests/test_fcitx_owned_handoff.py`：117 项通过。`ruff check` 和格式化检查对应两个修改文件通过。这是隔离模拟和本地测试，并非真实桌面、包或性能验证。

待执行真实桌面复现：在隔离 Ubuntu 24.04/26.04 的 XFCE Xorg 客机，记录 `loginctl`、用户会话环境、Fcitx 版本和认证 owner；使用独立临时 schema 目录模拟缺失 GNOME 输入源 schema，先独立验证 `gsettings list-schemas` 成功且确实不列该 schema，若条件不成立则停止，不把普通系统当成缺 schema 样本。仅在候选进程使用该隔离环境，禁止改动宿主系统配置。验证实际候选选择 Fcitx、插件版本和身份；以自有 GTK 控件完成混合 Unicode、取消与当前光标样本，并用真实拼音预编辑证明拒绝输出且内容未变。另验证 schema 查询超时/安装但损坏时不选择该 Fcitx 例外；保留原始记录和失败。恢复会话与资源并关机。候选代码需独立审查，新包仍须同一 SHA 的双 Ubuntu 实包验收，以上本地测试不能代替这些步骤。
