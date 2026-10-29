# GNOME 46 临时键盘映射恢复探针

仅用于阶段 0 实验，非产品补丁或 AppImage 验收。使用独立 QEMU 容器、Ubuntu 24.04.5 基础镜像只读挂载、`-snapshot` 临时写层、无外网（容器 `--network none`）、只读测试输入；未挂载宿主用户桌面或配置。快照中设置 GNOME Wayland，`loginctl` 返回 `Type=wayland`。与上次实验一样运行 GTK3 原生 Wayland 输入框及临时 GNOME Shell 扩展，扩展使用 Shell 虚拟键盘，无剪贴板；其 D-Bus 接口不具备安全授权，仅限隔离实验。

唯一改变：`Restore` 不再写回应用开始时快照，而是读取 `getKeyboardManager()._currentKeymap` 并以其当前的 layouts、variants、options、model 调用 `global.backend.set_keymap`。这是 Shell 私有属性，不承诺稳定，且不能发现绕过该管理器对后端进行的更改。扩展 SHA-256 `987ccf1c11034f8b43cc12630837fbe4f42cf6de3ebefddb5869f62e3b121860`。

## 实测

- `conflict.log`（`conflict.py.txt`）中输入框活跃且聚焦，应用后 `a甲`；用户设置变为 `caps:escape` 后，Caps 键产生 Escape，再次发送测试键没有额外字符；恢复报告当前 options 为 `caps:escape`，恢复后 Caps 再次产生 Escape，设置仍为 `['caps:escape']`。这证明此受控配置更新没有被旧快照覆盖，同时说明变更会替换临时映射，继续发送会静默漏字。
- `disable.log` 首次失败，原因是实验脚本没有给 XWayland 设置 DISPLAY；`disable-r2.log` 修正连接后，应用、用户配置变更、停用扩展前后 XWayland keycode 66 均显示 Escape，设置仍为 `['caps:escape']`，服务名已无 owner。此项只通过 XWayland 映射观测，非原生客户端按键复验。
- `concurrent.log`（`concurrent.py.txt`）连续执行两次 Apply 再执行一次 Restore；之后测试键没有在有焦点 GTK 输入框产生字符，第二次 Restore 为 `not-applied`。此探针使用顺序调用模拟两个重叠请求，没有保证不同 D-Bus 进程或请求真正并发；但已证明当前接口没有会话所有权，单个客户端恢复会撤销另一个活动任务的映射。
- 调用 Apply 的 `gdbus` 客户端每次调用后退出，但临时映射仍然生效，说明客户端离开本身不会自动恢复。未模拟 Shell 崩溃、进程强杀、断电及键按下未释放等异常。

测试结束在快照内禁用扩展、清空测试选项，`cleanup.log` 显示设置为空且总线名无 owner；客机关闭，容器退出码 0，临时快照丢弃。没有声称恢复了所有客机设置。

## 结论与未覆盖风险

读取当前管理器配置可以修复本实验重现的特定覆盖问题，但不能构成产品方案。GNOME 私有接口未提供对外原子比较与恢复保障；配置更新会撤掉测试映射，需在发送前后及时检测并终止且不得重放状态不明字符；并发任务需要串行所有权、生命周期绑定和客户端失联清理；若键盘配置发生在检测与按键之间，映射仍可能改变。尚未验证其他布局、输入源、扩展竞争、原生协议完整映射、真实物理按键、焦点切换、不同应用、24/26 其他桌面及异常恢复。全局 seat 映射也可能影响用户输入。现阶段不应在产品中启用。
