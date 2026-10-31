# Ubuntu 24.04 Xorg：正常登录 Fcitx 验证

使用隔离、无外网的 Ubuntu 24.04.5 GNOME Xorg 客机，原始镜像只读且使用临时写层。客机使用发行版 `im-config -n fcitx5`、标准 Fcitx 自启动项及测试版 InkEcho 插件，重启后用户管理器自然生成 `XMODIFIERS=@im=fcitx`、`GTK_IM_MODULE=fcitx`、`QT_IM_MODULE=fcitx`；没有为应用或系统会话注入这些值。Fcitx 5.1.7 同时拥有 Fcitx 与 IBus 服务名。`login.log` 和 `probe.log` 记录了会话、插件、运行时实际加载文件路径和 SHA-256 `523775705dfb1b356f5162d798f94da992a79f4b6ebd11390c4d7b0168866a9d`。

`probe.log`：自有 GTK3 X11 输入框获焦，自动路由选择 Fcitx 并完整收到 `甲乙丙`。`session-normal.log`：真实 Session 使用合成录音、识别和流式润色，6 字全部送至自有 GTK3 输入框；`session-cancel.log` 在首字发送后程序取消，1.3 秒观察只收到首字。两者记录被测进程中的检测器路径和哈希、每次 dispatch 的路由与单调时刻；最终清理后 route 为空。Session 使用旧 AppImage Python/Qt 运行时及源码覆盖，运行时哈希载于日志，并非最终包验收。

`preedit-pass.json`：只在隔离客机设置已安装的拼音引擎，QMP 向确认焦点的自有窗口发送 n、i；预编辑长度 2 时自动路由报 `fcitx_composition_active`，attempts=0，0.5 秒后预编辑仍是 2、正文为空。夹具在上下文内捕获该错误后，上下文退出额外报 `output_failed`；该结果不代表任务正常结束。`preedit-timeout.json` 保留上一轮因按键未在 30 秒前置窗口到达而无法形成组词的失败；另一次因焦点上下文未建立导致引擎为空的前置失败未保存原始记录。

`browser-pass.log`：从系统用户管理器环境启动的独立 Chrome X11 自有 textarea，焦点确认后自动路由选择 Fcitx，完整收到 `甲乙丙`，运行进程记录相同检测器哈希。首次浏览器启动失败，因 9p 只读挂载的 Chrome sandbox 所有权不满足要求；`browser-failed-stderr.log` 保留原因。在客机复制浏览器并设置标准 root/4755 sandbox 后重试成功；未禁用浏览器沙箱。

该客机的系统提示本身为 fcitx，走既有的 Fcitx 检测分支，**不能证明提示为 ibus 时的新兼容分支在 Ubuntu 24.04 生效**。这里只覆盖所列应用、固定时序及合成语音，不证明所有程序、焦点竞争、真实麦克风或云端服务；发送返回不是目标应用通用接收确认。不得将源码覆盖实验视作最终同一个 AppImage 的双系统实际验收。

`actor.py.txt` 和 `qmp-key.py.txt` 保留自有控件及虚拟按键程序；QMP 只在焦点检查通过后使用。客机中的测试配置及 Chrome 复制品均位于该临时写层。
