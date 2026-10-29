# 自有窗口帧时钟与另一窗口暂停对照

2026-10-28，在隔离 Ubuntu 26.04 GNOME 原生 Wayland 会话中，两个独立 GTK3 进程各创建一个自有窗口并用 `add_tick_callback` 连续请求绘制；探针通过 `/proc` 确认 B 进程处于停止状态后等约 250 ms，再恢复 B。A 的计数从 3 到 22，B 保持 3；进程退出 0。结果表明一个窗口的 GTK 帧时钟回调仍能推进，即使另一窗口进程完全没有处理事件。它不能用来确认那个窗口收到或呈现输入。

该样本未发送 Fcitx 输入，也未观测实际呈现像素；GTK 帧时钟回调不应直接等同 `wl_surface.frame` 协议回调。它只验证窗口间信号不能互相代替，不能作为 40 ms 输出质量评估或跨应用支持验收。目标暂停、恢复均仅作用于测试自建进程，不读取文本或使用剪贴板。`probe.log` 是执行工具返回的 stdout 原文转存，非额外运行的原始终端录屏。

复现仅限隔离虚拟机：将 `actor.py.txt` 与 `probe.py.txt` 去掉 `.txt` 后复制至新建的 `/tmp/inkecho-own-frame-r1`，在用户 Wayland 会话设置 `XDG_RUNTIME_DIR=/run/user/1000`、`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`、`WAYLAND_DISPLAY=wayland-0`、`XDG_SESSION_TYPE=wayland`、`GDK_BACKEND=wayland` 后运行 `/usr/bin/python3 /tmp/inkecho-own-frame-r1/probe.py`。脚本 finally 恢复并终止自有进程。实验后临时目录已删除，虚拟机 ACPI 正常关机，容器退出码 0；没有改会话配置。

```text
7c2c7ba39d2966060b35be8d7be13baaf2df73361d253594b5ddd93d1dbe3a95  actor.py.txt
6a753882b064778aed9df662ac49af56cadee132bef37db6a94beb31901b4a34  probe.py.txt
f0f104f223660d21b0537887e4ec4d273c735d6bcf91c8e853d0297b120d1a2f  probe.log
```
