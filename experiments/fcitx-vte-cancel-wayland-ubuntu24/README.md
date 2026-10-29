# Ubuntu 24.04 Wayland Fcitx / VTE：受控取消

2026-10-29，独立 Ubuntu 24.04.5 GNOME Wayland QEMU 快照，会话 active；基础盘、系统盘及 seed 只读，容器无外网且不挂载密钥。宿主只用该客机专用测试 SSH 密钥。仅快照内切换到 Wayland，创建私有临时 Fcitx 配置和桥，不更换系统输入法引擎，不使用剪贴板或读取用户正文。候选包 SHA-256 `207b97eb667e5439137b51963a2aa09515c7ba50a83496d9c10070e989252685`，合成识别文本为“风云日月山川河海”重复 25 次。

为使取消信号在输出中到达，`sender.py.txt` 对探针拦截的 Fcitx Commit 回复增加 25 毫秒等待，并记录调用和取消处理事件；这是实验桩，不是产品发送速度或自然网络时序。`vte_driver.py.txt` 在自建 GTK3 VTE 内原始字节读取器收到首字后立即发送 SIGUSR1，并记录发信号时与最终内容；子进程不执行 shell。实际调用候选包的 Session 和 Fcitx 路由，录音和识别使用替身。

`cancel.log` 的单次样本显示：信号发出时为“风”，最终仍为“风”，是原始 200 字的前缀；发送进程退出码 0、outcome `cancelled`。记录顺序是 Fcitx `commit_started`、状态 1、`cancel_handler`、`finished cancelled`，取消处理后无新的 Commit 调用记录。发送进程在终态后等待约 1.2 秒，测试驱动在进程退出后又等待约 1 秒再读内容。脚本总退出码 0。此样本证明受控条件下未观察到后续输入；不能证明取消可撤回在途请求、所有焦点与延时条件安全、任何真实应用都可取消，亦不等同物理 Esc 测试。

本轮会话和系统版本写入 `shutdown.log`；使用 `sudo poweroff` 后容器 `docker wait` 为 0，inspect 报告 ExitCode 0、OOMKilled false，测试容器已删除。快照内未逐项恢复，原镜像只读。日志仅包含固定合成文字与隔离测试路径；没有截图。

仅在一次性隔离客机复现：按 `experiments/fcitx-vte-wayland-ubuntu24/README.md` 准备同哈希候选包和 GTK3 VTE，将此目录四个 `.txt` 脚本去后缀复制至 `/tmp/inkecho-r4-test/probes/`，然后执行 `bash probes/vte-run.sh <SHA> wayland`；此脚本仅执行 cancel 模式，会启动私有 Fcitx 并安装桥，不应在真实用户桌面使用。相对先前正常测试额外引入的可控延时和事件记录不得当成产品变更。非真实麦克风、云端识别、浏览器、实际终端应用或最终包验收。

SHA-256：`cancel.log` `b96dc6d13ed8c11b1e61274a60cfea1e7a6a9445fe6ae3685754365b76e8072b`；`sender.py.txt` `504ec2b4752997ceedcd46d8fb3082d0ef020b6bdb5265dfa70df7bd868118fc`；`vte_driver.py.txt` `5ac02dde67f9d05c1ed6062b26fabe0702d834e57ff749e3b40015e3dd80142f`。
