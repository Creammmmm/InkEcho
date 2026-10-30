# Ubuntu 24/26 Wayland：取消派发统计实际 Session 复测

2026-10-31 顺序在隔离 Ubuntu 24.04 与 26.04 GNOME Wayland 客机测试，logind 均记录 seat0 用户会话 active/wayland。使用同一个 0.15.0 AppImage（SHA-256 `94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a`）的运行时和依赖，`inkecho` 目录覆盖为提交 `b4392561d711` 的源码；启动器比较覆盖树中 94 个常规文件的路径集合及逐项哈希（包括非 Python 资源，不含符号链接）。其中 `wayland_keyboard.py` SHA-256 `c61c002e0aefe40402ba430be63d37a21290b883ee30469fbaab33512234d43a`，`hybrid_keyboard.py` SHA-256 `02818c227f9e298d48f224457fe95008a7ce54e1cd9ec9f05ff653881240ec34`。两系统相同探针 SHA-256 `883d3d030780a43501ec6e1b6352b22229dff1c2f1ef484975941394892dbebd`；包装器只观察 worker 请求或 X11 send 调用，调用原实现。这不是新版本 AppImage 验收。

测试使用真实 Session、自动路由、Hybrid 输入器和自建 GTK3 文本框，分别要求 GdkWaylandDisplay 或 X11Display，目标在发送前及后续采样均记录活动与输入焦点；录音、转写、润色使用本地固定公开文本夹具，非真实麦克风或云服务。

| 系统与控件 | 实际观察 |
| --- | --- |
| 24 原生 Wayland | worker connect 返回，authorize 报 `unsupported_compositor`；Session failed、统计 0，两次控件采样为空，未发送 worker key 请求。这是实际失败，不是原生输入或统计通过。 |
| 24 XWayland | 原生 authorize 返回 unsupported 后 Hybrid 使用 X11；一次按下与释放调用返回，首字同步取消后 Session cancelled、统计 1；finished 后约 1.38、2.68 秒两次采样均为“甲”。 |
| 26 原生 Wayland | 真实 worker 的 key 回复 count=1 返回后，首字回调同步取消，Session cancelled、统计 1；finished 后约 1.38、2.68 秒两次采样均为“甲”。worker 的 sent_at 早于其 key 回复返回，不能把回执等同于目标接收。 |
| 26 XWayland | Hybrid 使用 X11，一次按下与释放调用返回，首字同步取消后 Session cancelled、统计 1；finished 后约 1.38、2.68 秒两次采样均为“甲”。 |

所有字符统计均为已完成派发的下界，不确认目标接收或显示。两例 XWayland 的 finished 信号均先于释放调用返回；不能根据 finished 断言释放已结束。两次控件读取仅证明各采样时刻的值，不证明中间和更晚的全部时间。每次 Session 关闭后观察到 native.connected 和 x11.connected 均为 false；native close 请求有返回，但未单独核验进程退出状态。GTK 测试客户端由夹具 SIGTERM，退出码 -15。没有在真实桌面注入响应失效、未回复、迟到 ACK 或跨原生/XWayland 切换；这些仅有离线测试，finished 先发后的迟到 ACK 不能追补该事件。

24 首次夹具误将 `GdkWaylandDisplay` 视为非预期名称，在任何 key 发送前终止；修正后进行了正式样本。26 初始会话为 XFCE Xorg，首次 Wayland 控件无法初始化且未发送输入；卸载包后切换隔离客机至 GNOME Wayland 重试，结束后恢复 XFCE Xorg 活动会话。两系统 AppImage FUSE、覆盖目录及共享卸载，QEMU 和容器均退出 0、无 OOM，停止快照完整解压校验通过；SSH 原始记录、主机身份及客机快照仅留本地。本结果不证明真实云服务、实物麦克风、浏览器或其他应用，也不构成同版本双系统正式包验收。
