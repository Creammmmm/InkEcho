# XIM 同步与 Ubuntu 24 XFCE 验证汇总

[XIM 私有双端实验](../xim-sync-private-20261030/README.md)由作者和独立审查者分别在隔离 Xvfb 中复跑通过。同步 COMMIT 的回复触发了后续显式同步回调；这是限定范围的协议反例，不证明真实桌面应用的显示或跨后端交付。首次启动的磁盘配额与 GLX 故障，以及依赖、复现步骤和未覆盖情况均在原记录中。

[Ubuntu 24.04 XFCE Xorg 证据](../xfce24-schema-desktop-015-20261030/REPORT.md)记录相同环境下原版与候选 Fcitx 检测的对照、完整 Session 以及独立拼音预编辑保护。该实验仅覆盖已发布包上的单文件源码覆盖，不能当成新包验收；实际 schema 查询超时、其他应用、真实麦克风和云端未覆盖。

两项均不构成 IBus 到 XWayland 跨后端问题已修复的证明。最终提交的代码与完整测试检查由本地 workflow 记录，不替代双 Ubuntu 同一 SHA 的实际包验收。
