# Ubuntu 24 GNOME Wayland Unicode 输出路径复核

目标是用户当前光标、切窗后后续文字可进入新焦点、取消后不继续发送、未确认输入不重放；不使用剪贴板或更换用户输入法。以下是有界研究，不代表所有可能方案均不可行，也不是包验收。

| 路径 | 隔离证据 | 结论 |
| --- | --- | --- |
| RemoteDesktop EIS 键盘 | `../experiments/fcitx-handoff/wayland24/eis-r7/`：系统授权后设备键盘映射找不到测试中文和 emoji，ASCII 能到自有 GTK；未发送找不到映射的 Unicode。 | 当前键盘映射无法直接表达这些字符。 |
| Ctrl+Shift+U 组合输入 | `../experiments/fcitx-handoff/wayland24/compose-r14/`：切焦时 Chrome 测试将整字送往旧字段；VTE 测试把剩余十六进制字符及回车送往新终端。 | 破坏当前光标语义，终端可能执行意外文本，不可自动回退。 |
| GNOME Shell 私有 commit | `../experiments/ibus-gnome-shell/gnome46-native-commit-r16/`：受控同回调切窗时调用返回成功但目标均未收到；XWayland simple 无 currentFocus。 | 没有可靠送达确认，且无法通用覆盖目标；实验接口本身也不适合部署。 |
| AT-SPI EditableText | `../experiments/accessibility-probe/`：26 自有 GTK 选区插入未替换选区；项目先前受控 Chrome / VTE 的探针未见 EditableText，见 `direct-input-alternatives.md`。 | 不是模拟键盘等价物，且不能假设所有应用提供接口；上述选区样本不是 24 新实测。 |

较新 [libei 1.6 的文本能力](https://libinput.pages.freedesktop.org/libei/api/group__libei-sender.html) 值得未来按协商能力探索，但不应以客户端升级推断旧合成器支持。上游 [Mutter 46.0 的 EIS 实现](https://github.com/GNOME/mutter/blob/46.0/src/backends/meta-eis-client.c) 对外配置键盘与指针等能力，处理键码事件，源码没有文本能力或文本事件处理。这是上游 46.0 源码观察，不能替代对 Ubuntu 补丁版本以新版客户端实际协商的验证。若未来合成器提供文本能力，仍需实际测试当前焦点、取消与不确定结果，不能默认具备目标处理确认。

目前没有足够证据把以上途径实现为安全通用回退。应保留既有明确不支持和部分输出后的不重放保护；不能让失败路径自动发送组合键、改引擎或使用剪贴板。后续研究应优先验证新版本 compositor 对 UTF-8 能力的实际协商，并分别覆盖不支持 Fcitx 的浏览器、终端、选区、异步切窗和取消。
