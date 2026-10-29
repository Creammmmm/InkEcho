# 602 Ubuntu 24 Wayland 会话中的 GNOME Terminal 输入

2026-10-29，Ubuntu 24.04.5 / GNOME Shell 46，active Wayland 会话的独立 QEMU 快照；系统盘、基础盘、seed 只读，容器无外网且不挂密钥，宿主仅使用客机专用 SSH 测试密钥。客机预装真实 `/usr/bin/gnome-terminal` 3.52.0-1ubuntu2（见 `inventory.log`），没有复制宿主终端或配置；未独立确认终端服务器使用原生 Wayland 还是 XWayland，因此只称其运行在 Wayland 桌面会话。测试只在快照内启动临时 Fcitx 和应用桥，不切换输入法引擎，不使用剪贴板或个人内容。

AppImage SHA-256 `602dab02b4837bb8d30c864dbe50d0413d58d53afb53d9695c7f96f50cdfb756`，包内源码未覆盖；Session 和输入路由使用包内代码，录音与识别为替身。真实 GNOME Terminal 每次启动自建 Python 子进程，只以原始模式逐字节读取固定合成输入“风云日月山川河海”重复 25 次并记录，不执行 shell 命令。测试 sender 对每次桥 Commit 响应人工等待 25 毫秒，便于触发受控切换与取消，不能当成正常输入性能。

`terminal.log` 三次测试的 sender 均 exit 0：

* 正常：自建子进程实际读取 200 字，逐字与原文一致，outcome succeeded。
* 取消：检测到第一个字“风”后发送 SIGUSR1；发送时和结束时均只有该字，日志顺序为首次 Commit、取消处理和 cancelled，取消处理后未记录新 Commit。信号不等于物理 Esc，不证明任意在途请求可撤回。
* 切焦：首字到达后暂停 sender，启动第二个真实终端窗口，等该窗口中的字节读取器准备好并等待 2 秒后恢复；A、B 分别收到 1 和 199 字，拼接准确，outcome succeeded。没有在发送前独立核对第二窗口焦点，B 的实际接收可证明这次部分文字进入 B；不能推广到无暂停切焦及所有竞态。

受控 25ms 等待、固定内容与一轮样本只证明上述有限场景；未覆盖 Chrome、其他终端或实际 shell、真实麦克风与云端、物理快捷键、IBus、其它系统以及完整包验收。Fcitx 状态 1 是桥提交状态，不是任意应用消费回执；此实验以受控子进程记录的字节为接收证据。

复现仅限一次性隔离客机：把本目录 `run.sh.txt`、`sender.py.txt`、`terminal_driver.py.txt`、`reader.py.txt` 去后缀复制到 `/tmp/inkecho-r4-test/probes/`，同哈希包放父目录，在 active Wayland 会话执行 `bash probes/run.sh <SHA> wayland`；该脚本临时启动并安装 Fcitx 桥，不能在用户真实桌面运行。测试脚本按 pid 结束自建读取子进程，客机 `sudo poweroff`，容器 `docker wait=0`、ExitCode 0、OOMKilled false，容器已删除；快照内设置未逐项恢复。`shutdown.log` 中 pgrep 行匹配到的是自身查询 shell，不作为终端后端证据；其版本查询字段为空，版本以 `inventory.log` 为准。没有截图。

SHA-256：`terminal.log` `5734c5c4d0a7497ebe7803af3f3905aa0e8fe141876c94c8d73f06300b3272e4`；`inventory.log` `356e6d522a1e6fb040165556317664bcec574d5a39e927f8fa8aaf45b1d2c885`；`sender.py.txt` `504ec2b4752997ceedcd46d8fb3082d0ef020b6bdb5265dfa70df7bd868118fc`；`terminal_driver.py.txt` `7df4c1185f6fac2d95ebab65293aa523635c0163bc9035302e6f70ff0b58e3f1`；`reader.py.txt` `d24e6bb8cd1b1fa46b1564b9c31c8f730e22d93d9315c2586cd9ebd6bf03cb25`。
