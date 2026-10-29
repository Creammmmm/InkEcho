# Ubuntu 24.04 Wayland Fcitx 与自建 VTE 定向实验

2026-10-29，Ubuntu 24.04.5 隔离 QEMU 快照，GNOME Wayland 会话报告 active；候选 AppImage SHA-256 `207b97eb667e5439137b51963a2aa09515c7ba50a83496d9c10070e989252685`。基础盘、系统镜像和 seed 只读挂载，容器无外网、不挂载密钥；仅宿主使用专用客机 SSH 测试密钥。启动时网络等待约 125 秒。仅在快照中启用 Wayland，Fcitx 使用专用临时配置和自建输入桥，未切换输入法引擎；目标是自建 GTK3 VTE 控件，其内部子进程只读取原始字节，不运行 shell。固定合成文字为“风云日月山川河海”重复 25 次；未访问个人文本或剪贴板。

测试运行候选包中 Session 和实际 Fcitx 路由，录音及识别采用替身，不是语音端到端或包验收。

* `vte.log` 正常样本：目标实际读取 200 字，逐字等于固定文本，发送进程 exit 0，报告 200 次桥提交状态 1、succeeded。
* 同一文件的取消样本：发送 SIGUSR1 时输出已完成，最终仍为 200 字及 succeeded；不算取消通过。相应命令在随后的切焦阶段因 SSH 连接断开以 255 退出，没有切焦结果。代理套接字的 10 秒空闲超时是连接断开的可能原因；后来添加 SSH 保活后连接稳定，但没有断线根因的独立确认。
* `switch.log` 为第一次独立切焦尝试，连接中断，SSH 退出 255，未获得样本。`switch-retry.log` 与 `switch-retry2.log` 原夹具两次在发送之前均报告 `focus_a_missing`，因此没有发送切焦样本；包装脚本吞掉夹具错误而退出 0，不能算通过。
* `switch-delayed.log` 使用 `vte_fixture_delayed.py.txt` 将初始窗口激活推迟 500 毫秒，得到切焦样本。检测首字后暂停发送，确认第二个自建窗口和终端控件已聚焦后继续；窗口 A、B 分别读取 144 和 56 字，拼接精确等于 200 字固定文本。发送进程 exit 0、200 次桥提交状态 1、succeeded，外层 SSH 命令 exit 0。受控暂停和确认焦点的测试不能证明未暂停切焦、到达瞬间竞态或其他程序正确。

快照内使用 `sudo poweroff` 后容器 `docker wait` 返回 0，inspect 记录 `ExitCode=0 OOMKilled=false`，容器已删除。快照中未逐项恢复桌面配置，不影响只读原镜像。未保存截图；`shutdown.log` 显示测试会话类型及系统版本，版本字段查询输出为空，因此不据此宣称 Fcitx/VTE 具体版本。每份日志仅含固定合成内容与测试路径。

复现需一次性 Ubuntu 24.04 GNOME Wayland 会话、上述同哈希 AppImage、可用的 Fcitx5 和 GTK3 VTE；按本目录 `vte-run.sh.txt`、`vte_driver.py.txt`、`vte_fixture.py.txt`、`sender.py.txt` 复制为 `/tmp/inkecho-r4-test/probes/` 下无 `.txt` 后缀的文件，以原脚本 `bash probes/vte-run.sh <SHA> wayland` 运行，脚本仅适合隔离测试环境。延迟焦点样本使用 `vte_fixture_delayed.py.txt` 覆盖隔离客机内夹具，并将脚本中的 `for mode in full cancel switch` 改为 `for mode in switch`；SSH 测试连接需适当保活。此步骤会启动临时 Fcitx 并修改快照内 Fcitx 配置，绝不可在用户真实桌面复现。

限制：只覆盖一个自建 VTE 版本与固定合成内容，没有测试真实终端应用、浏览器、未受控切焦、有效取消、物理键、真实麦克风、云服务及其它输入法组合，不构成 24.04 通用支持或发布验收。桥状态 1 表示桥尝试提交，不是目标应用处理确认；本实验的实际内容由自建接收端独立记录。

SHA-256：`vte.log` `fa920690fe2bc7918794306ad9802ab2615b33a6972c2bb403782232b5650c68`；`switch-delayed.log` `b823ece16d159ad32a986ec38ad60ae5e5b04934de8f3e2b7a2c1a4e11e4f4b0`；`vte_fixture_delayed.py.txt` `998dfc2e572c336654eef7c366c479e6a22f0f04c987d259851778ff8bed07c5`。
