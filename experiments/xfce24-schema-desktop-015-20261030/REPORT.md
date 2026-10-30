# Ubuntu 24.04 XFCE Xorg：Fcitx 缺 schema 候选桌面实测

2026-10-30，隔离 Ubuntu 24.04.5 / XFCE4.18 / 实际 Xorg，Fcitx5.1.7；loginctl、会话管理器环境和 Xorg 进程共同确认。原客机未安装 XFCE：先从其 APT 包索引取得 23 个 Ubuntu 官方依赖的 SHA-256，在宿主下载并逐项核验，仅安装到隔离客机，未修改宿主。第一轮直接指定本地 deb 的 `--no-download` 安装被 APT 拒绝，改放客机 APT 缓存后成功；失败记录保留。XFCE 包仍存在于本次隔离停止快照，不声称卸载，但原 Ubuntu Xorg 登录会话已恢复，父镜像未改。

正式 v0.15.0 AppImage SHA-256 `94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a` 只读挂载。测试为隔离运行目录的**单文件源码覆盖**：候选 `framework_detection.py` SHA-256 `f1e78deb2cdcefe3c21dd14b7ea266e2d63c7b39ee3415488dd0a498b19ddba1`，与当前修复源码一致；原包该文件 SHA-256 `119ebfaee65ce6a8b04e3652f9712c7916e57e73c64a37e3b59ac5844555033d`。包内 InkEcho 常规文件逐项比较，仅此文件有变化；其他依赖指向原包。结果是候选源码验证，不能作为未修改 AppImage 验收。使用合成音频及本地模拟 TLS ASR/润色，不代表真实麦克风或云端；不使用剪贴板。

独立编译 schema 目录仅供候选和基线进程使用：`gsettings list-schemas` 成功且非空，仅列自有 fixture schema，确实不含 GNOME 输入源；读取 GNOME 输入源失败。测试启用私有 Fcitx 并将会话管理器 hints 设为 Fcitx；检测按产品代码核验系统 owner 与插件状态。原包 `collect_system_framework`、`detect_system_framework` 均返回 None，候选均返回认证的 fcitx owner。额外独立 schema 清单包含 GNOME 输入源 ID 但缺 `sources` 键时，读取失败且候选检测均返回 None；该案例不代表实际查询超时。

候选真实完整 Session 的 auto 选择 fcitx，录音期间切至自有新 GTK X11 控件后准确收到 22 码点，旧控件为空。部分取消在收到首字时触发，最终接收 2 字，第二字可能为取消竞态中已发送或晚到前缀；进程退出后 1.3 秒内容无追加。真实虚拟硬件按键形成 `ni` 两字符拼音预编辑时，独立 router 返回 `fcitx_composition_active`、attempts0，已有文字和预编辑不变，随后空格上屏“你”。该拼音保护是独立 router 测试，并非活动预编辑期间的完整 Session。

原始包索引、23 个软件包 SHA-256 清单、安装日志、命令、schema 证明、两版检测结果、真实按键保护、目标内容、Session 结果和恢复记录均在 `raw-byte-archive.json`，逐项附解码后大小与 SHA-256。所下载 deb 和客机快照为外部保留文件，不在补丁中；快照路径及 SHA 见 `external-retained-pins.json`。测试结束 Fcitx、测试进程、能力文件、包挂载和指定按键残留检查通过，hints 与 Ubuntu Xorg 登录会话恢复；QEMU/Docker 退出0、无 OOM，停止快照全流解码核验。

未验证 schema 读取实际超时、任意应用、实际物理设备或真实云端；原生 IBus/XWayland 跨后端问题不受本测试改变。不能将此候选结果作为当前新包双系统实包验收。
