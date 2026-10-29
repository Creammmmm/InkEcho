# GNOME 46 原生 Wayland：临时 XKB option 运行时实验

这是一次隔离的阶段 0 探针，不是 InkEcho 产品能力或包验收。Ubuntu 24.04.5 虚拟机 GNOME Shell 46.0 原生 Wayland，输入源为 `xkb/us`。QEMU 使用只读基础镜像和 `-snapshot` 临时写层，容器 `--network none`，没有挂载宿主桌面会话或用户配置，没有使用剪贴板。客机最初网络等待约 120 秒后超时并继续启动；首次启动误将 KVM 设备组遗漏导致容器立即退出，补上原测试容器的设备组后启动成功。首次自动登录为 X11，仅在快照内改为 Wayland，启动后 `loginctl` 报告 `Type=wayland`。首次启用扩展的参数引用错误，未执行输入，改用 `enable.py.txt` 成功。

## 实验与结果

在快照的 `~/.config/xkb` 放置前一离线探针 [xkb-shell-probe](../xkb-shell-probe/) 的临时规则和符号，注册仅用于实验的 Shell 扩展。扩展把 Shell 的 `_currentKeymap` 参数保存，再调用 `global.backend.set_keymap` 附加 `inkecho:test`。普通调用不证明目标应用收到字符，因此使用有焦点的自建 GTK3 Wayland 输入框检查文本。扩展使用 Shell 的虚拟键盘发送固定的 Linux 按键码 124，不接触物理用户输入。

- `target-restart.log`：原参数 `layouts=us,us`、`variants=,`、`options=''`、`model=pc105+inet`。附加 option 后按键实际产生 `甲`；用旧参数恢复后再次按相同键，内容仍为 `甲`。它只证明这个输入框和这个键的实验结果。第一次 `target.log` GTK 版本选择错误，`target-gtk3.log`、`target-reload.log` 的虚拟键盘调用使用了不存在的方法；其中 Apply 与 Restore 成功，但没有按键发出。修正后重启 GNOME 会话才加载新的 JS 模块并获得上述结果。`extension-r1.js` 是实际成功使用的源码，`target.py.txt` 是修正后的脚本。
- `conflict.log`：使用 `extension-r2.js`，在映射启用期间依次发送模拟普通键 `a` 和测试键，输入框为 `a甲`。这并非人手真实并发按键测试。随后在快照中把 `xkb-options` 改为 `caps:escape`，固定模拟 Caps 键到达 GTK 时确为 Escape；按旧参数恢复后同一键又变为 Caps_Lock，而 GSettings 仍显示 `['caps:escape']`。旧参数恢复会覆盖并发更新，导致实际键盘状态与设置不一致，**不能直接用于产品**。
- `keymap-capture.log`：清空测试选项后，以 `xkbcomp` 导出 XWayland 当前完整键盘映射。前后 SHA-256 均为 `8d6e352a7deb3fbd480e850ef5483374ea557ce0054caa6b0862988dedea983d`，应用期间为 `6b926167287c9e4d632725adb1cffaedab033ac6d348438d4416716ffbc5d1f3`。三个原始输出保存在本目录。该比较是 XWayland 导出，不能证明原生 Wayland 客户端看到的完整映射一致，也不覆盖其他布局。

测试客户端每次 `gdbus call` 返回后即退出；成功输入表明扩展在调用者退出后仍保留映射，不能把客户端退出视作自动恢复。没有模拟扩展崩溃、Shell 崩溃或断电，也没有验证可靠的崩溃恢复。

## 可复现范围

仅在隔离快照操作：先检查当前输入源、会话和原有规则；新建临时 XKB 规则（不要覆盖实际用户已有同名规则），安装此目录的 `metadata.json` 和相应版本 `extension.js`，启用扩展，必要时重启隔离 GNOME 会话。运行修正后的 `target.py.txt`、`conflict.py.txt` 和 `keymap-capture.sh`，使用客机会话的 `XDG_RUNTIME_DIR`、D-Bus、`WAYLAND_DISPLAY` 和适当 `DISPLAY`/`XAUTHORITY`。这些脚本只适合隔离实验，未实现安全锁、授权或通用恢复。复制 `.py.txt` 去掉后缀供执行；此复制操作未另行独立复跑。

清理记录 `cleanup.log` 显示扩展停用且服务名无 owner、测试 options 清空、输入源为 `xkb/us`；快照内测试扩展及临时 XKB 目录被删除。QMP 请求关机，容器退出码 0 后删除；基础镜像只读。只证明所列清理观察，不声称所有客机设置逐字还原。网络等待原因尚未诊断。

## 未验证与禁止外推

没有比较原生 Wayland 完整映射，未覆盖已有自定义规则/选项合并、不同输入源及布局、真实物理按键并发、用户焦点切换、取消、按键释放顺序、任务替代、客户端和 Shell 异常退出、竞争写入、扩展授权安全、浏览器/终端、AppImage 或 Ubuntu 26.04。全局映射会影响整个 seat；`set_keymap` 调用成功也不表示其他应用已处理。当前不能自动启用此方案，不能宣称 Ubuntu 24.04 原生 Wayland 回退已解决。
