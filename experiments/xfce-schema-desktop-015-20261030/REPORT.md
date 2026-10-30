# XFCE Xorg Fcitx 缺 schema 候选：隔离桌面实测

2026-10-30，隔离 Ubuntu 26.04.1 / XFCE4.20 / 实际 Xorg，Fcitx5.1.19；`loginctl`、会话管理器环境和 Xorg 进程共同确认会话。正式 v0.15.0 AppImage SHA-256 `94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a` 以 FUSE 只读挂载。候选是独立运行目录中的单文件源码覆盖，`framework_detection.py` SHA-256 `f1e78deb2cdcefe3c21dd14b7ea266e2d63c7b39ee3415488dd0a498b19ddba1`；原包该文件 SHA-256 `119ebfaee65ce6a8b04e3652f9712c7916e57e73c64a37e3b59ac5844555033d`。对包内 InkEcho 常规文件逐项比较，只有该文件变化；其他依赖指向原包。结果属于候选源码覆盖测试，**不是未修改 AppImage 验收**。合成音频和本地模拟 TLS ASR/润色，未使用剪贴板。

在隔离客机创建独立编译 schema 目录，仅设置给候选与对照进程：`gsettings list-schemas` 真实成功且非空，仅列出自有 fixture schema，不含 `org.gnome.desktop.input-sources`；直接读取该 GNOME schema 失败。会话管理器的实际桌面为 XFCE、类型 x11；测试启动私有 Fcitx 并设置会话的 Fcitx hints，执行后逐项恢复。比较相同环境中原包与候选的实际 `collect_system_framework` 和 `detect_system_framework`：原包均为 None，候选均为经系统 owner/插件检查的 fcitx owner。另设有效 schema 清单包含 GNOME 输入源 ID 但缺 `sources` 键，读取失败且候选两个检测均返回 None；这不是超时测试。

候选实际 `DefaultAutoOutputRouter` 选 fcitx。真实 Session 在录音期间切到自有新 GTK X11 控件，正常样本 22 码点完整、旧控件为空；部分取消在接收首字时触发，最终收到前 2 字，第二字可能是在途竞态。进程退出后观察 1.3 秒无追加。真实虚拟硬件按键建立 `ni` 两字符拼音预编辑时，独立 router 返回 `fcitx_composition_active`、attempts0，已有文字及预编辑不变，后续空格上屏“你”；这项预编辑保护是 router 测试，不是活动预编辑期间的完整 Session。

首轮完整 Session 的目标文本实际准确且选 fcitx，但系统音频初始化使默认设备从占位值变为 `auto_null`，fixture 的默认设备不变断言失败，故整轮不计通过；设备稳定后独立第二轮正常和取消通过，首轮原始数据保留。未测试实际 schema 查询超时、Ubuntu24 XFCE、其他应用、真实物理设备或云端；不扩大为全平台已支持。

原始命令、schema 证明、候选与旧版哈希及真实选择、系统受控按键、目标状态、Session 结果、日志和两轮失败/成功均保存在 `raw-byte-archive.json`，每项含解码后大小及 SHA-256。候选和模拟 schema 均只在客机临时目录；测试后 Fcitx 及测试进程、能力文件、挂载与按键残留检查通过，框架 hints 和原 GNOME Wayland 会话恢复；QEMU/Docker 正常退出0、无 OOM，停止快照完整流解码核验。`external-retained-pins.json` 仅记录外部快照，不代表补丁包含完整系统。
