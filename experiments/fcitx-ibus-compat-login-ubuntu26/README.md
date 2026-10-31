# Ubuntu 26.04：Fcitx 的 IBus 兼容名与自动检测

测试使用隔离、无外网的 Ubuntu 26.04.1 GNOME Wayland 客机，虚拟机基础磁盘只读、临时写层；未挂载宿主用户凭据。客机安装 Ubuntu 官方 `im-config` 0.62（包 SHA-256 `20a83ff67deb010b3481cb58dfd7a7b099c21342d537d9b9f82714f59dd00e17`），执行 `im-config -n fcitx5`、安装 InkEcho 测试插件并重启。此时 Fcitx 未启动，会话仍是 IBus，见 `setup-evidence.log`。然后将系统提供的 `/usr/share/applications/org.fcitx.Fcitx5.desktop` 复制到客机用户的标准 XDG 自启动目录，重启后 Fcitx 5.1.19 由桌面启动；没有手动设置、导入或覆盖输入法环境变量。

测试以 `systemd-run --user --wait --pipe` 从用户管理器继承实际桌面环境启动探针，并在自有 GTK3 原生 Wayland 输入框内确认窗口活动与光标焦点。探针只输出固定文字、进程及配置状态，不读取用户输入或真实录音。会话实际 `XMODIFIERS=@im=ibus`、`QT_IM_MODULE=ibus`、`GTK_IM_MODULE` 未设置；两个输入法服务名称均经产品身份检查识别为 Fcitx。产品插件已安装并确认 5.1.19，测试未修改 Shell 输入源。

- `before.log`：原实现的 collector 和自动探测为 null；自动路径尝试键盘回退并报 `session_closed`，自有文本框保持空白。
- `explicit.log`：对新的空自有文本框单次选择 Fcitx，输出 `甲乙丙` 完整接收；未重放上一次输入。
- `after.log`：覆盖最终候选 `framework_detection.py`（SHA-256 `523775705dfb1b356f5162d798f94da992a79f4b6ebd11390c4d7b0168866a9d`；客机与宿主对照一致）后，collector 和自动检测均选择同一 Fcitx 唯一所有者；再次在新的空自有文本框单次自动输出 `甲乙丙`，完整接收。

`probe.py.txt` 和 `actor.py.txt` 是最后一轮程序；显式测试仅将探针的 `prepare_task('auto')` 改为 `prepare_task('fcitx')`。首次对照使用原源码，其余源码来自工作区的复制；此处是源码覆盖实验而非 AppImage 验收。两次空白控件为独立测试，不是对未知投递的重试。记录不证明所有应用、跨窗口切换、正在组词、其他系统、物理快捷键、音频或云端识别。Fcitx 发送返回不是目标应用通用接收确认。本实验不能取代相同最终 AppImage 在 Ubuntu 24.04 与 26.04 的实际验收。

继续使用上述会话的只读快照重启客机，`session-normal.log` 通过真实 `Session`、本地合成录音/识别及流式润色对自有原生 Wayland GTK3 输入框输出 6 字，dispatch 记录协议 4、Fcitx 路由、各次单调时刻，文本框完整收到 `甲乙丙丁戊己`；`session-cancel.log` 在首字回调时主动取消，1.3 秒后仅观察到首字。两项使用旧 AppImage 的 Python/Qt 运行时（哈希载于日志）及工作区源码覆盖，不是该包的产品验收。最终路由字段在 Session 清理后为空，发送期间的 dispatch 路由才是选择证据。

在客机为 Fcitx 启用已安装的拼音引擎后，QMP 向确认焦点的独立 GTK3 窗口发送 n、i，`preedit-result.json` 显示两字符预编辑、文本为空；随后自动路由返回 `fcitx_composition_active` 且 attempts 为 0，约 0.5 秒后预编辑仍为 2、正文仍空。测试在输出上下文内部捕获组词错误后，上下文退出另报告 `output_failed`；这段附加错误如实保留，不视为完全无异常的任务结束。结果仅证明该时序和控件中的保护，并非目标应用接收确认。

`browser-normal.log` 为另一个独立 Chrome 原生 Wayland 的自有 textarea；从系统用户管理器继承原输入法环境，自动选择 Fcitx，收到 `甲乙丙`，Wayland trace 确认 compositor、toplevel、keyboard；浏览器是测试版本并使用独立测试配置。初次浏览器夹具因错误引用候选路径而在启动浏览器前失败，修正夹具后成功；不能推断任意网站。

后续从实验快照再次启动，`*-verified.log` 和 `preedit-result-verified.json` 复测上述成功、取消、浏览器和组词样本；各测试驱动进程及 Session 实际子进程在日志中输出已导入的检测器模块 `__file__`、该单个文件的 SHA-256 及进程继承的输入法环境，不证明整个源码树一致。Session 的模块身份记录来自使用 AppImage 运行时的实际子进程，不是父进程推断。浏览器驱动由用户管理器环境启动、未设置 IM 变量；浏览器子进程的输入法环境仅由传入环境推断，未独立读取验证。驱动为确保原生 Wayland 移除了浏览器子进程的 DISPLAY 并设置了调试变量。客机的 `~/.config/environment.d/90-inkecho-qa.conf` 不存在。旧测试素材目录携带的 `setup-login.py` 及旧 `input/src` 并未在本实验中运行或作为被测源码；检测器源码路径由日志确认。
