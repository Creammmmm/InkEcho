# 私有 Wayland 双事件队列反例（阶段 0）

2026-10-30，本机 Ubuntu 26.04.1。双端使用 `socketpair`，仅连接自建 libwayland 服务端与客户端，不连接宿主 Wayland、输入法、D-Bus 或实际应用。使用 Ubuntu 官方 resolute 软件包 libwayland-bin/dev 1.24.0-2、wayland-protocols 1.47-1，scanner 使用包内官方 xdg-shell 和 text-input-unstable-v3 XML 生成绑定；动态链接宿主 libwayland-client/server。下载清单、包和关键文件哈希分别在 `packages.txt`、`debs.sha256` 和 `sha256.txt`；`host-lib-sha256.txt` 记录本次使用的部分宿主运行库。在项目根目录执行：

```sh
bash experiments/wayland-ping-queues-20261030/prepare.sh
bash experiments/wayland-ping-queues-20261030/run.sh
```

准备脚本按精确版本下载并 SHA-256 验证后才解包，不安装系统包，拒绝覆盖已有 root；可设置 `INKECHO_WAYLAND_LAB_DIR` 为新目录。需 Ubuntu resolute 软件源、gcc、libwayland 客户端/服务端运行库。全新目录 `/var/tmp/inkecho-wayland-repro-2` 复现成功，见 `prepare.log` 与 `fresh-run.log`；修改为可独立准备的脚本前曾成功连续 5 次，见 `repeat.log`。

客户端将 xdg_wm_base 和 zwp_text_input_v3 指定为两个不同的 libwayland 事件队列。服务端对同一连接按 `commit_string("A")`、`done(1)`、`ping(42)` 顺序发送并 flush。客户端只分发 xdg 队列，按真实 xdg 协议回复带原序号的 pong；服务端收到 pong 后通过自有管道通知客户端。此时客户端文字 commit 和 done 回调计数均为 0；之后分发文字队列，计数分别变成 1。输出由断言校验，说明 libwayland 允许跨队列回调按不同于服务端发送顺序执行，即使服务端收到与本次 ping 完全匹配的 pong，也不蕴含先前文字回调已处理。

这是使用正式协议接口的合成最小服务端/客户端，并未创建真正的窗口、焦点、text-input enter/enable 状态或完整合成器，也不是 GTK、Chrome、Mutter 桌面或应用端最终文字是否显示的测试；它提供的是合法的独立客户端事件队列调度反例，不证明常见客户端必然采用此配置，更不授权放宽产品保护。尚未验证强制中断、失败路径的进程或临时目录清理。最初一次重跑在客户端关闭管道后测试服务端未移除事件源而断言退出，结果不计通过；修复事件源移除后重跑一次和连续五次均退出 0。

Ubuntu 的 Mutter 46 构建源码 `dist/mutter46-done-boundary-20261030/output/mutter-source`：`core/delete.c` 的公开 `meta_window_check_alive` 不返回回执，只调用内部 `meta_display_ping_window`；`core/display.c` 对同窗口已有 pending ping 直接返回、pong 用 serial 找记录并调用 `meta_window_set_alive(TRUE)`，`core/window.c` 若状态已为 TRUE 不发 notify，因此无法使用正常 `is-alive` 通知作为逐次 pong 回执。该源码的 SHA-256：display.c `4c8c736a0557d6fae641a4bb3b61dc2c9892372890e1157b998c17f7491fcc5f`，window.c `63dc3e62dbae5eb6e81a7521abda918e8d0552002bf6fdea7e7ddf962d87c636`，delete.c `df92da297dfc07db939f2765e85f0db8ca9dde6f34b213e98f267e7ec91fa35f`，meta-wayland-xdg-shell.c `3a2b20968995a853de2d486fe2d1e78efd1037e64c07bd336094db7f1d12ff0a`。官方上游 [Mutter 50.1](https://github.com/GNOME/mutter/tree/50.1/src) 的同一逻辑具有相同结果，文件哈希见 `mutter50-sha256.txt`；尚未验证 Ubuntu 26.04 发行版补丁或运行时。源码观察也没有将时钟等待、刷新或 producer boundary 当作客户端应用已处理的回执。
