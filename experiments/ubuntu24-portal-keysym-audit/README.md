# Ubuntu 24 Portal Unicode keysym：现有实测核对

2026-10-29 核对既有证据，没有重新执行输入或访问真实桌面。`experiments/fcitx-handoff/wayland24/KEYBOARD_PATHS.md` 的 “Completed standard authorization and keysym control” 记录了 Ubuntu 24.04.5 GNOME 46 隔离 Wayland 客机使用标准 RemoteDesktop 键盘授权后，向自有 GTK 控件直接调用 portal `NotifyKeyboardKeysym`；不是 EIS keycode 测试。授权只选键盘，未使用剪贴板或注册系统输入法。

原测试脚本 `portal_unicode_probe.py.txt` 第 88–95 行调用 `NotifyKeyboardKeysym`，第 164–175 行将 U+00FF 以上字符编码为 Unicode keysym（按位或 `0x01000000`），逐个发送按下/释放并等待；测试固定字符串 28 码点。`portal-r5.log` 显示 `keyboard_only_granted: true`、`exact_unicode: false`；自建原生 Wayland 控件只收到 15 个 ASCII/空格/换行码点 ` InkEcho caf  \n`，中文、é、Ω、emoji 未到达。日志保留测试期望失败后的异常和外层失败退出，不得把其写成通过；成功的方法调用不能作为接收确认。说明仅针对该会话、现有布局与自有控件，不能外推所有布局、不同合成器或应用。

该结果与 [Mutter 46 上游实现](https://raw.githubusercontent.com/GNOME/mutter/46.0/src/backends/native/meta-virtual-input-device-native.c) 查找当前键映射而没有键位时丢弃的代码一致，但上游代码与受测 Ubuntu 二进制并非逐字源码对照；接口列表和该客机 Ubuntu 软件包实际版本见 `experiments/ubuntu24-remote-input-capabilities/README.md`。此处不能得出任何未公开机制均不可用的结论。

经本次校验并保留的原始日志 SHA-256 `8e8b448dcb8d5451178d4d633e5ddd4f3c60aa187fd20f6a61a34be06d3e68e8`，脚本 SHA-256 `f61db5143fc17cd7b2429b5d485538314c1fb81c5d0daff47eb8fcc8abec7580`，与原记录一致。复现需一次性隔离 GNOME Wayland 客机、自建目标及标准键盘授权；步骤、授权记录、环境与清理见 `experiments/fcitx-handoff/wayland24/KEYBOARD_PATHS.md`，禁止在真实用户桌面执行。
