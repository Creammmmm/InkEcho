# GNOME Wayland 直接调用输入焦点虚函数探针

2026-10-29：为既有 Ubuntu 26.04 GNOME 测试客机创建写时复制快照，原客机镜像及其基础镜像以只读方式挂载；实验容器无外部网络。只在快照中将输入源设置为 libpinyin、安装未认证的临时 GNOME 扩展，并创建两个自有 GTK3 文本框。只生成固定合成按键和文字，不读取其他应用正文、不访问宿主会话、剪贴板或用户输入法。**扩展无认证、调用私有 API，不能用于真实桌面。**

动机：Mutter 46 源码中 `MetaWaylandTextInputFocus` 的 commit-text 虚函数向聚焦的 Wayland text-input 资源发送 commit-string，并延迟 done；切换焦点路径会 flush done。它看起来与 `ClutterInputMethod.commit()` 把事件排入 Clutter 队列不同，可能值得隔离验证，但源码不能证明应用最终接收：[Mutter 46 text input](https://raw.githubusercontent.com/GNOME/mutter/46.0/src/wayland/meta-wayland-text-input.c)。该虚函数也会发送清除 preedit，能否保留用户正在组合的文字必须单独验证。

本机 GJS 在人工创建的 JavaScript `Clutter.InputFocus` 子类中可以调用 `vfunc_commit_text`（`mock.js.txt`）；不能据此推断实际 Mutter C 子类可用。快照中 GNOME Shell 的真实 `Main.inputMethod.currentFocus` 已指向 native Wayland 自有 GTK 输入框。扩展读取 `focus.vfunc_commit_text` 时两次抛出 `Virtual function not implemented: Class ClutterInputFocus doesn't implement commit_text`，因此没有发送实验文字，程序中计划的同一回调切窗口也**没有执行**。两次失败分别发生在 libpinyin 自造 `ni` 预编辑期间及另一自有窗口活动时；`result.log` 为第二轮保存的输出，进程退出码 0。预编辑前正文为空、布局是“你”，失败调用后正文仍空、布局仍为“你”，空格后正文为“你”；引擎前后均为 libpinyin。这证明在该次失败调用下合成预编辑未被改变，并不证明可成功调用时预编辑会保留、切焦不丢字，或 Ubuntu 24.04、其他控件可用。

复现仅限一次性 Ubuntu 26 GNOME Wayland 客机：在隔离图形会话将输入源设置为 `ibus/libpinyin`，将 `metadata.json` 和 `extension.js` 放入 UUID `inkecho-vfunc@local.invalid` 的临时用户扩展目录并启用，重启后检查扩展 ACTIVE。复制 `actor.py.txt` 到客机 `/tmp/vfunc-lab/actor.py`，设置图形会话的 `XDG_RUNTIME_DIR`、`DBUS_SESSION_BUS_ADDRESS`、`WAYLAND_DISPLAY`、`XDG_SESSION_TYPE=wayland`、`GDK_BACKEND=wayland`，清除 `GTK_IM_MODULE`，确认 `ibus engine` 为 libpinyin，然后运行 `/usr/bin/python3 /tmp/vfunc-lab/actor.py`。这些操作会切换隔离客机输入源，绝不可在用户真实会话中复现。

初次启动阶段尝试额外启动 IBus daemon 导致暂时存在第二个测试 daemon；后续结束了所启动的 daemon 主进程，实际两轮实验查询引擎均为 libpinyin，不能据此排除其残留子进程对结果的影响。首轮输出见代理执行结果，未另存；第二轮原始结果保存为 `result.log`。测试后 QMP 正常关机，`docker wait` 返回 0；未在快照内逐项恢复设置，但快照与原镜像隔离，不声称对快照内账户做过完整恢复。无产品代码更改。

SHA-256：`actor.py.txt` `5da56060bb85fffb2bb027db7f9898dcc9204d79f9c6b0338f5b4c249428ab1e`；`extension.js` `7c43e05db02cc87cda20ec5ffd6fb71524320043052b548d736d3fa7be4d54d6`；`metadata.json` `5d9d985958b48fc0e0940c584b7a51476a4ebfa20e3ca1b074f95c8583002261`；`result.log` `678d57fb136294769b35bc4c533c3238fb82eb2f2a6af79a96004057bf7cf8f4`；`mock.js.txt` `0b7c348e3bd87e2f38285a76f2d51044a7356c4717e1b24563463487b560b1ad`。
