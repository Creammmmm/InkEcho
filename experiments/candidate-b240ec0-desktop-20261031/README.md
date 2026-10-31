# InkEcho 0.15.56 候选包有限验收（未发布）

冻结源码 b240ec0d23530bb024f4895830b8f2346058921f，候选 AppImage 104430072 字节，SHA-256 a3817a8fcb9ef15c8b93db9f5358d818e676b6dee94ffb1c1b5f46d6398760b8。两套客机对各自副本核验该哈希、包内版本、3707 文件、1048 链接、94 项应用文件与冻结源码一致。未更新稳定入口、真实用户配置或宿主输入法。

Ubuntu 24.04.5 GNOME 46 Wayland：包内五页和生命周期、合成本地 HTTP 和 Qwen VAD WebSocket、受控 XWayland 键盘混合 Unicode 22 字和首字取消通过；独立第二次快照中 Chrome 原生 Wayland 的 IBus 手动模式 22 字、首字取消、发送前取消和发送前切换输入框通过。

Ubuntu 26.04.1 GNOME 50.1 Wayland：同包五页和生命周期、本地协议；原生 Wayland 和 XWayland 键盘各 22 字和首字取消；Chrome 原生 Wayland IBus 手动模式的上述四项均通过。目标控件进程在测试清理时由夹具 SIGTERM，不能称为自然退出。测试服务、录音及文本均为合成，没有真实云端和麦克风。

两次首次客机均完成 FUSE 包卸载、资源检查、正常退出 0、无 OOM、快照完整性校验并移除测试容器；Ubuntu 24 的补充 IBus 客机也已恢复扩展及设置，包卸载和资源检查成功，退出状态见同目录最终结果。准备夹具时 /tmp 用户配额导致首次脚本写入失败（零字节）；脚本改在 /var/tmp 创建后成功，候选构建未受影响。Ubuntu 24 反复发生 SSH banner 超时，等待原快照的网络等待结束后继续；26 首次连接重置，随后同一实例连接成功，失败日志均保留。

未覆盖本版 Xorg、Fcitx、24 原生 Wayland 键盘、真实麦克风/物理快捷键、实际云端、输出中跨真实窗口切换、IBus Xorg 活动组词。受控样本不能代表所有应用或完整产品闭环，也不等于最终发布验收。原始日志和快照仅留此临时目录，可能含客机系统配置，勿原样提交；稳定入口未改变。

[脱敏回执与原始文件散列](receipts.json) 只摘录退出状态及合成协议结果。第一次 Ubuntu 24 容器状态文件被补测覆盖，第一次干净退出仅由当时控制器输出记录，未保留独立状态文件。

夹具中继承的 `input/new-artifact-identity.json` 是历史 0.15.0 包身份资料，未作为本候选包的身份或验收证明。本次包身份与 94 项源码匹配以两台客机实际执行的 `output/wayland/package-audit.json` 为准（24 首轮结果保存在 `output-first/wayland/package-audit.json`），其 SHA-256 见回执。

回执中的 `*-archive` 项 `sha256` 是客机归档校验结果 JSON 文件的散列，**不是**快照压缩文件的散列；`full_stream_verified` 和 `qemu_exit` 摘自该结果。原始快照及其内容不纳入仓库。
