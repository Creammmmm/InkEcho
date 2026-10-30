# 隔离 XWayland / GTK / Fcitx 阶段 0 探针

2026-10-30 在本机 Ubuntu 26.04.1，用单独网络及 PID 命名空间、临时 HOME、X socket、私有 D-Bus 和 Weston 14 headless + pixman 启动宿主 XWayland。私有会话使用官方 Ubuntu 解包的 Fcitx 5.1.19、xcb-imdkit 1.0.9、Weston 14 和宿主 GTK 3/XWayland，不安装系统包、不连接宿主输入法或剪贴板。AppArmor 只对私有会话总线关闭；全局策略未修改。仅发送固定测试字符。根文件系统是只读绑定而非完全隔离：宿主文件仍可读取，宿主系统库和工具可见；/tmp、/dev 和 /proc 有单独挂载。不要将此视为保密沙箱。

在 Ubuntu 26.04 amd64 的项目根目录，以配置了 Ubuntu resolute 软件源的 APT 执行：

```sh
bash experiments/fcitx-xwayland-gtk-private-20261030/prepare.sh
bash experiments/fcitx-xwayland-gtk-private-20261030/run.sh
python3 experiments/fcitx-xwayland-gtk-private-20261030/check_cleanup.py 1
python3 experiments/fcitx-xwayland-gtk-private-20261030/check_cleanup.py 2
```

准备脚本按 `packages.txt` 中的精确版本下载，依据 `debs.sha256` 逐一验证后使用 `dpkg-deb -x` 解包，不调用系统包安装。默认放在 `dist/fcitx-xwayland-private-20261030`；可设置 `INKECHO_LAB_DIR` 使用新的空目录，且准备脚本拒绝覆盖已有 root。仓库中记录的是 `ce402c9` 时插件哈希；运行脚本会检查该哈希。上述源上版本消失或宿主组件不一致时不能直接复现。除下载的组件外还需宿主 bwrap、gcc、pkg-config、dbus-run-session、Python GI GTK3、Xwayland、xprop、Mesa。脚本编译仅用于测试的 Fcitx 插件，并加载项目打包的 `assets/native/fcitx5/x86_64/libinkecho.so`。GTK 是自有 popup 窗口，通过自有 XSetInputFocus 获焦；这不是验证桌面上的真实窗口切换。Fcitx XIM 在此注册为 @server=ibus，客户端强制 GTK_IM_MODULE=xim、XMODIFIERS=@im=ibus，因此本实验没有启动 IBus。Begin3 使用私有一次性测试凭据。

`run.log` 为最终重跑：第一窗口确认为 X11Display 且输入框获焦，测试插件清空 inputPanel，PREEDIT=1、Begin3=True、Commit=1，GTK 收到“测”。第二窗口获焦，测试插件对真正的该 XIM 输入上下文设置合成 client preedit，PREEDIT=2、Begin3=True、Commit=5，GTK 内容为空。断言验证状态及最终文本。预编辑不是由真实拼音引擎产生，未证明其候选界面或语义；Commit=1 只是该桥的发送尝试，不是通用客户端确认。

初次由宿主 NVIDIA EGL 导致 Xwayland 崩溃，改为 Mesa；常规 GTK 顶层窗口触发 Weston 窗口管理断言，使用 popup。最初错选 @im=fcitx 导致无输入上下文。一次旧探针在窗口间注入 XTest 键时产生延迟字符“a”，使对照被污染；最终脚本不发送该合成键并重新通过。不能据此证明事件顺序及跨后端安全交接；特别没有先向 owned IBus 原生 Wayland 输出、转移到 XWayland 再确认之前输出，未验证竞态、取消、真实拼音、用户应用、GNOME、Ubuntu 24.04 或 AppImage。禁止据此放宽生产保护或宣称完整支持。

故障验证：`python3 experiments/fcitx-xwayland-gtk-private-20261030/check_cleanup.py 1` 在 Fcitx 启动后模拟失败，退出码 42；参数 `2` 在真实 GTK 客户端已获得焦点后模拟失败，退出码 43。两次都先从宿主 `/proc` 按 bwrap 报告的 PID namespace 确认 Weston、XWayland、私有总线、Fcitx 等进程存在，再在退出后确认该命名空间无进程。结果分别见 `cleanup.log`、`cleanup-client.log`，当次原始输出见 `failure-1.log`、`failure-2.log`；复跑不会覆盖这些记录。bwrap 使用 `--unshare-pid --die-with-parent`；shell 对 Weston 和 Fcitx 分别设置退出清理，PID namespace 负责清除其余后代。该验证未覆盖宿主崩溃或外部内核故障。

`debs.sha256` 保存全部下载 deb 的哈希；主要包的当前 Ubuntu 软件源和版本见 `apt-policy.txt`，下载地址是 Ubuntu resolute 官方软件源 http://archive.ubuntu.com/ubuntu 。`host-component-sha256.txt` 固定部分宿主组件，不涵盖全部动态依赖；`artifact-sha256.txt` 固定探针和日志。原始复现路径 `/var/tmp/inkecho-fresh-reproduce`，验证输出见 `prepare.log` 和 `run.log`；后者仅清除了行末空白。材料属于阶段 0 实验，不是提交或发布验收。
