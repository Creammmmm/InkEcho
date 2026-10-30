# Ubuntu 26 GNOME Wayland 中 XWayland Fcitx 客户端实测

2026-10-30 在隔离 Ubuntu 26.04.1 / GNOME 50.1 Wayland 客机，Fcitx 5.1.19，使用 FUSE 挂载的 0.15.0 AppImage（SHA-256 `94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a`，提交 `76aeb33`）和包内插件（SHA-256 `f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44`）；通过安装器安装插件，未修改产品代码。Fcitx 测试期间临时设定系统会话提示，并在隔离客机安装真实拼音组件；测试后恢复提示。目标为自有 GTK3 XWayland 窗口，确认 GdkX11Display、焦点、活动窗口、Fcitx GTK 前端已加载；通过自有窗口激活和 QMP 虚拟键盘形成真实拼音，不使用剪贴板。

独立 router 样本 auto 实际选择 fcitx，焦点控件接收“甲乙”。真实 Fcitx 拼音 `ni` 形成长度 2 的预编辑时尝试输出，返回 `fcitx_composition_active`、尝试数 0，内容与预编辑保持不变，按空格后上屏“你”。随后一个字符发送后取消，报告 `fcitx_cancelled`、已确认尝试数 1，实际只收到前缀“己”；等待 1.2 秒时未发现额外字符。这是单个受控样本，不保证任意取消竞态。此项是 router 而非完整 Session。

完整 Session 使用虚拟音频及本地模拟识别、润色服务，auto 选择 fcitx。录音期间切换至自有第二 GTK3 XWayland 文本控件，正常样本 22 码点完整一致；以首字符接收作为取消触发，触发时接收端有 1 字，最终接收 2 字“你好”，晚到字可能已经在途。进程退出后 1.3 秒无追加。两者均正常结束、旧控件保持空白。没有在完整 Session 中验证活动拼音预编辑。

首轮夹具焦点校验路径错误导致按键未发送并超时，已保留；第二轮真实 router 样本通过，但完整 Session 夹具读取 9p 目标状态时出现 `OSError: No data available`，未完成该流程。第三轮修正焦点路径和短暂读取错误重试、明确验证 X11Display 后通过；只修改测试夹具。测试后 Fcitx 退出、提示恢复、FUSE 挂载移除；客机 QEMU 和容器退出 0，无 OOM。隔离停止快照完整解码核验后保留在 `dist/fcitx-xwayland-26-audit-20261030/vm26/output/stopped-followup-child.qcow2.gz`，SHA-256 `edb2bea3d0f4cb114153c505ea1f60aa094c089def68ac1c3b93eaa63ca48f0b`，未包含在提交。

原始脚本、命令、日志、包审计、接收数据和失败情况按字节存于 `raw-byte-archive.json`，每项有 SHA-256 和大小；私有 PulseAudio 认证 cookie 已从归档中省略。此结果不验证真实麦克风、云服务、其他客户端、活动拼音时完整 Session、跨输入后端切换、Ubuntu 24 或任意取消竞态；不能据此宣称所有组合受支持或关闭已有 IBus 到 XWayland 问题。

本次输入模块验收汇总：同批次的 [Wayland 双事件队列实验](../wayland-ping-queues-20261030/README.md) 从全新目录下载并校验官方依赖，私有双端复现 pong 先于文字回调的反例；这是未完整建模输入法状态的阶段 0 协议实验。本报告的客机实测单独验证了上述 Fcitx XWayland 场景。两者均不证明 owned IBus 已尝试文字与后续 Fcitx 输出之间的安全交接，不改变自动路由限制。
