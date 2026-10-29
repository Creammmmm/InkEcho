# 同 SHA ad355d 候选的会话、IBus 与安全回退增量

本记录补充[初轮实际包验收](appimage-0.10.10-candidate-validation.md)，两份报告必须一起阅读。版本仍为 **0.10.10**，冻结产品提交 `34f8ee9b643f82bb30e44d7eaa5a3e30e9c7050e`，候选 SHA-256 仍为 `ad355d622d6888b8092381988327f589f71669791cb32465c0b5e825573bcf23`，104,409,592 字节。没有重建、修改产品或稳定入口、发布、读取真实凭据或访问剪贴板。

持久候选位于 `dist/candidates/InkEcho-0.10.10-x86_64-ad355d62.AppImage`，完整客机原始输出与停止后子盘归档位于已忽略的 `dist/acceptance-ad355d62-20261030`。本补丁仅保存非敏感原始日志、测试结果、截图和夹具，不包含客机个人配置、音频 cookie、SSH 密钥或临时 TLS 私钥。

## 顺序隔离与实际会话

只读基础盘/父盘/快照、独立 RAM 写入层、网络隔离 KVM 客机，顺序运行，容器 cap-drop ALL/no-new-privileges，未借用宿主桌面。24 通过 AccountsService/GDM 从实际 GNOME Xorg 转到 `ubuntu-wayland`；26 原有 GNOME Wayland，在实际列出的 `/usr/share/xsessions/xfce.desktop` 下选择 XFCE Xorg。26 的 Xorg 结果不代表 GNOME 提供了 Xorg 会话。

| 系统/会话 | 默认自动输出实测 | 同包界面 |
|---|---|---|
| Ubuntu24.04.5 GNOME Xorg | 初轮真实 Fcitx/Pinyin 保护与 Unicode/取消通过 | 初轮 xcb 五页及生命周期通过 |
| Ubuntu24.04.5 GNOME Wayland | 正确安装并启用 V5 后自动 IBus → **原生 GTK3 Wayland**；禁用 V5 后自动 keyboard → **XWayland GTK3**，均通过本表下样本 | native Wayland 五页/IPC/cold controls/配置保护通过 |
| Ubuntu26.04.1 GNOME Wayland | 自动 IBus → 原生 GTK3；禁用 V5 后 auto keyboard → 原生 GTK3、XWayland GTK3；初轮 Fcitx → XWayland GTK3，均通过相应样本 | 初轮 native Wayland 五页及生命周期通过 |
| Ubuntu26.04.1 XFCE Xorg | auto keyboard → Xorg GTK3、真实 Fcitx 明确零发送后 keyboard 回退通过 | xcb 五页及生命周期通过，帮助实际显示 XFCE/X11 |

每个新增会话以实际同 SHA FUSE 挂载包审计，包内解释器、模块来源与版本均验证；不能用源码启动替代。实际 GUI 截图逐页查看中文字体及布局。可滚动页面的截图只证明当前可见区域，未把所有设置控件的人工交互冒充已完成。

## 输入、取消与独立接收结果

- 24、26 的原生 Wayland IBus：包内 `OwnedExtensionManager` 安装、重登、校验并显式启用 V5，默认 `Session` 未注入 inputs/router/factory。真实 Recorder 读取生成的 PulseAudio marker，本地 TLS Qwen WebSocket 和 SSE 润色后，自动路由实际选择 `ibus`。录音期间创建并切到另一个自有 GTK3 控件，旧控件不变，新控件得到完整 22 字符 `你好 InkEcho，café Ω\n第二行。`（真实换行）。正常任务按产品诚实契约为 **unconfirmed / ibus_delivery_unknown**；独立目标确实收到全文也不是端到端确认 ACK。接收窗口首次观测文字后取消，分别留下 3 字符 `你好 `，等待 1.3 秒无尾部追加。
- 显式禁用 V5 后的默认自动 keyboard：24 Wayland→XWayland、26 Wayland→XWayland、26 Wayland→原生 Wayland、26 XFCE Xorg→Xorg 均得到同样完整 22 字符及旧目标空；各取消样本留下 1 字符“你”，等待 1.3 秒无追加。部分取消的产品记账可为 0 确认字符，而目标实际有 1 字符；保留二者，不把投递变成确认或重放尾部。
- 这些 keyboard 控件各自独立监测 **22 press / 22 release**，取消 **1 / 1**，控件观测 held 集合为空。计数覆盖自有目标观察到的生成事件，不是对所有物理键或用户预先按住修饰键的保证。26 原生键盘路径没有独立收集前后完整 Mutter keymap/group/modifier 快照，不冒称本次已重新证明其全部恢复边界；结束时的 XQueryKeymap 检查属于当时实际 X 服务器。
- 24 GNOME Wayland、26 GNOME Wayland 和 XFCE Xorg 的实际 Fcitx 明确零发送回退：正式 pin addon 被系统 Fcitx 加载，普通自有 XWayland/Xorg GTK Entry 使用 simple IM，因此 Fcitx 没有可提交目标。对真实返回只做转发观测、不替换回复；两次任务分别记录 **no_target / accepted=0 / unsent_offset=0 / uncertain=false**，随后 auto keyboard 得到 15 字符 `无目标 fallback Ω。`；另一次任务第一字符后取消仅留下“甲”，1.2 秒无追加。actor/daemon 正常退出 0、临时 hints 恢复。键盘已投递但上层确认计数 0 的取消事实仍保留。
- 24 GNOME Wayland 另由独立子盘实际重复同类 Fcitx confirmed-zero→XWayland keyboard：两次真实 no_target/accepted0/offset0/uncertainfalse，完整15字与取消1字、1.2秒无追加通过；V5实测 disabled，使用同一产品桌面工厂。不是从26外推。

