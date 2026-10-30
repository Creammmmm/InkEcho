# InkEcho 0.15.0 输入法组合补充桌面实测

2026-10-30，五台隔离客机顺序运行同一个正式 AppImage：SHA-256 `94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a`，源码提交 `76aeb33`；包内代码及扩展由包清单/来源验证，未覆盖包内代码。测试未使用剪贴板，所有文本控件均为测试自有。源自复制旧 fixture 的测试脚本有针对目标场景的修改；具体修改和执行命令均保留在归档中。

## 实测范围及结果

- Ubuntu 24.04.5/GNOME46 和 Ubuntu 26.04.1/GNOME50.1 原生 Wayland，Fcitx5 分别为 5.1.7 和 5.1.19；自有 GTK3 Entry 显示 GObject 类型 `GdkWaylandDisplay`，窗口 active、控件 focus 且系统 `im-fcitx5.so` 实际加载。手动在隔离会话安装并启用包内校验通过的 Fcitx 插件，真实 `DefaultAutoOutputRouter` 选择 fcitx，收件控件精确收到“甲乙”；第二任务首字符后取消，只追加“己”，1.2 秒后没有尾字。该样本是直接桥接输出，不是 keyboard 回退。这是独立 router 测试，未使用完整 Session、麦克风或云端；不验证拼音预编辑，不证明其他控件或长文本。
- Ubuntu 24.04.5/GNOME46 **实际 Xorg**：包内旧 IBus V2 扩展在隔离桌面手动安装并启用，真实 Session 使用显式 `ibus`，自有 GTK X11 控件完整接收 24 码点，包含中英文、重音、希腊、emoji、换行；取消触发时接收端已有 1 码点，最终接收 2 码点；第二码点是竞态中已发送或晚到的前缀，进程退出后的 1.3 秒观察窗口无追加文字。焦点在输出前切换到另一个自有窗口，旧窗口为空。使用合成音源、本地模拟转写/润色，不代表实麦克风或云端。此项是手动旧 V2，未验证 24 Xorg 自动选 IBus。
- Ubuntu 24 GNOME46 Xorg，另一独立客机中 IBus 会话提示且未启用 InkEcho IBus 桥，auto 的真实 Session 实际选择 keyboard，混合 22 码点完整输入；取消样本接收 1 字，进程退出后的 1.3 秒无追加。该结果是键盘回退，不能当成自动 IBus 正向。
- Ubuntu 26.04.1/**XFCE Xorg**（非 GNOME Xorg），IBus 会话提示，包中未安装可用 GNOME IBus 扩展。auto 的真实 Session 选 keyboard，混合 22 码点正常输出，取消仅接收 1 字且无迟发。手动 `ibus` 测试得到 `ibus_unavailable`、0 字且无迟发，因此该组合的 IBus 正向没有通过。自动 keyboard 回退不能称作 IBus 正向支持。

## 失败、恢复和证据

26 原生 Fcitx 第二次试验使用系统缺失的 GdkWayland introspection typelib，目标程序退出，未产生文字；第三次改为 GObject 真实类型名断言后通过。24 Xorg 旧 IBus 第一次 fixture 用键盘样本对照 IBus 专用样本，少算 emoji 导致误判失败；保留原记录，修正独立对照脚本后重跑通过。26 Xorg auto 首次测试音频系统启动时默认设备从占位名变为 auto_null，收件文字正确但默认设备不变断言失败；待稳定后重跑通过。26 Xorg 恢复会话后初次写上下文因目录缺失失败，补建目录并再次核验恢复后正常关机。上述失败均未改生产程序或隐藏。

各次测试恢复输入法框架环境提示、禁用并移除测试扩展、清理包挂载与测试输入法进程；Xorg26 恢复原 GNOME Wayland 会话。残留资源检查、实际运行日志、结果、包审计和五台客机 Docker 状态均随原始记录保存，均正常退出 0、无 OOM。每台独立停止快照的完整解码校验值保存在原始归档，外部快照保留路径和 SHA 见 `external-retained-pins.json`，不等于本补丁包含完整虚拟机。`raw-byte-archive.json` 对每项记录原始大小与 SHA-256，内容 gzip/base64 编码，可解码复核；目录中保留执行脚本、命令和失败结果。

24 Xorg auto 在启用旧 V2 桥时的选择、26 GNOME Xorg IBus、Wayland 其他 Fcitx 应用、物理快捷键/麦克风、真实云端、广泛 Unicode/长文本、并发和所有焦点切换仍未验证；原生 IBus 至 XWayland 中途停止的问题仍未修复。不能凭这组样本宣称完整平台组合已支持。
