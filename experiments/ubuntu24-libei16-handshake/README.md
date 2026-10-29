# Ubuntu 24 客机新版 libei 文本能力的核查边界

本次没有启动虚拟机、连接桌面、改系统或发送任何事件。此前真实隔离客机记录见仓库 `experiments/ubuntu24-remote-input-capabilities/versions.log`：Ubuntu 24.04.5、Wayland、GNOME Shell 46.0-0ubuntu6~24.04.16、libmutter-14-0 46.2-1ubuntu0.24.04.18、libei1 1.2.1-1、xdg-desktop-portal 1.18.4-1ubuntu2.24.04.3。原接口探测仅 introspection，不等于新版 libei 能力协商。

本任务沙箱内 `command -v qemu-system-x86_64` 无结果，`docker ps` 返回 `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`。可见系统库 `/usr/lib/x86_64-linux-gnu/libei.so.1.5.0`，`nm -D` 没有 `ei_device_text` 符号，有限范围的 `/tmp` 搜索未找到 1.6 客户端。无法在该隔离环境构造有效的 libei 1.6 客户端与运行中的 Ubuntu 24 compositor 的协商；不能把旧库及已退出的探测会话当新实验。

[Ubuntu 官方同版源码包目录](https://packages.ubuntu.com/source/noble-updates/mutter) 列出 `mutter_46.2-1ubuntu0.24.04.18.debian.tar.xz` 和上游 46.2 原始源码，其版本与客机记录相符。当前没有取得并检查该补丁包；这不等于 Ubuntu 构建和上游逐字一致。[上游 46.2 EIS 源码](https://raw.githubusercontent.com/GNOME/mutter/46.2/src/backends/meta-eis-client.c) 只配置键盘和指针类 seat 能力，没有实现文本设备，但也不能代替 Ubuntu 补丁审计或实测协商。

后续可行的隔离实验需要：可访问的只读 Ubuntu 24 客机基础盘和专用临时写层；客机专用测试凭据；可运行于客机的 libei 1.6 库与探针，且不要替换系统动态库；仅申请桌面输入授权、记录 seat/device capability 与协议握手，不发送文字或读取用户窗口，结束时释放会话。分别检查包内源码补丁和客户端实际协商；如果没有 text capability，不将升级客户端宣称为修复。如果有，另行使用自有目标验证焦点、取消、Unicode 和可否确认送达。

## 补充：取得源码和客户端后的结果

经审核网络访问，已从 Ubuntu 官方包池取得同版 `mutter_46.2-1ubuntu0.24.04.18.debian.tar.xz`，MD5 `d141f99aa2543689feeb7dff2c29a304` 与官方源码索引一致。在解压出的 `debian/patches` 对 `meta-eis-client.c`、`EIS_DEVICE_CAP_TEXT`、`eis_seat_configure_capability` 和 `EIS_EVENT_TEXT` 搜索均无匹配；此结果只说明相关文本未出现在补丁文件，不能替代将补丁应用后逐行审计或动态协商。上游 46.2 EIS 源码没有广告文本 seat 能力，与这项补丁搜索一致。

从 KDE neon testing 包池取得 Ubuntu 24.04 编译的 `libei1_1.6.0-1+24.04+noble+stable+build17_amd64.deb`，仅在临时目录解包，未安装系统库。包 SHA-256 `b82cc9fe8ce555b3d769f1502f5a27a4fb1f776dfe067eb8b728a6c837d568b0`；动态符号表包含 `ei_device_text_keysym` 和 `ei_device_text_utf8`。也取得上游 libei 1.6.0 源码，MD5 `08186470213bdba5a4e58d322368f31d`。这些材料证明可准备新客户端，不代表服务端宣告该能力，亦不代表完成协商实验。

审核后的只读 Docker 查询发现旧虚拟机工具镜像及已退出快照，同时另一个任务的隔离客机正在运行；没有操作它。旧容器含测试 SSH 凭据挂载，安全重跑需创建新的无凭据挂载容器。当前尚缺已实现 `EI_DEVICE_CAP_TEXT` 的只读协商探针及完整的客机授权清理步骤；为了不把旧 1.2 探针当作新库协商，本次没有启动新会话，故未进行新实验。

## 2026-10-29 实际独立握手尝试

新建 QEMU 快照，原 state/base/seed 只读，未挂载测试密钥目录，容器无外网，输出目录在 /tmp；为 SSH 从宿主使用原有客机专用测试密钥。KVM 启动报 `Could not access KVM kernel module: Permission denied`，故改用软件 TCG。首次登录为 X11，故仅在快照中将 GDM/AccountsService 切至 Wayland 并重启；`loginctl` 随后记录 `Type=wayland`、`Active=yes`。每次启动都经历网络等待约两分钟。

探针为 `probe.py.txt`，载入临时 libei 1.6，尝试申请键盘授权后读取座位的 KEYBOARD/TEXT 能力及对应设备；只绑定已广告的能力，不开始模拟或发送文字/按键。首轮 CreateSession 调用因三秒超时失败；第二轮以 20 秒上限重试，仍在 CreateSession 超时。`guest-results.log` 记录两轮回溯和隔离客机 journal；其中 GNOME Shell 于 portal 启动前因信号 11 退出，GNOME portal 服务依赖失败，进程被会话管理器重启。未出现授权对话框，未取得 EIS fd，未执行能力握手，不能对目标系统实际能力作新的结论；这是测试环境错误，不能归咎产品。

曾首次尝试管道传输探针时遇到 tar 输入错误；随后单独传输成功，再运行两轮探针。测试结束后停止并移除独立容器；快照内临时改动丢弃。无产品修改、剪贴板调用、真实语音/凭据及第三方并行客机操作。保留串口日志 `serial-tcg.log`；测试依赖与库未附入此补丁。不同机器上重跑还须确保 GNOME 会话和 portal 正常，不能据此报告动态支持或不支持。

补丁保留实际运行探针的原样源码（包括复用旧探针时遗留、未调用的 `key()` 辅助函数与样本文本常量）；本次执行路径没有调用该函数，未发出 `NotifyKeyboardKeysym`。探针实际停在取得 EIS 文件描述符之前。`portal_action.py.txt` 是本次准备的隔离授权工具，因授权对话框未出现而未执行；源码中的剪贴板相关字符串来自无操作的辅助功能动作名称枚举，代码不调用剪贴板动作。日后运行须在空白独立客机中核验执行路径，避免把旧探针中的遗留函数误认为已调用或已验证。

复现时将 `probe.py.txt` 与 `portal_action.py.txt` 复制至隔离客机的测试目录，并分别去掉 `.txt` 后缀；保留原始脚本内容及记录中的哈希，不在用户桌面运行。
