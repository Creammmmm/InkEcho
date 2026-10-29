# IBus 自动输出替代路径审查

2026-10-28，只读源码审查；不读取用户正文，不修改用户输入法或桌面设置。
本记录是技术候选与限制，不是支持声明。仓库既有隔离实验见
`automatic-framework-detection-research.md`。

## 现有门户

[IBus 与 Fcitx 的 portal 权限定义](https://github.com/canonical/snapd/blob/master/interfaces/builtin/desktop.go)
为受限应用创建其自身输入上下文并允许与该上下文通信。它没有提供一个
已证实可直接向另一应用的当前光标提交文字的方法；不能把 `CreateInputContext`
误认为跨应用提交。上述判断基于权限定义，不等于穷举所有未来接口。

[XDG RemoteDesktop portal](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html)
提供经用户授权的键盘按键或 EIS 事件，不是任意文本的 IME 提交接口；
这属于键盘输出路径。文档中没有将一次按键调用的返回描述为目标应用
接收或显示文字的确认。

## 输入法接口的占用与焦点

Wayland input-method-v2 协议规定每个 seat 最多有一个输入法对象；
自行成为另一个输入法并非透明共享现有输入法的方法。
IBus 的 [上游服务实现](https://github.com/ibus/ibus/blob/main/bus/ibusimpl.c)
在没有真实目标时可能使用虚拟上下文，其能力位也包含焦点与周边文本，
故不能靠上下文路径非空或这些能力位确认目标。
[引擎 focus-in-id](https://github.com/ibus/ibus/blob/main/src/ibusengine.c)
可包含客户端类型，但依赖活动引擎启用该可选事件；既有隔离测试的
xkb/us 引擎没有发出该事件。更换当前引擎来获得事件会干扰用户输入法。

GNOME Shell 46 的 [InputMethod 实现](https://github.com/GNOME/gnome-shell/blob/46.0/js/misc/inputMethod.js)
使用 `currentFocus` 并将 IBus 的 commit-text 转交给 Clutter 的 `commit`。
仓库先前的 Ubuntu 26 Wayland 隔离对照中，当前原生文本输入焦点存在时
直接调用 commit 可使自有 GTK 文本框收到合成字符，而按钮和 XWayland
simple 文本框的焦点检查失败；另一个实验显示提交后立即切焦点可丢字。
仅在检查未通过且确实尚未调用 commit 时，才可能安全地交回键盘后端；
提交调用后结果未知，不得重放。上述私有接口未验证 Ubuntu 24 Wayland、
真实浏览器和终端、非 XKB 输入法预编辑与最终 AppImage，也不能推广到
X11。更不能依据一次检查把以后任意焦点视为可用。

## 本轮验证

本轮执行 `.venv/bin/pytest -q tests/test_ibus.py tests/test_ibus_extension.py
tests/test_framework_detection.py tests/test_output_router.py`，结果 90 项通过；
`node experiments/ibus-gnome-shell/gate_v2.test.mjs` 通过。它们验证的是
路由与协议模型，不执行实际 GNOME 桌面投递。上述资料没有提供可同时
覆盖所有请求组合的已验证非侵入式自动 IBus 路径。

## 只读属性及静默丢字的源码审查

IBus 上游的 [InputContext 接口和实现](https://github.com/ibus/ibus/blob/main/bus/inputcontext.c)
中，客户端连接和 fake 标记是守护进程的内部字段；公开接口未提供对应只读
属性。接口中的 `PostProcessKeyEvent` 是不稳定的键事件后处理属性，事件
队列可含有文本，不适合作为不读取正文的目标探针。`FocusIn`、
`SetCapabilities` 等方法会改变上下文状态，也不是无副作用的查询。

同一实现中，输入上下文没有客户端连接时，发送信号的路径会直接返回成功；
因此服务层的成功返回不能证明目标收到文本。该结论来自上游源码，不是对
Ubuntu 两个发行版中所有具体 IBus 版本的运行时验证。前述 24.04 对照已
实际观察到非 IBus 控件未收到字符而面板仍返回 attempted。现阶段不以此
接口启用自动 IBus；已尝试提交的文字仍不得重复发送。
