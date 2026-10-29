# GTK 控件与无控件上下文的能力位对照

此实验检查 `SetCapabilities` 元数据能否作为自动选择的控件关联证据。私有 Broadway 和 IBus 中先启动一个自建 GTK3 Window/Entry，监控仅限 `InputContext.SetCapabilities` 方法调用；待 GTK 进程退出后，再在同一个私有 IBus 创建一个没有控件和接收处理器的上下文，明确设置相同能力位并将其聚焦。未发送、读取或监视文字，也不连接真实用户输入法或会话。

运行 `bash experiments/ibus-gnome-shell/capability_widget_probe/run.sh`，需要 GTK3、Broadway、IBus、PyGObject 和本机 Unix socket 权限。退出时结束独立进程并清理临时目录。

2026-10-28 Ubuntu 26.04.1 / IBus 1.5.34-rc2：GTK 进程的 SetCapabilities 参数为 41；随后无控件上下文同样上报 41 并成为 IBus 当前上下文。脚本退出 0。D-Bus 不支持新式监控并回退 eavesdrop；GTK 在私有会话中启动了辅助功能总线。首次只观测 GTK，得到 41，最终对照脚本重跑得到两个 41。Ruff 检查通过。最终运行源码 SHA-256：`actor.py` `65a51cffd6a5aadd2b934929d3a4388669302511e57643a4bf7de3b3a0de4b30`、`probe.py` `0353fff36d5aef59c4899a7c4d21bfbcb33113ec7a5f6dab1ae73f7af4aaef02`、`run.sh` `a075c81cbfa4b654eea804189b91a25d98c794b3b72d960d8274586915daf2a0`。

结果表明单凭所观测的能力位不能区分有无控件；它们可由上下文自行声明。GTK 控件在 Broadway 无外部显示客户端下未验证实际焦点及接收，仅证明其创建上下文时发出的能力位，不能视为真实桌面支持或投递成功。观察也存在启动前盲区；其他版本、其他应用和并发切窗没有覆盖。该结果没有证明组合其他独立可靠信号不可行。
