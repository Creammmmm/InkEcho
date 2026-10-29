# r4 Ubuntu 24.04 Xorg 实际包：Fcitx、回退与 owner 切换

在独立 Ubuntu 24.04 Xorg 桌面核对并解包同一 r4 候选 AppImage，SHA-256
`852a9e53efd66c7a19806e2473726d1ae5cdae5306804992fbf7d925eb583a48`；
包内 `fcitx5.py` SHA-256
`ec6fa4434a31ebd94222777d4f63d9755952d08acb2c46ab4b92b8e5799322f9`。
使用包内 Session、真实 Fcitx 桥和自有私有 Fcitx 服务、真实 X11 键盘，
目标为测试进程自建 GTK3 TextView；转写和音频为固定合成结果，不使用
剪贴板、云服务、真实凭据或用户桌面。测试包装器只记录真实调用，同时
在 owner 场景按下述方式人为切换隔离服务名。

首轮七项功能样本均输出 passed：

- 自动 Fcitx：200 字精确；取消时目标保留已发送 1 字。
- 显式 Fcitx：200 字精确；取消时目标保留已发送 1 字。
- 自动零前缀回退：真实 Fcitx 首先返回状态 3，`no_target`、accepted=0、
  offset=0、uncertain=false，随后使用真实键盘；完整 200 字准确，
  自然切窗 A/B 为 1/199 并精确拼接；取消时保留已发送 1 字。

首轮额外的 owner 场景**未通过预期校验**：测试包装器结束隔离 Fcitx 并
尝试替代服务名后，错误地对 `RequestNameReply` 枚举调用 `int()`，产生
`TypeError`；产品将包装器异常按 `delivery_unknown` 处理，目标得到已
确认提交的 1 字，未切键盘、未重放。该样本不是自然 D-Bus 回复丢失的
验证，原始失败未覆盖。受控独立重试使用不同合成文本和修正后的枚举
读取：真实 Fcitx 第一字符返回状态 1 后，将原服务关闭，由新的独立
测试 D-Bus 连接取得同一服务名（`PRIMARY_OWNER`）；r4 报
`owner_changed`、accepted=1，任务失败，目标保持 1 字、无键盘回退和
自动重放。重试样本 passed。替代连接只是占名的测试服务，旧 Fcitx
已经退出；这不证明旧服务仍存活时的并发替换、检查与提交之间的所有
竞态或真实投递不确定时的所有行为。取消无法撤回已发送字符。

首轮完整日志 SHA-256
`3e64397dd69869e7576e36227a5dc15e3a42b915f7cb8ab1a2438f8cd0c8b726`；
owner 独立重试日志 SHA-256
`b18e9161094dd0adfd3b7f933376fe97aaca64ab3a6bdc3b456d7cf755ece277`。
原始脚本、日志与 Fcitx 服务日志分别保存在 `initial/`、`owner-r2/`，
代码文件附加 `.txt` 后缀。每例为新窗口和新任务；失败后没有重放不确定
文本。仅 stdout 的 runner 退出 0 不代表每个子场景均通过。

仅在隔离 Ubuntu 24 Xorg 复现：将对应目录脚本去掉 `.txt` 放入
`/tmp/inkecho-r4-test/probes/`（重试使用 `/tmp/inkecho-r4-owner-r2/probes/`），
同一候选包放在其父目录，运行 `bash probes/run.sh <上述包 SHA> x11`。
脚本读取本测试会话 Xauthority，不记录其内容；只控制私有 Fcitx 及自有
目标。测试后私有服务和 owner 退出、IBus 会话环境恢复、临时文件删除，
虚拟机正常关机并验证容器退出 0，见 `r4-ubuntu24-cleanup.log`。该定向
实验不构成完整双系统包验收，也不证明 Wayland 或真实语音输入行为。
