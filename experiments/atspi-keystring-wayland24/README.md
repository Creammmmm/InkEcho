# Ubuntu 24 GNOME Wayland 的 AT-SPI KEY_STRING 探针

2026-10-29，Ubuntu 24.04.5 / GNOME Shell 46.0，active Wayland 独立 QEMU 快照；系统盘、基础盘和 seed 只读，容器无外网、不挂密钥，仅宿主使用专用客机 SSH 密钥。仅在快照启用 Wayland，不切换输入法、不访问剪贴板或个人正文。当前 IBus 引擎测试前后均为 `xkb:us::eng`，`xkb-options` 均为 `@as []`，不代表测试了 libpinyin 或其他非 XKB 引擎。

`run.sh.txt` 依次在 `GDK_BACKEND=wayland` 的自建 GTK3 Entry 和 `GDK_BACKEND=x11` 的自建 XWayland GTK3 Entry 中分别测试 ASCII `b` 与固定中文 `甲乙`，每次先确认该窗口活动且 Entry 有焦点；单独的 Python worker 调 `Atspi.generate_keyboard_event(0, text, Atspi.KeySynthType.STRING)`。所有四次调用均返回 `true`、worker 退出 0，但目标 Entry 实际内容均为空；故 API 调用成功不等于文字送达。只覆盖两种固定字符串和两个自建控件，未覆盖浏览器、终端、选区、取消或切焦，不能推断所有应用或解释未送达原因。

首轮 `probe.log` 使用 `target-sync.py.txt`，等待 worker 时目标 GTK 主循环阻塞；第二轮 `probe-async.log` 使用 `target-async.py.txt`，以定时器轮询 worker，目标主循环持续运行，结果仍相同。两份输出字节相同且均保留；第二轮用于排除首轮观察中的主循环阻塞这一明显疑点，但仍非所有时序的证明。客机实际第二轮 target 和 worker 哈希由 `shutdown.log` 记录；AT-SPI 软件包版本查询输出为空，不能据此声明具体库版本。

每轮前、中、后经 XWayland display 的 `xkbcomp -xkb` 导出映射 SHA-256 均为 `8d6e352a7deb3fbd480e850ef5483374ea557ce0054caa6b0862988dedea983d`，原始 `before.xkb`、`middle.xkb`、`after.xkb` 与 warning 保留；文件由第二轮覆盖，第一轮日志记录相同哈希。XWayland 导出不证明原生 Wayland 其他内部状态未变化，不排除短暂映射变化，也未监测物理按键并发。

隔离复现：将本目录 `worker.py.txt` 和所需 `target-sync.py.txt` 或 `target-async.py.txt` 去后缀复制到 `/tmp/inkecho-atspi-test/worker.py` 与 `target.py`，仅在一次性 GNOME Wayland 快照、正确 D-Bus/显示环境及可写独立输出目录运行 `run.sh.txt`（去后缀）。实验会合成按键、创建窗口，不能在真实桌面运行。客机 sudo poweroff 后 docker wait=0、ExitCode=0、OOMKilled=false，容器已删除；未逐项恢复快照。无截图。此结果不构成产品支持或包验收。

SHA-256：`probe.log` 与 `probe-async.log` 均 `3364dadca7c0f1795335ad75ca5cc3b4edfee8ccc6ec61c6f85ac770427446b2`；`target-sync.py.txt` `c7d18c273cb350879a2a4bd5aba3da0ccf25d49469cd9d6294c02a0bfa01cf`；`target-async.py.txt` `2b8e1c79745b02e14072ff90c3d1ea7991168b18a4af0e5375f3069ea8549525`；`worker.py.txt` `c586677f63feccdf2e7da48b2abd6f8c6daa7c990bbea65b9ff6a3e0eaeadcae`；`run.sh.txt` `3b9553c1540817fca04d5f4652a01e632dd31bcde15bc89b4c966c8c9f5499de`。
