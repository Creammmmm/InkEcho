# OpenLESS Linux 输出与 Ubuntu 24 Wayland 回退对照

2026-10-29 只读检查本机 `/home/lth/github/openless`，Git HEAD `63be178b43e3e8084d09ff082a42dbdcbaf74d2b`，当时工作树状态输出为空。没有运行 OpenLESS、读取用户正文、修改桌面或进行新方案的运行测试。以下是源码结论，不是运行兼容性证明。

* `openless-all/app/linux-egui/src/fcitx5.rs` 的 `Fcitx5TextInserter.begin` 以任务 ID 调 `CaptureDictationTarget`；`scripts/linux-fcitx5-plugin/openless.cpp` 将此前保存的 `savedIc_` 存入任务，`commitDictationTarget` 调目标 `commitString`。此路径依赖 Fcitx 输入上下文，且固定录音开始时的目标，不符合 InkEcho 当前输出时焦点语义。另有 `commitText` 在没有 savedIc_ 时遍历当前焦点，但也只作用于 Fcitx 输入上下文，不能直接作为保持 IBus 的通用回退。
* `openless-all/app/linux-egui/src/portal/mod.rs` 中 `PortalTextInserter` 的 `supports_streaming` 为 false；`portal/bridge.py` 的插入路径先 `Clipboard.SetSelection`，再调用 RemoteDesktop `NotifyKeyboardKeysym` 发送粘贴快捷键。不符合 InkEcho 不使用剪贴板的约束；不能把它称为无剪贴板键盘 Unicode 方案。`backend.rs` 分别接入 PortalTextInserter 和 Fcitx5TextInserter，源码本身不证明所有桌面实际可用。
* InkEcho 现有 `experiments/fcitx-handoff/wayland24/eis-r7/README.md` 记录 EIS 当前 keymap 没有常见中文直映射；`compose-r14/README.md` 记录 Ctrl+Shift+U 中途切焦时 VTE 可能收到字面剩余字节；`xkb-owner-lifecycle/README.md` 与 `native-seat-source-review/README.md` 记录全局临时映射与物理键风险；`experiments/ibus-gnome-shell/gnome46-native-commit-r16/README.md` 记录 Shell 提交的切焦丢字与 XWayland 边界。这些既有实验都不应通过重新包装而称为解决方案。

额外发现 AT-SPI `generate_keyboard_event` 的 [API 文档](https://gnome.pages.gitlab.gnome.org/at-spi2-core/libatspi/func.generate_keyboard_event.html) 描述 KEY_STRING 可接受 UTF-8 字符串；但 [上游 2.52 X11 源码](https://raw.githubusercontent.com/GNOME/at-spi2-core/AT_SPI2_CORE_2_52_0/registryd/deviceeventcontroller-x11.c) 的 `spi_dec_x11_synth_keystring` 将字符串转 keysym 并按 X 键映射合成，[控制器方法](https://raw.githubusercontent.com/GNOME/at-spi2-core/AT_SPI2_CORE_2_52_0/registryd/deviceeventcontroller.c) 即使底层合成失败仍创建正常 D-Bus 返回。此接口与此前 `EditableText.insert_text` 实验不同，但未在 Ubuntu 24 原生 Wayland 运行验证，无法证明支持、焦点、是否触及键盘映射或不影响物理键；不能把 API 成功返回当作目标收到了文字。若后续研究，必须只在无个人数据的隔离客机中分别验证自有原生 Wayland 与 XWayland 控件、未映射中文、选区、实时切焦、取消及失败回执，同时确认实际安装版本和副作用。

本次没有发现可直接移植且已经满足现有 IBus、输出时焦点和无剪贴板约束的通用 Unicode 方案；这只是对列出代码及已有证据的范围结论，并非证明不存在任何方案。未执行新隔离实验，不改变产品或包发布状态。

所读本地 OpenLESS 文件 SHA-256：`fcitx5.rs` `29c2d0c0ebd3e8c2b239b7fc1e036ba6742ba8e80b6e600552a9e47e52b43efd`；`portal/mod.rs` `09616119337017cff8c953344b19f59b1387870d3658837b491168cea458c2cb`；`portal/bridge.py` `9c17c0bad9e311461fc037130b21ea4b6f3d2e76495ca3f708cf94f6bd70619e`；`backend.rs` `d3219f7b36358129d8f5418b7b0c22ac101ab1bcf87f3ab05c295eed855adc1f`；`linux-fcitx5-plugin/openless.cpp` `8d254c7097621e58e680163e8bf9c5ffb4c931b2a7a5a294dbd9e9814320b1a3`。
