# GNOME 46 键盘映射候选：离线编译初探

这是离线可行性探针，**不是 GNOME 实测或应用验收，不得用于生产**。Ubuntu 24 GNOME 46 在此前实验缺少当前产品所需的远程桌面 SetKeymap。查阅 GNOME Shell 46 的 [`keyboardManager.js`](https://raw.githubusercontent.com/GNOME/gnome-shell/46.0/js/misc/keyboardManager.js) 和 [Mutter 46 后端](https://raw.githubusercontent.com/GNOME/mutter/46.0/src/backends/native/meta-backend-native.c) 可见 Shell 自身有按布局、变体、选项和型号重设 seat 键盘映射的调用。由此提出利用 XKB option 向空槽追加 Unicode 映射的假设；该调用操作座位级全局状态，和 RemoteDesktop 的 SetKeymap 不是同一接口。

本次只在宿主机独立临时 XDG 配置离线调用 libxkbcommon 1.13.1-1 编译映射。`offline.log` 显示 `us`、`pc105`、无 option 的基线成功编译且输出中无符号键定义；带 `inkecho:test` 时同样成功，文本输出出现 `key <AE13> { [ 0x1007532 ] };`，即 U+7532。`<I132>` 是 `<AE13>` 的别名。脚本只打印包含这些字段的行，没有比较完整 keymap 内容，因此不能说其余键位完全不变。该测试没有输入字符、修改宿主桌面、使用剪贴板或切换系统输入法，也没有测试 Ubuntu 24 自带 libxkbcommon。

复现离线编译：复制本目录 `config` 到一个临时空目录，将 `check.py.txt` 改名为 `check.py`，执行 `XDG_CONFIG_HOME=<临时目录>/config python3 <临时目录>/check.py`；Python 需能加载 `libxkbcommon.so.0` 及常规系统 XKB 规则。不要把测试的 `rules/evdev` 写入实际用户配置：它会遮蔽同名用户规则，且此演示未处理现有用户设置的合并。

## Ubuntu 24 快照未进入实测

对已有 Ubuntu 24 QEMU 镜像建立 `-snapshot` 临时写层，客机盘、基础盘及 seed 只读绑定；容器采用 `--network none`，测试未接触实际用户桌面。三次启动均未得到可用 SSH，串口日志停留或主要停留在 `systemd-networkd-wait-online`；前两次分别使用受限和普通 QEMU 用户网络，第三次恢复原有虚拟设备顺序。日志按原始字节保存在 `serial.log`、`serial-retry.log`、`serial-third.log`；SSH 轮询当时显示 banner 超时，但其输出未另行保存。网络等待的具体原因未知，不能据此判断任何产品功能。三次均未安装扩展、改客机 XKB 文件或发送输入。前两次强制删除一次性容器；第三次通过 QMP 请求关机，随后 Docker stop，容器退出码 0。原盘只读，不声称验证了客机正常关机或恢复功能。

下一阶段需先验证真实 GNOME 46 是否加载自定义 option，以及不覆盖原有自定义规则的方法；然后使用自有窗口严格验证完整映射、锁定及恢复、用户并发按键、焦点切换和取消。还要验证读取用户现有映射及竞态处理，避免覆盖其他程序或用户的变更。任何一种测试未完成时都不能自动启用该路径，也不能用其声称 Ubuntu 24 Wayland 支持或通过发布验收。

SHA-256：

- `check.py.txt`: `67915fb21bf060177431cd27040ab6f618889cce0efdc28b11b7cdd7224dbfa7`
- `config/xkb/rules/evdev`: `0a120d0c8385b87cb37f374c1144fe6c0abc329f282a3b108e4fb31a91537c1e`
- `config/xkb/symbols/inkecho`: `35f7c1b20d2308e02f5cc01c2b9592fd0c5ad3a029d8f6de0826360f77a035f4`
- `offline.log`: `8311b436e346d95112036bd44aeea4f70d10078bf011744dd88b42636019db07`
- `serial.log`: `58ce6ffe9b2727122cb521a720b9c951281ba8585dfd01bb126318d4466daf1f`
- `serial-retry.log`: `e84d9b1f58a3e12ddac11e41cfa711474f2e60f0231182d9e70893f477ed37cc`
- `serial-third.log`: `435c5b90e644113841fffaac91be11e073fcec4246cc1701c125e1a7c943fed5`