所有输入目标和焦点切换均为本次夹具自建控件；没有读取其他应用正文，没有产品焦点捕获或周期抢焦点。合成音频/本地固定服务是实际包协议与路由测试，不是物理麦克风、云端认证或模型准确率验收。

## 原始失败与范围保留

1. 24 新子客机有既有约 125 秒 networkd wait-online 启动延迟，SSH 超时/拒绝前没有发送文本。原始 receipts 保留。
2. 24 首次原生 Wayland 夹具**强制 `GTK_IM_MODULE=ibus`**，实际 auto 选择 keyboard，GNOME46 缺少所需原生键盘接口，结果 `unsupported_compositor` 且 0 字符。包内诊断当时 V5 文件正确/state enabled。移除夹具的强制直接 IBus 模块，使用真实默认 GTK Wayland 输入上下文后通过。第一种配置仍是失败，不能把默认上下文通过外推到它，更不能宣称 GNOME46 原生 keyboard 已通过。
3. 24 GUI 严格驱动第一次报告 `Invalid screenshot output`，主进程退出 0，五张 PNG 随后均合法可视。驱动只等待 page05 出现，尚无原子完成屏障，因此“读取写入中的文件”是与现象一致的推断，非已确定根因。原始失败目录 `ui-r1-read-during-write` 保留；未修改驱动重跑后全部门槛通过。
4. 26 XFCE Xorg 第一条完整任务实际上 succeeded、目标全文正确、键对平衡且无 cleanup_errors；但刚冷启动的音频服务把初始 defaults 返回为 `@DEFAULT_SINK@ / @DEFAULT_SOURCE@`，测试结束变成实际 `auto_null / auto_null.monitor`，严格“defaults 不变”断言失败。失败保留 `suite-keyboard-normal-r1-audio-startup`；音频服务 ready 后按原断言重跑通过。
5. Fcitx 零发送专用夹具曾硬编码构造 `HybridKeyboardInput()`，在 XFCE Xorg 回退时不符合实际 Session 使用 `keyboard_for_desktop()` 的行为，结束报 `session_closed`。原夹具和原始失败 `fcitx-zero-raw-xorg-r2` 保留；改用产品同一桌面工厂后通过。只改隔离夹具，未修改生产路由或弱化零发送/取消断言。普通 default Session 的 Xorg 样本独立通过，不受该夹具问题替代。

## 清理与复现

[原始增量证据](evidence/appimage-ad355d-session-followup/) 包含完整失败及成功的 SSH receipts、包审计、receiver/report、目标按键事件、GUI、环境/session 记录、容器退出状态、清理结果、停止子盘归档 SHA 及夹具。`.py.txt` / `.sh.txt` 仅为证据保存，复现时恢复后缀；尾空格原始日志无损 gzip 保存，未修写内容。`evidence-manifest.json` 校验每个已保存文件字节。完整 gzip 客机写入层不进 Git，仅在上述 dist 私有目录保留并全流解压 SHA 校验。

原环境先核验同 SHA，`start-gap24.py` 启动只读原24快照，待实际 SSH ready 后依次挂载、`guest.py prepare`、`gap.py install`，`guest.py cleanup` 后 `select-wayland.sh` 正常客机 GDM 重登。重新 prepare、`gap.py enable`、`gap.py suite-ibus`，disable 后 `suite-keyboard`。26 由 `start-gap26.py` 顺序启动、同包 prepare/install/relogin/enable，执行 `suite-ibus`；disable 后 `suite-keyboard`、`suite-keyboard-native` 和 `fcitx-zero`，正常卸载再 `select-xfce.sh`，核实实际 X11/XFCE 后重新 prepare、keyboard、Fcitx zero、GUI。每次切会话均使用新实际 mount；不能复用已卸载路径。保留原 driver 安全断言，步骤失败即停止后续依赖，修正夹具需另存失败，不改写已成功结果。

最后24零发送缺口由 `start-gap24-zero.py` 从已停止且全流校验过的24Wayland子盘恢复，仍以只读快照启动独立写入层，重复同包 prepare/diagnostic/fcitx-zero 后立即清理关机。

每台正常 `cleanup`、`resource-check`、poweroff，等待容器结束及完整写入层归档；资源检查验证本候选进程、capability、虚拟音源模块和生成键残留为 0，锁可获取，Fcitx 无 owner，FUSE mount 消失。原始基础盘、父盘和快照未写。

## 仍未证明的行为

本轮有限后端/控件样本不等于所有24.1兼容性承诺。尤其未实测本 SHA 在 Chrome/DeepSeek/Codex 中的端到端输入、真实麦克风和云端认证、全局 Ctrl+F4/F13/F14/Escape Portal、所有悬浮窗、桌面安装/启动器迁移/自启动、密码框、预先 held 修饰键、其他 IM 引擎/隐藏预编辑、输出中逐字符跨应用切焦、实际任务超时/被替代及迟到网络响应。V5启用时 Fcitx 无目标→GNOME-owned 的交接未在本轮完整重跑，IBus 仍是尝试/未确认投递。不能由候选通过样本称用户 Chrome 故障已经解决；发布与稳定入口仍由主任务审查后决定。
