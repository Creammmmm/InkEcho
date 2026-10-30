# Ubuntu 26 Mutter RemoteDesktop 双连接 Stop 权限（本地摘要）

在隔离 Ubuntu 26 GNOME Wayland 客机，用两条独立 session D-Bus 连接、应用包运行时及源码覆盖调用真实 Mutter RemoteDesktop。未发送按键、未创建虚拟键盘、未设置或更改键盘映射。A 创建并启动自己的会话，B 是不同的 D-Bus unique sender；B 对 A 的会话调用 Stop 得到 org.freedesktop.DBus.Error.AccessDenied。之后 A 再次 Introspect 获得成功返回，A 自行 Stop 成功并收到 Closed，两个连接断开。

该实验只证明这一台客机、该会话的 Stop 访问结果。没有验证 SetKeymap 或 NotifyKeyboard 是否有相同限制，也没有测试 A 终止后的跨会话按键释放、映射恢复、外部并发变更或 Ubuntu 24。当前没有可靠的独立恢复验证，因此未对键盘映射做任何改动；不得将本结果用作恢复安全性的证明。

本地 two-sender.json、输入脚本与 run.log 保留了按时间排序的调用结果；原始会话地址等内容不应直接上传。prepare 成功，关机前日志记录 overlay 清理、XFCE/X11 用户环境和共享目录卸载，但用户环境不单独证明活动图形会话状态。容器和 QEMU 正常退出，客机归档完整流校验为真。
