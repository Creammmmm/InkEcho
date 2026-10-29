# GNOME 扩展 info 输出与安装文件状态验证

2026-10-29，分别在独立 QEMU 快照中测试 Ubuntu 24.04.5 / GNOME Shell 46.0 X11 和 Ubuntu 26.04.1 / GNOME Shell 50.1 Wayland；系统盘、基础盘、seed 只读挂载，容器无外网、未挂载密钥。宿主仅使用各客机专用 SSH 测试密钥。测试代码是工作区 `ibus_extension.py`，SHA-256 `399b4ecca28e2544c677797a731997b8a4c7dd215c40dc0ff029232b3df5438c`，不是 AppImage 安装验收。两台客机都只操作测试专用 UUID `inkecho-ibus-v2-prototype@local.invalid`，没有用户数据或剪贴板。

两版系统均调用真实 `gnome-extensions install` 安装候选扩展，但已运行会话尚不能通过 `info` 发现它，首次 enable 和 uninstall 返回错误；保留首轮日志。测试仅在快照内重启 GDM，让 Shell 扫描磁盘。重启后的 `probe-relogin.log` 中，两版真实 `gnome-extensions info` 输出均包含 Path 与 State: ACTIVE，路径指向自建用户扩展目录；`ExtensionManager.status()` 显示“安装文件已校验”，并注明无法确认运行代码和输入框兼容性。

测试改动该临时扩展的 `delivery_gate.js` 后，状态报告文件未通过校验；恢复原始字节后状态再次显示文件已校验。随后从刚才真实 `info` 输出中去掉 Path 行并用测试替身返回该文本，状态拒绝确认：**缺失 Path 是基于真实输出的模拟，不是 GNOME 实际产生的输出**。恢复正常调用后禁用、卸载，命令返回 0，状态显示未发现。初始无效样本与重试均保留，未当作通过。24 客机首次 SSH 因网络初始化超时，另一次等待后成功；`ubuntu24/probe.log` 保留失败。

两台分别正常请求 poweroff，容器均 `docker wait=0`、`ExitCode=0 OOMKilled=false`，已删除；快照内未逐项恢复配置，原镜像只读。没有截图。单一安装输出不证明其他 GNOME 版本、语言或设备，也未检验正在内存执行的扩展代码、并发篡改、输入功能、包验收或 Wayland/X11 全组合。

仅在一次性隔离客机复现：将该版本的 `ibus_extension.py` 与 `src/inkecho/platform/ibus_candidate` 复制到 `/tmp/inkecho-ext/`，将 `probe.py.txt` 去后缀放在同目录，在图形用户会话的 D-Bus 环境执行 `python3 /tmp/inkecho-ext/probe.py`；如刚安装未被识别，在隔离客机重启图形会话后运行 `python3 /tmp/inkecho-ext/probe.py --installed`。探针会安装、启用、修改、恢复、禁用并卸载自建扩展，不可在真实桌面使用。探针 SHA-256 `596fee7e06b56aec7d825dafea13e2e4cfe8036dbe7759bec0c1e6536f007e7f`。
