# Fcitx5 输入桥单次配置验证

2026-11-09。该改动合并应用内的安装、刷新操作，不解决尚未交付的免扩展
stock Xorg IBus 路径，也不改变自动输出路由。此记录区分机制验证、源码候选
和最终包验收，不能据此宣布新 AppImage 已通过双系统验收。

## 阶段 0 机制

上游 5.1.7 和 5.1.19 的 Refresh 会异步重新扫描插件描述，加载此前未知、
已启用且 `OnDemand=False` 的插件。调用返回不等于加载完成。已经缓存的
失败、停用或旧版同名插件不会因此重新加载。因此不自动重启服务，也不把
Refresh 成功当作运行成功。

Ubuntu 24.04 隔离 Xorg 客机使用真实系统 Fcitx5 5.1.7、私有 D-Bus、独立配置
和两个阶段的磁盘发布与刷新。使用官方 0.16.0 旧包运行时中的安装器，来源
提交 `eb5536b7e374debf1b799ce8fd2e3be96d43a368`，不是新按钮源码验证。
原始证据位于 `/tmp/inkecho-fcitx-refresh24.HEYUkf/output/mechanism.json`。

| 观察 | 实际结果 |
| --- | --- |
| 安装前与仅发布后 | `/inkecho` 均为 UnknownObject |
| 请求 Refresh 后 | 接口可用，RuntimeVersion 为 `5.1.7` |
| 服务身份 | 前后 owner、PID、进程启动时间相同，没有重启 |
| 重复安装与刷新 | 配置和库的 inode、mtime、哈希不变，接口仍可用 |
| 实际 GTK 目标 | 加载系统 im-fcitx5，真实聚焦，protocol 4 输出 `甲A🙂乙Ω`，收到五个码点 |

该样本的 GTK changed 分两次出现，不证明每字符独立显示。私有服务禁用
clipboard、ibusfrontend、xim，不接管宿主输入法。证据记录实验进程已停止。

机制实验安装器 SHA-256 为
`407cd00c47fcf277f247827cc86c5a04b75fd7d1074abbdf3d721552de7ddae9`。
随包插件 SHA-256 为
`f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44`。
复现需要上述目录的私有客机夹具和冻结旧运行时。先核对发行版及模块版本，
在启动的私有 Fcitx 中验证接口不存在，发布插件后再次验证，再 Refresh 并观察
同一服务实例的接口。最后在自有 GTK 输入框发送合成文本并清理私有进程。
临时目录不是长期下载地址。

## 冻结候选及生命周期

按钮改为“配置 Fcitx5 输入桥”，明确发布当前用户配置并请求正在运行的服务
刷新。保留停用和检查。系统输入法选择及重新登录仅在尚未选用并运行 Fcitx5
时由用户完成。启动、选项切换和自动模式不安装插件、不改系统输入法。

单个 maintenance 操作依次执行 install、enable，再最多等待 3 秒检测已校验
磁盘描述、运行服务 owner 和 RuntimeVersion。维护期间不启动录音，调用方
取消后，已经启动的维护仍继续完成，并由 Session 跟踪。退出等待维护结束。
这里不发送文字，不创建输出任务，不声称具体目标可用。明确检查按钮只执行一次只读运行检测。

发布失败、刷新未确认、已发布但运行未确认分别保留真实状态，不自动删除
可能已发布的文件，也不重启。停用仅移除加载描述，已映射插件仍保留到服务
退出。运行检测成功也不代替实际输出时的协议和目标检查。

| 冻结文件 | SHA-256 |
| --- | --- |
| app.py | `7a49939f57d537a6792fc20688b5aeb1f071ad17de87a565a99107a3dfaab77a` |
| information.py | `b540a96a3ee2451b3f55aba045aaf2b05ea6a9a2f1a162b3738458eb7873c7b6` |
| fcitx5_install.py | `598c86da1fc43925a36b1627bef8efe19f7b560ce6ea2f49c7a2fddf233cdddf` |
| 审查补丁 | `6d96fb11e47e123364488cb71c567ba67cfc1e693da4c76b7c3ed6bbb0bc23e9` |

候选位于 `/tmp/inkecho-fcitx-one-action/`。Ruff 格式与检查通过，针对安装器、
界面及维护生命周期的测试为 67 passed、202 deselected。覆盖发布/刷新错误、
运行与磁盘状态区分、只读检查、维护期间快捷键阻止和取消后 verifier 完成。

另补无 APPDIR 回归测试。已有已校验磁盘输入桥可直接刷新，不要求随包来源；
未安装且没有随包来源仍明确失败。首次客机夹具在发布前因焦点断言失败，
该次不作为功能结果，保留失败记录。以下仅记录独立复核后的实际结果。

## Ubuntu 24.04 实际按钮验收

隔离 Xorg 客机用官方 0.16.0 运行时覆盖上述冻结源码。界面显示候选源码版本
0.16.13，不是新版本 AppImage。打开可见 XCB 设置页并选择 Fcitx5 后，磁盘仍
未发布输入桥。通过实际 XTest 指针在“配置 Fcitx5 输入桥”按钮上点击一次，
随后磁盘配置存在、真实 RuntimeVersion 为 5.1.7，界面才显示已确认运行。
维护状态归于空闲，服务 owner、PID、启动时间均不变。

随后在真实聚焦且加载系统 im-fcitx5 的自有 GTK 输入框，通过 protocol 4
输出 `甲A🙂乙Ω`，最终内容完全相同。初次 UI 夹具尝试导入旧运行时未提供的
QtTest 失败，未作为功能结果。最终改用真实指针点击，未绕过按钮处理函数。
逐项结果与源码核对位于该 24 客机证据目录的 `ui.json`、`ui-source-check.txt`。

## Ubuntu 26.04 配置验收与输出限制

真实隔离 GNOME Wayland 客机加载同一冻结源码和旧包运行时，使用系统 Fcitx5
5.1.19。真实 Qt Wayland CompatibilityPage 打开并选择输出方式后未发布输入桥。
夹具调用实际 QPushButton.click 一次，经过正常按钮处理链完成配置。该轮没有
物理指针点击，不与 24 的 XTest 点击混称。明确检查按钮在配置前报告未确认
运行，配置后报告已确认运行，真实 RuntimeVersion 为 5.1.19。维护状态回到
空闲。owner、PID、启动时间保持一致，私有 bus 上没有 IBus owner。

证据位于 `/tmp/inkecho-fcitx-setup26/output/ui-r2-result.json` 和同目录 r3 的
`mechanism.json`。r2 后续 GTK 辅助程序要求错误的 GdkWayland typelib，导致
断言失败。r3 更正后真实 native GTK 已加载 im-fcitx5.so，但未获得 active /
focused 状态，等待超时，输入事件为零。两轮均未发送测试文字。保留失败，
不能将配置步骤成功扩写为本轮 26 文字输出通过。

本次新配置入口在 24 和 26 均验证了发布、刷新和运行状态。精确文本输出只在
本轮 24 完成。既往 26 输出证据属于历史版本和不同夹具，不代替本轮结果。
这些都是旧运行时的源码覆盖验证，没有制作或验收同 SHA 的新 AppImage。
26 私有实验进程已停止。串口显示正常关机，`output/qemu-exit.json` 记录
QEMU 返回 0。容器删除未在本报告中确认。
