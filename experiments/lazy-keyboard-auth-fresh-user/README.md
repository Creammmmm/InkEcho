# 全新用户首次授权探测（未触发或确认提示）

隔离 Ubuntu 26.04 QEMU 临时快照以 `-snapshot` 启动，原有 qcow2 与其基础镜像、seed 均只读挂载；在临时副本中创建无历史用户 `authprobe`，通过 GDM 自动登录该用户。检查该 session 为 active Wayland，用户 ID 1001。原始虚拟机镜像与账户配置未作为可写挂载。首两次快照启动分别因基础镜像挂载路径、KVM 组权限失败；修正后启动并完成探测。

测试 r4 包 SHA-256 `852a9e53efd66c7a19806e2473726d1ae5cdae5306804992fbf7d925eb583a48`，解包覆盖 `app.py` SHA-256 `69cad54fee6b70bef05a5110289133aa819a33ebb4f0ba35d10f1d784fbf8600`、`platform/output_router.py` SHA-256 `e3f8e993566d996eabc43345f94956af821dec0ae071a8d632bbd62c36ff61e0`。使用自建 GTK 文本框、私有固定合成文本，系统输入检测被探针固定为无框架，测试 auto 选择键盘，不是 Fcitx 自动选择，也不是最终包验收。

原始日志 `first-user.log` SHA-256 `9233afdf4fd811bd9063cc49af8e24fdff7ec63a988d06e10cd88a682e98328b`。cancel、timeout、normal 的授权函数耗时分别约 24ms、3ms、4ms：cancel 在调用开始 50ms 后取消，授权已返回，目标先收到“甲”后报告 input_cancelled；timeout 指定 100ms 任务期限，目标未收到文字并报告 input_cancelled，授权已返回；normal 收到“甲乙”。目标在各次结束时报告 active/focused，不能证明过程中的焦点状态。

虽然该用户为新建用户，探针没有持续观察 GNOME UI，没有触发或确认实际授权弹窗；因授权返回过快，取消与任务期限均未发生在授权等待中。故首次系统授权弹窗、弹窗期间取消/超时、过程中的切焦与远端会话完整清理均未验证。本次仅检查无独立 wayland_worker 进程，不可扩大为没有任何远程会话资源残留。

脚本与前一轮相同，位于 `../lazy-keyboard-auth-prompt/`；本轮原始日志位于本目录；`sender.py`、`target.py` SHA-256 分别为 `170df88b25e625632e6105bbb308ba46e192f79117f4a173162962e0ad9ff744`、`39ed956f29a19c674f9bf59602e7dec7fe35f85ee8d7dce722c058a2195cf6ef`，与前一轮实验相同。客机关机退出码 0，快照容器已删除。该临时账号和桌面变更仅存在已销毁的临时快照。
