# Ubuntu 24.04 Xorg 的 Fcitx Qt6 受控验证

在网络隔离 Ubuntu 24.04.5 GNOME Xorg 客机的一次性写层中，使用系统 Qt 6.4.2、PyQt 6.6.1、Fcitx 5.1.7 及匹配的 Qt6 前端 5.1.4，运行两个系统 Python QPlainTextEdit 测试窗口。当时在客机执行了 34 个安装包与软件源元数据的 SHA-256 比较并观察到通过，但未保存原始逐包回执，无法独立复核；包安装只影响临时客机。插件调试日志证明加载了 `/usr/lib/x86_64-linux-gnu/qt6/plugins/platforminputcontexts/libfcitx5platforminputcontextplugin.so`，而非先前与 AppImage 自带 Qt ABI 不兼容的组合。

通过真实生产 Session 合成文本，自动路由选择 Fcitx 协议 4。200 个中文字符在主动切换的两个窗口中分别收到 18 和 182 个，拼接完全一致；首字后程序取消，两个窗口分别收到 1 和 0 个，在额外 1.3 秒观察期没有后续文字。完整记录见 [系统 Qt6 日志](qt6-system-run.log)。

使用 XTest 输入 `ni` 在 Qt 窗口确实触发 `n`、`ni` 组词事件；自动路由随后返回 `fcitx_composition_active`、0 次尝试，事件与文本均未改变，空格提交了“你”。见 [组词保护记录](preedit-second-run.log)。[首次组词日志](preedit-run.log) 因夹具错误处理没有向会话传播异常而失败，不能作为产品测试结果；修正夹具后重试才得到上述结果。

客机的 `fcitx5.py` SHA-256 为 `790300a2eaf14fffc0d66b327ab488fd7e694177088b9677edc9053b295897c4`，与本次宿主工作树一致；执行时另一次命令观察到客机编译出的 `product-native-build/libinkecho.so` SHA-256 为 `f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44`，但未持久保存该命令的原始输出，无法独立复核。身份和清理见 [回执](guest-identity-cleanup.txt)：其中错误路径 `product-native-build/inkecho.so` 不存在，不能用于证明插件摘要。测试后客机配置恢复、插件与临时环境文件移除。

以上均为手动设置 `XMODIFIERS`、`GTK_IM_MODULE` 和 `QT_IM_MODULE` 的合成任务，不证明系统自动配置发现、物理麦克风或快捷键、真实云端、Wayland、Ubuntu 26.04、任意焦点切换时机，亦非最终 AppImage 包验收。Fcitx 的发送返回不是目标应用完成接收的通用确认。测试夹具来自前次 Qt 实验，并使用旧 AppImage Python 运行时加载冻结生产源码，不代表该旧包的产品验收。

客机正常关机，QEMU 及容器均退出 0；临时写层归档的完整解压流校验结果见 [归档回执](ram-overlay-archive.json)。原始归档保留在 `/var/tmp/inkecho-terminal-qa/output/`，不属于仓库证据。

仓库中的日志仅移除行尾空白；原始运行日志保留在本机临时证据目录。
