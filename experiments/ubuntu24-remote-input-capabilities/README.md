# Ubuntu 24 GNOME 远程输入接口能力核对

2026-10-29 在 Ubuntu 24.04.5 / GNOME Shell 46 active Wayland 独立 QEMU 快照查询 D-Bus 接口；原系统盘、基础盘与 seed 只读，容器无外网且不挂载密钥，宿主仅使用客机专用 SSH 测试密钥。测试只读取接口、属性和软件包版本，并创建一个未启动的空 Mutter RemoteDesktop 会话用于 introspection；没有请求桌面授权、发送任何按键或文本、使用剪贴板、读取个人数据或更换输入法。客机当前 IBus 引擎 `xkb:us::eng`。

`versions.log` 是实际包版本：`libmutter-14-0` / `mutter-common` `46.2-1ubuntu0.24.04.18`、GNOME Shell `46.0-0ubuntu6~24.04.16`、libei `1.2.1-1`、xdg-desktop-portal `1.18.4-1ubuntu2.24.04.3`、xdg-desktop-portal-gnome `46.2-0ubuntu1`。`probe.log` 的首次 dpkg 格式命令误被 shell 展开而输出空行，版本以修正后的 `versions.log` 为准。宿主只读包查询见 `host-packages.log`（GNOME 50.1、libei 1.5.0 等）；未在宿主运行 D-Bus 交互或测试输入。

客机实际 introspection 显示 portal `org.freedesktop.portal.RemoteDesktop` version 2、可用设备标志 7；方法包括 `NotifyKeyboardKeycode`、`NotifyKeyboardKeysym`、`ConnectToEIS`，没有独立文本提交或 `SetKeymap` 方法。Mutter 根接口 `Version` 为 1；新建空 session 的可见方法同样包含 keycode/keysym 和 ConnectToEIS，属性中没有 `KeymapCapabilities`，方法中没有 `SetKeymap`。session 还列出剪贴板相关方法，但本探针没有调用它们。原始完整相关接口列表见 `probe.log`。这是当前 Ubuntu 包实际暴露的 D-Bus 接口，而不是对 Ubuntu 全部补丁源码的逐项审计，不排除未公开的其他机制，也不能从方法存在推断调用可用。

因为 session 未 Start，`Stop` 返回 `Session not started`，不是成功停止；探针进程退出后另一个连接查询旧对象得到 `UnknownMethod: Object does not exist`（`session-after.log`），证明当时旧对象已消失。客机 poweroff 后 docker wait=0、ExitCode=0、OOMKilled=false，容器已删除；快照内 GDM 设置未逐项恢复，原盘只读。没有截图。

这组只读能力查询没有发现可用来绕开已有 GNOME 46 XKB 限制的公开文本输入方法；并未重新运行 EIS 键入或测试其它协议。此前实际 EIS 限制与 XWayland keymap 实验分别见 `experiments/fcitx-handoff/wayland24/eis-r7/README.md` 与 `xkb-owner-lifecycle/README.md`。不得把这次查询当作 Ubuntu 24 通用回退已解决或完整包验收。

隔离复现：将 `probe.py.txt` 去后缀，设置隔离图形会话的 `XDG_RUNTIME_DIR` 和 session D-Bus 地址，用系统 Python 运行；脚本创建空 session、尝试停止并退出，需随后由独立连接检查对象是否消失。不能在真实用户桌面运行该探针。SHA-256：`probe.py.txt` `decea60a3802e9beb16b961a184e32b0a74cfdff0f2b1324a9ae76939a3e90ba`；`probe.log` `fff0f67b9768f62e8ae1f3a619f4cc2f1847d5acd27c25f2c02b1ee2aa0f530d`；`versions.log` `355959dd5c4cd0b40d842e8e4b905bbc069dde137c9a84b386056ce73939e03c`；`session-after.log` `e87c43ee7476f1912fe686d59a509a5a20840c8bcf2548d69e7b30ea1b60a1f8`。
