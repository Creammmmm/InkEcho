# IBus 私有会话暂停目标实验

在独立 D-Bus 会话和临时 HOME 中启动私有 IBus daemon；自建子进程创建并聚焦合成 InputContext，主进程持有私有 panel。确认当前上下文为子进程后，对该子进程发送 SIGSTOP，等待 `/proc` 确认停止，再调用 panel 的 `commit_text` 和连接 flush。0.4 秒内检查子进程回调标记不存在，随后 SIGCONT 并检查回调标记出现。实验只发送自造的单字，不读取用户正文，不连接用户 IBus、不变更输入法。退出时恢复子进程并清理临时文件。

运行：`bash experiments/ibus-gnome-shell/paused_client_probe/run.sh`（需允许本机 Unix socket）。最终源码 SHA-256：`probe.py` 为 `5dfa9a08b1553bce8ec2b2c3b96431543f3b0c802f008a05d4b384e5df4871ce`，`run.sh` 为 `a075c81cbfa4b654eea804189b91a25d98c794b3b72d960d8274586915daf2a0`。

2026-10-28 本机私有会话最终源码运行退出 0：提交返回 `None`，含 flush 耗时 0.939 ms；停止期间 400 ms 无回调，恢复后出现回调。GLib 输出一次 `g_object_is_floating` 警告。实验不是实际文本控件，也没有确认用户应用显示或保存文字；它证明此场景下提交返回及连接 flush 不等待客户端回调，不能作为目标应用已处理或送达确认。首次格式化前运行同样观察到 0.534 ms 和相同顺序；最终源码已重新运行。此结果不提供安全自动选路或投递确认机制。
