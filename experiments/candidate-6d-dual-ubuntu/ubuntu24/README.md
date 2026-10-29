# Ubuntu 24.04 隔离桌面输入验证

测试包 SHA-256 6d537689d5e30f4611f1e8376025705bf5fcc26c9198c9cda7c51717d434e34a，原包解压不覆盖源码。系统 Ubuntu 24.04.5、GNOME 46.0、Fcitx 5.1.7，实际 X11 会话 active、未锁定。QEMU 原盘只读、临时写层，测试配置与合成内容，不含真实凭据。脚本在 /tmp/inkecho-6d-payload/probes。

6d-x11.log 中自动及手动 Fcitx 正常各完整 200 字，取消分别留下 1、2 字；simple 控件 no_target 零前缀回退后 200 字，5 项均通过。6d-focus.log 切焦 1+199、gap 27+173 字均通过。初始强制运行 Wayland 脚本时客机实际为 X11，GTK 初始化失败，记录于 6d-wayland.log，这不是 Wayland 输入结果。随后仅在隔离快照切换实际会话，另行记录。

这些测试模拟音频与识别，未验证真实录音、物理快捷键、云服务、IBus、Chrome、真实终端或所有应用；不构成完整项目发布验收。

真实 Wayland 复测：重启后系统清理客机 /tmp，第一次运行因找不到脚本退出 127（6d-real-wayland.log），重新传入后由 session-after-reboot.log 与 6d-real-wayland-r2.log 确认 Type=wayland、active、未锁定。自动/手动 Fcitx 完整各 200 字，取消各 1 字，均通过。simple 输入控件 Fcitx no_target、0 字未发送后回退，Wayland 键盘返回 unsupported_compositor，0 字、failed；此路径未通过，不能视为已支持。

Wayland Fcitx 切焦样本 1+199 字、短暂无输入目标 27+173 字，均通过；保留日志 6d-real-wayland-focus.log。
