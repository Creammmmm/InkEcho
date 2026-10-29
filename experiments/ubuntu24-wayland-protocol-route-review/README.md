# Ubuntu 24 原生 Wayland 可选输入协议复核

2026-10-29 核对已有客机证据和协议文档；没有运行新实验、访问用户正文、剪贴板或更改系统输入法。目标约束是保留现有输入法、按输出当时焦点、无剪贴板地发送 Unicode。以下不是证明不存在任何可行方案。

* [libei 官方 ei_keyboard 规范](https://libinput.pages.freedesktop.org/libei/interfaces/ei_keyboard/index.html) 中 sender 的 key 请求发送 Linux 键码；服务端可提供 XKB keymap，发送方按该映射选键码，映射对设备生命周期恒定。规范没有在此键盘接口中提供任意文本提交请求。已存 `experiments/fcitx-handoff/wayland24/eis-r7/README.md` 测过 Ubuntu24 EIS 当前布局，中文不在键映射中；不能从新建设备直接推断得到自定义映射。
* input-method-v2 的协议定义有 `commit_string`，但明确一个 seat 最多一个输入法对象；另一个对象不会自然成为与现有输入法并存的通用注入器。[协议 XML](https://github.com/Smithay/wayland-rs/blob/master/wayland-protocols-misc/protocols/input-method-unstable-v2.xml) 是公开协议文件副本。旧客机普通 Wayland 客户端 registry 日志 `build/handoff-review/wayland24-r3-registry.log` SHA-256 `77f306abad35482d7219475429a1026771a3c1528558c85bd7fe9bdb089f0951`，列出 `zwp_text_input_manager_v3`，没有 `zwp_input_method_manager_v2` 或 `zwp_virtual_keyboard_manager_v1`；该观察只针对普通客户端和当时会话，不能排除特权客户端或其它版本。不能将 text-input 客户端接口误认为可向其他客户端发送文本的输入法接口。
* 已有 `experiments/ubuntu24-portal-keysym-audit/README.md` 保留标准 portal keysym 实测：普通布局下未收到中文等字符，虽然调用返回；`experiments/ubuntu24-remote-input-capabilities/README.md` 保存当前 Ubuntu 包的远程桌面接口清单，未见公开文本提交或 SetKeymap。`experiments/atspi-keystring-wayland24/README.md` 的 AT-SPI 字符串探针也只得到调用 true 而两个自建控件无输入。`experiments/ibus-gnome-shell/gnome46-native-commit-r16/README.md` 则记录 Shell 直接提交切焦时丢字和 XWayland 不匹配。

本轮未识别出在现有 IBus 不变、无剪贴板、通用当前焦点和任意 Unicode 四个条件同时满足且可安全隔离测试的新协议路径。以上只覆盖检查过的接口及实际客机会话；如未来发现受信任的多输入法合成器接口、每设备独立映射或目标消费回执，仍需另行隔离验证。此只读复核不构成 24 Wayland 回退修复或包验收。
