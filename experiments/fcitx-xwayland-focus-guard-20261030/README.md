# Fcitx 私有 XWayland 焦点关联实验

2026-10-30 本机 Ubuntu 26.04.1，隔离 Weston 14 headless、宿主 XWayland、私有总线、Fcitx 5.1.19 和仓库打包的 Fcitx 插件。实验隔离网络、PID、X socket 和总线，不连接用户输入法或剪贴板；根文件系统只读绑定而非保密隔离。先使用 `experiments/fcitx-xwayland-gtk-private-20261030/prepare.sh` 准备 Weston 和 Fcitx 的官方依赖，再使用本目录 `prepare-xres.sh` 按精确版本下载并校验 XRes 开发包；脚本拒绝覆盖已有 root，不安装系统包。`INKECHO_LAB_DIR` 和 `INKECHO_XRES_LAB_DIR` 可分别指定新目录；焦点测试使用 `/var/tmp/inkecho-fresh-reproduce` 和 `/var/tmp/inkecho-xres-fresh-20261030`；另在新目录 `/var/tmp/inkecho-xres-project-fresh` 验证依赖准备，输出为 `xres-prepare.log`。在项目根目录依次执行：

```sh
bash experiments/fcitx-xwayland-focus-guard-20261030/run-unmodified.sh
bash experiments/fcitx-xwayland-focus-guard-20261030/run.sh
bash experiments/fcitx-xwayland-focus-guard-20261030/run-samepid.sh
python3 experiments/fcitx-xwayland-focus-guard-20261030/check-cleanup.py different
python3 experiments/fcitx-xwayland-focus-guard-20261030/check-cleanup.py same
```

只做受控测试，不修改系统输入法。每次编译均使用独立临时目录，并校验打包插件的固定哈希；当前脚本依赖仓库中的该原插件版本和宿主 GTK3/XWayland/Mesa/XCB 运行库。当前实验预加载 hook 仅显式应用于新启动的私有 Fcitx 进程；无 preload 轮先清除继承环境的 LD_PRELOAD。`sha256.txt` 固定最终脚本、原始输出及插件；XRes 包由准备脚本校验，上游源码哈希见 `upstream-sha256.txt`，宿主其他动态库未全部固定。

## 两进程陈旧焦点

未使用 preload、但加载测试插件的实验 `unmodified.log`：独立 GTK A 先用 XIM 获焦，SIGSTOP A 后检查进程状态 T；独立 GTK B 的 `gtk-im-module=simple`、顶层和输入控件获得焦点。Fcitx ibusfrontend 禁用，私有总线没有 IBus 服务，@server=ibus 是 Fcitx 自有 XIM 名称。B 的进程映射列表出现 im-ibus.so，因此不声称该模块未加载。测试插件读取 Fcitx 唯一上下文 `xim|python3.14|x11::0`；桥 Begin3=True、Commit=1。保持 A 停止 1 秒时 B 为空，A 恢复后失焦却收到“测”，B 仍为空。该轮未注入下面的映射 hook，不能据此认定其他客户端、普通非冻结切换或真实 GNOME 也必然发生同样问题。

`result.log` 是后续带测试插桩的重跑：XGetInputFocus 读到 B 的顶层 XID，XRes 分别识别 A 和 B 为不同 PID，且与受控子进程一致；仅在私有 Fcitx 进程通过 LD_PRELOAD 测试 hook 捕获 XIMInputContext 与 xcb-imdkit 私有 XIM 对象的对应关系。测试插件读取到旧 A 的 XIM 子窗口，XRes 识别为 A 的 PID；插件的测试判定在 A 聚焦时为 1，在 B 聚焦时为 0。判定方法只查询、不调用产品 Commit；后续刻意绕过它直接调用原桥，重现失焦 A 收字。`TEST_GUARD_REJECT_ZERO_ATTEMPTS` 指控制脚本的测试分支，不是已集成产品的原子 guard。

