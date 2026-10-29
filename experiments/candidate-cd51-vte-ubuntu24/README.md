# cd51 候选包 Ubuntu 24 Wayland 自建 VTE 复测

2026-10-29，在 Ubuntu 24.04.5 / GNOME 46.0 原生 Wayland active 会话，运行 AppImage SHA-256 `cd510bade9fbb01e4f321fa33785df9c9f4d0627a1336db9e430f2d51073d1a8`。独立 QEMU 快照，系统盘、基础盘和 seed 只读，容器无外网且不挂密钥，仅宿主使用客机专用 SSH 密钥。只在快照内启用 Wayland，临时 Fcitx 配置与应用输入桥，不切换系统输入法引擎。目标是自建 GTK3 VTE 控件，子进程只读取原始输入字节、不执行命令。输出固定合成文本“风云日月山川河海”重复 25 次，不使用剪贴板、不读取个人正文。候选包代码未被覆盖；录音与识别是替身。

* `normal-switch.log` 中正常样本实收 200 字且完全相等，发送进程 exit 0，桥报告 200 次状态 1、succeeded。该文件的首次切焦样本虽然观察到切焦请求和第二窗口获焦，收到 200+0 字；发送结束太快，未证明输出期间的切换，保留为无效切焦对照。
* `switch-controlled.log` 使用测试脚本对每个桥提交回复追加 25 毫秒等待，收到首字后暂停发送进程，确认第二窗口及控件已获焦再恢复。A、B 分别实收 1 和 199 字，拼接精确等于 200 字，发送进程 exit 0，桥报告 200 次状态 1、succeeded。该样本是人为限速且受控暂停，不证明自然时序或切换瞬间无丢字。
* `cancel.log` 使用相同 25 毫秒测试侧延时，在首字被接收后通过 SIGUSR1 请求取消。发信号时和最终均只收到“风”，为原文本前缀；事件顺序为一次 Commit 开始、状态 1、取消处理、finished cancelled，取消处理后没有新的 Commit 调用记录。发送进程 exit 0；终态后发送端约等待 1.2 秒，驱动再等待 1 秒读最终内容。该样本不证明物理 Esc、可撤回在途请求或任意取消时序。

三个脚本目录是实际测试输入，文件保留 `.txt` 后缀。自建 VTE、合成结果与测试侧猴子补丁不代表真实终端、物理快捷键、真实麦克风或云端识别，也不构成完整 Ubuntu 24/26 软件包验收。Fcitx 状态 1 只是桥提交状态，实际文字来自自建原始接收端记录，不能推广为所有程序的消费确认。

在一次性隔离客机复现：准备同哈希 AppImage，分别把 `probes/`、`switch-controlled/` 和 `cancel-probes/` 中脚本去 `.txt` 后缀放到 `/tmp/inkecho-r4-test/probes/`，每次执行 `bash probes/vte-run.sh <SHA> wayland`。脚本会在测试快照中启动临时 Fcitx 并安装桥，不应在真实用户桌面运行；人为延时和焦点暂停仅用于受控样本。`shutdown.log` 记录环境；隔离客机执行 poweroff 后容器 `docker wait=0`、`ExitCode=0 OOMKilled=false` 并已移除，快照内未逐项恢复。没有截图。

SHA-256：`normal-switch.log` `4cc24ca6421e72628d8a1bd9904d47f75868a4202d94549a6326525d9c12afac`；`switch-controlled.log` `c55eb098214ed38e69e373bdf590aaf0d55b2e6294fd58a0c38a3da152c1bb8f`；`cancel.log` `6046a4a77e88fd2353851dfc6be438ad8ee661b5af24d100c1fd25855632317d`。
