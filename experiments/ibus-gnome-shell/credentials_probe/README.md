# 私有 IBus 连接身份方法对照

目标：检查除已测 `GetConnectionUnixProcessID` 外，标准 D-Bus 的 `GetConnectionCredentials`、`GetConnectionUnixUser` 或 `GetConnectionSELinuxSecurityContext` 是否能为透明关联焦点提供进程或身份元数据。本实验只查询自建进程自己的唯一连接名；不查询其他进程或正文、不使用用户 IBus。

`bash experiments/ibus-gnome-shell/credentials_probe/run.sh` 创建临时 HOME、私有 session bus 与 IBus daemon，需要 IBus、PyGObject 和 Unix socket 权限。结束后停止私有 daemon 并清理临时目录。

2026-10-28 在 Ubuntu 26.04.1、IBus 1.5.34-rc2 的私有会话中，`GetNameOwner` 对自身唯一名称的正向对照通过；上述四种方法均返回 `org.freedesktop.DBus.Error.UnknownMethod`，脚本退出 0。静态 Ruff 检查通过。`probe.py` SHA-256 为 `f93aabd2c9ff7164a95713c1f704d95a0c897e53cb6a9b9a3f3312cc427e1bcf`，`run.sh` 为 `a075c81cbfa4b654eea804189b91a25d98c794b3b72d960d8274586915daf2a0`。

这排除了在此受测实现中通过这些方法直接查取该私有总线连接身份的候选路径；不证明其他 IBus 版本都相同。即使其他版本返回 PID，跨进程中间层、同进程多个窗口或控件、焦点变化及未确认投递仍需独立解决。此实验未提供自动选路或可靠投递方案。
