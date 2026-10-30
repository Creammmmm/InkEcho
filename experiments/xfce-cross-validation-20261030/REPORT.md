# XFCE Fcitx 检测与跨客户端输出验证汇总

XFCE Xorg 缺少 GNOME schema 时的 Fcitx 检测修正，针对性本地测试 117 项通过，Ruff 检查与格式检查通过；详见[候选验证记录](../xfce-fcitx-schema-fallback-20261030/REPORT.md)。Ubuntu 26.04 XFCE Xorg 的旧版/候选对照、完整 Session 和独立拼音预编辑保护见[桌面证据](../xfce-schema-desktop-015-20261030/REPORT.md)：该实验是已发布包上的单文件源码覆盖，非未修改包验收；Ubuntu 24 XFCE 与实际超时尚未验证。

已发布 0.15.0 包在 Ubuntu 24.04 和 26.04 原生 Wayland 中的受控 Fcitx 跨客户端 Session 样本见[跨客户端证据](../fcitx-cross-session-015-20261030/REPORT.md)。取消时存在已发送或晚到前缀；两个客户端是相同 GTK 测试程序，不证明跨应用、跨后端或所有取消竞态。

两项证据的实际会话、源与包的关系、失败和未覆盖条件以各报告为准；这些结果不证明完整输入法适配目标已完成。最终提交的 Ruff 与完整 pytest 检查由本地 workflow 记录，不替代实际包验收。
