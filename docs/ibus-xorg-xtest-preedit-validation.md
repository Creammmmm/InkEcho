# Ubuntu 24 Xorg：XTest 与活动 IBus 拼音单字实验

2026-10-31 在独立 Ubuntu 24.04 GNOME 客机，logind 报告 seat0 会话 active/x11、Xorg 进程存在。使用旧 0.15.0 AppImage（SHA-256 `94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a`），包内 `keyboard.py` SHA-256 `67000fe0de6592017796ebd07cb47dc0e187a1d24457ade68cfe4243cde5920e` 与当前源码相同；包的 `keyboard_for_desktop()` 在 X11 会话创建输入器，探针运行时确认驱动为 `_XTestDriver`。此处直接使用该工厂，不经自动路由或 Session。

自建 GTK3 X11 输入框使用 IBus libpinyin，在活动窗口及控件焦点均为 true 时用合成按键输入 ni，等待 0.8 秒后记录预编辑“你”、正文为空。调用该生产键盘输出器发送“测”，返回 1；0.8 秒后焦点仍在该控件，正文为“测”，预编辑仍为“你”。合成空格后正文为“测你”，预编辑为空。此受控单次单字样本未破坏观察到的活动预编辑；不能推断其他输入法、应用或字符、跨窗口焦点变化、取消、自动回退，亦非双系统发布验收。

执行前在隔离客机安装六个离线 IBus 拼音包并重启 IBus；`ibus engine libpinyin` 返回 1，但实时查询显示 libpinyin 已选中。探针恢复源和引擎后，清理时卸载六个临时软件包并重启 IBus，记录引擎 `xkb:us::eng` 和源 `[('xkb', 'us')]` 恢复，AppImage 和共享目录卸载。QEMU 与容器退出 0、未 OOM，停止快照完整解压校验通过。自建客户端的前置与后置状态、探针和日志仅保留本地。

此前相邻实验误以 `KeyboardInput()` 的默认 `_XDriver`/XSendEvent 作为生产 Xorg 驱动，报告已更正；该结果不是此 XTest 实验。没有使用宿主桌面或剪贴板。

测试结束时探针向自建 GTK 客户端发送 SIGTERM，客户端等待结果为 -15；这不是客户端自然退出 0。
