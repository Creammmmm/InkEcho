# Ubuntu 24.04 GNOME 46 libei 1.6 TEXT 能力握手

2026-10-29 使用独立 Ubuntu 24.04.5 KVM 快照，当前会话 Wayland，已确认 GNOME Shell `46.0-0ubuntu6~24.04.16`、Mutter `46.2-1ubuntu0.24.04.18`、客机系统 libei `1.2.1-1`、xdg-desktop-portal `1.18.4-1ubuntu2.24.04.3`、GNOME portal `46.2-0ubuntu1`。只挂载 state/base/seed 为只读、使用 QEMU `-snapshot`，容器无外网，不挂载密钥目录；宿主使用客机专用测试 SSH 密钥。仅在写层将登录会话从 X11 切为 Wayland 并重启 GDM，之后测试容器已停止并删除。

宿主 `/dev/kvm` 对用户 lth 有 ACL，但容器设备节点未保留该 ACL；容器内普通用户不属于设备组 991，最初 KVM 初始化报 `Permission denied`。在独立无盘、无外网容器中给普通用户增加设备组 991 后，KVM 可用；快照测试仅使用 `--device /dev/kvm --group-add 991`，不使用 privileged，不改宿主权限。

探针使用仅解包、未安装的 KDE neon Ubuntu 24.04 构建 `libei1_1.6.0-1+24.04+noble+stable+build17_amd64.deb`（包 SHA-256 `b82cc9fe8ce555b3d769f1502f5a27a4fb1f776dfe067eb8b728a6c837d568b0`），实载动态库 SHA-256 `603223f31a831c72fc20369f7e2034336db595cfe3d37ff8237b0d92cc574c79`。不把该第三方构建或二进制包含在补丁中。探针 SHA-256 `f6ef9f38c3295f2040f191827e0e89f3a63882c5a3d6b4476827cd23a316043d`。普通 RemoteDesktop 授权选择仅键盘，无剪贴板。探针查询 seat，再绑定已公布的 KEYBOARD 能力、观察设备，没有 start_emulating、键盘或文本发送。

`results.log` 显示标准授权成功、libei 1.6 `EI_EVENT_CONNECT` 和 `EI_EVENT_SEAT_ADDED` 到达：seat `keyboard=true, text=false`；绑定 KEYBOARD 后，已加入的键盘设备 `keyboard=true, text=false`。这是新客户端同此具体 GNOME 46 会话的真实协商；因为 seat 未公布 TEXT，探针没有尝试绑定 TEXT，也未测试 TEXT 输入或其他 compositor。设备只被请求为键盘，因此不能将该设备本身当作对另一种可能独立设备的单独测试。此结果不能推导未来软件版本或其他 Ubuntu 安装。

前两次点击 Share 太早且辅助功能动作返回失败；第一轮 checkbox 异步才变为 true，第二轮又将其取消；第三轮重新勾选、等待五秒后 Share 成功。所有 `allow*.log`、`share*.log` 原样保留，不把失败计作成功。`serial.log` 是该客机启动日志，包含约两分钟 networkd 等待；与此握手无因果结论。

探针是前次实验的原样副本，包含复用旧代码留下但未调用的 `key()` 和样本文本常量；本次未调用该函数。`portal_action.py.txt` 枚举授权窗口的辅助功能动作名称，日志中虽然列出剪贴板相关动作名称，程序只调用确切的 checkbox 和 Share 按钮动作。没有读取或修改剪贴板、用户正文、真实音频或凭据。无法仅凭该握手证明任意 Unicode 输入、焦点切换、取消和送达；若将来服务端公布 TEXT，须另行隔离验证。

复现时将 `probe.py.txt` 与 `portal_action.py.txt` 复制至隔离客机的测试目录，并分别去掉 `.txt` 后缀；保留原始脚本内容及记录中的哈希，不在用户桌面运行。