## 同进程不同窗口

`samepid.log` 的自有客户端在一个进程创建 A/B 顶层窗口，A 先获得焦点；测试暂停整个客户端，再由测试进程将 X 服务器焦点设到 B。XIM 子窗口和 B 焦点都属于同一 PID，测试 PID 判定返回 1，造成假匹配。原型查询 XQueryTree 顶层祖先时，A 状态返回 1，B 状态返回 0。此项没有发送文字，客户端被暂停，不能声称 B 的 GTK 光标已处理聚焦。祖先关系只覆盖该自有窗口样本；同一顶层不同控件、焦点查询与提交之间的竞态、活动预编辑、不同 X11 层级和非 XIM 前端均未解决。XRes PID 相等或顶层相等不构成实际提交的原子授权。

前一轮未禁用 Fcitx IBus 兼容前端时 B 收到文字，见 `with-ibusfrontend.log`；该轮不能证明前端独立。又一次误用 @im=fcitx，而 XIM 实际注册 @server=ibus，导致 Commit=3，见 `wrong-xim-name.log`。两轮不是最终通过结果。

上游 5.1.19 的 `XIMInputContext` 持有私有 xic，窗口须通过该内部对象读取；DBusInputContext1 持有私有 sender。公开的基础 InputContext 没有可靠的上下文与 X 窗口或 DBus 连接映射。测试 hook 必须在启动私有 Fcitx 时预加载，依赖内部实现与 ABI，不能注入现有用户服务或直接用于产品；DBus/GTK 前端也未覆盖。没有测试真实 GNOME、真实 IBus daemon 共存、活动拼音、取消、Ubuntu 24.04 或跨后端发送顺序。现有生产防护不得据此放宽。


## 时序与异常退出

最终三次正常实验的 `MONOTONIC_NS` 行依次记录当前焦点确认、目标进程停止、切换后的 X 焦点观测、测试判定、直接调用前后和恢复后的观察。比如 `unmodified.log` 中，B 获焦时间为 249112813586999 ns，调用 Commit 为 249112830341487 ns，A 恢复请求为 249113835934287 ns；A 的最终文本在恢复后读取。数字仅为同一轮的本机单调时钟里程碑，不是泛化的性能或事件确认保证。

`check-cleanup.py different` 与 `same` 分别在冻结测试客户端后制造受控异常，故障前从宿主 `/proc` 以 bwrap 报告的 PID namespace 验证 Weston、XWayland、Fcitx、总线和一个状态 T 的测试客户端均存在，脚本退出码均为 1；两项均确认 namespace 内进程为空、测试编译及私有 /tmp 目录被移除。对应 `cleanup-different.log`、`cleanup-same.log`，测试过程输出为 `fault-different.log`、`fault-same.log`。日志仅规范化行末空白，其他内容保留。每次使用私有 PID namespace 和 `--die-with-parent`，控制脚本 finally 会先恢复并结束受控客户端，内层 trap 清理私有 Fcitx 和 Weston；不涉及用户的同名进程。只验证了受控异常；未测试 SIGKILL、宿主崩溃、内核故障或所有其他异常。复跑默认不写入归档日志，只有设置 `INKECHO_FAULT_LOG_DIR` 才将本次故障原始输出写入指定目录。

## 本批验证汇总

[Ubuntu 24 客机记录](../fcitx-xwayland24-session-015-20261030/REPORT.md) 和 [Ubuntu 26 客机记录](../fcitx-xwayland26-session-015-20261030/REPORT.md) 使用同一 0.15.0 AppImage，分别验证各自受控 Fcitx/XWayland GTK 场景。当前私有焦点实验另以受控暂停测试陈旧上下文；[Wayland ping 队列实验](../wayland-ping-queues-20261030/README.md) 是独立合成协议反例。这些记录各自有不同范围，均不能证明任意应用、跨 IBus/Fcitx 后端交接或完整双系统发布验收。
