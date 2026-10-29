# r4 Ubuntu 24 GNOME Wayland 定向验证

在隔离 Ubuntu 24.04 GNOME Wayland 会话，核对同一 r4 候选 AppImage
SHA-256 `852a9e53efd66c7a19806e2473726d1ae5cdae5306804992fbf7d925eb583a48`，
使用其解包 Session、真实 Fcitx 桥与私有 Fcitx 服务，自建 GTK3 原生
Wayland 控件、固定合成音频和转写。没有使用剪贴板、网络识别、真实用户
数据或用户桌面。测试包装器记录真实调用，并在 owner 样本中人为更换
隔离 D-Bus 服务名所有者，不改变包内源码。

| 模式 | 场景 | 实际结果 |
|---|---|---|
| 自动 Fcitx | 200 字 | 精确通过 |
| 自动 Fcitx | 自然切窗 | A/B 64/136，拼接精确 |
| 自动 Fcitx | 取消 | 目标保留 1 字已发送前缀 |
| 显式 Fcitx | 200 字 | 精确通过 |
| 显式 Fcitx | 自然切窗 | A/B 29/171，拼接精确 |
| 显式 Fcitx | 取消 | 目标保留 1 字已发送前缀 |
| 自动，GTK simple | 完整、切窗、取消 | 三例真实 Fcitx `no_target`、accepted=0、offset=0、uncertain=false 后，键盘能力报告 GNOME 46 缺 Unicode 映射；任务失败、零字符，切窗/取消没有实际覆盖 |
| 自动 Fcitx | 服务所有者变化 | 首字符 Commit 成功后，关闭真实私有 Fcitx，再由独立测试 D-Bus 连接占有该服务名；`owner_changed` accepted=1，目标仅 1 字，无键盘回退或重放 |

自然切窗时未暂停发送协程；取消无法撤回已发送字符。owner 替代者只是
占名测试连接，旧服务已退出；该样本不证明旧服务仍存活期间的变更、
所有并发竞态或真实不确定回复。三项键盘回退不支持必须计为失败，不得
将脚本总退出码 0 解释为全部通过。

原始 `r4-ubuntu24-wayland.log` SHA-256
`9592cebce1ad3d77b633271dbfcf17cdd3536e45bb726b1c2e7d68dd2f294c6b`；
脚本、Fcitx 日志和清理记录同目录，代码文件后缀为 `.txt`。仅在隔离
Wayland 虚拟机复现：将脚本去掉 `.txt` 放在
`/tmp/inkecho-r4-wayland/probes/`，同一候选包放父目录，执行
`bash probes/run.sh <上述包 SHA> wayland`。脚本使用私人 Fcitx 配置并
恢复输入法会话变量。实验后无 Fcitx 进程或 owner，私有目录删除；原
GDM/账户文件由持久备份恢复并逐项比较，虚拟机正常关机，容器退出 0。
此为定向提取包实验，不是完整双系统验收、FUSE 启动或真实语音验证。
