# Ubuntu 24.04 GNOME 46 原生 Wayland：不改全局映射的键盘路线核查

本次只做官方上游 46.0 源码阅读与隔离离线模型，未在用户桌面操作，未读取输入正文，未修改配置或剪贴板，也未安装输入法。结果不是 Ubuntu 包的源码一致性证明，不是目标程序实际输入测试。

* Shell `Clutter.VirtualInputDevice.notify_keyval` 并不是任意 Unicode 直达接口：上游在独立输入线程中通过 seat 当前 XKB 映射、当前组查询 keysym；查不到则忽略。之前 Ubuntu 24 的 EIS 实测已表明常见 US 映射中不存在中、😀。见 [上游 46.0 实现](https://raw.githubusercontent.com/GNOME/mutter/46.0/src/backends/native/meta-virtual-input-device-native.c) 第 416–460、503–523、569–588 行及项目 `experiments/fcitx-handoff/wayland24/eis-r7/README.md`。单独开一个虚拟设备或用 keysym API 不解决通用汉字。
* `notify_key` 也把任务排入输入线程，第 393–413 行；即使 Shell JS 回调内连续检查映射并发送，检查也不与输入线程解释按键构成同一事务。释放与客户应用处理同样没有得到确认。
* [上游 seat 实现](https://raw.githubusercontent.com/GNOME/mutter/46.0/src/backends/native/meta-seat-impl.c) 第 277–295、364–407 行以 seat 共享按键计数与 XKB 状态处理虚拟和物理键。因此只新建虚拟设备不能使同键物理按键完全隔离。`count_model.py` 是按该条件进行的离线模型：纯虚拟按下释放可见，物理键持有期间虚拟同键按下释放均被共享计数过滤。模型未运行 Mutter，不应视为物理设备实测。
* AT-SPI 编辑接口不需要改键盘映射，但已有的 `experiments/accessibility-probe/README.md` 实测表明它不替换选区，且客户端覆盖/焦点切换不充分，不符合现有键盘语义，不能作为通用自动回退。
* 现有 `experiments/ibus-gnome-shell/gnome46-native-commit-r16/README.md` 实测 Shell 直接文本提交在切焦和 XWayland 有缺陷，不能替代键盘语义。合成 Unicode 组合键在 VTE 切焦时还可能落下字面数据，见 `experiments/fcitx-handoff/wayland24/compose-r14/README.md`。

没有发现既能对任意当前焦点发送中文、又不使用共享映射/组合键并兼顾物理键和焦点切换的已验证通用键盘方案。此结论只覆盖核查过的路线，不是证明任何可行机制都不存在；不可声称 24.04 Wayland 回退已修复。建议继续研究支持真实目标与结果不确定性的输入法通道，或从上游输入协议的 per-device keymap 与目标提交确认能力入手；都需要隔离桌面实测后才能进入产品。
