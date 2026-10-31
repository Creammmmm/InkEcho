# Fcitx 输出节奏：双系统源码候选验证（2026-10-31）

这是隔离客机、自有 Chrome 离线页面和源码副本的测试，**不是同一 AppImage 的双系统包验收，也不是完整录音 Session 验收**。本轮最终候选的 `src/inkecho/platform/fcitx5.py` SHA-256 为 `709331bf404a6a7ae59f0ea0670896ecf2cadb1896e27a7b6eaf2b9e9185f4c8`；Ubuntu 24 和26 客机均独立核对了此文件哈希，26 另将94个源码文件与冻结副本逐项核对一致，24 没有独立留存全部文件的哈希比较。两客机使用正式允许的 Fcitx 插件，SHA-256 `f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44`。文本、页面和配置均为测试生成，不读取用户密钥或真实页面。

## 结果与局限

Ubuntu 24.04.5 GNOME46 与 Ubuntu 26.04.1 GNOME50，使用真实系统 Fcitx 5.1.7 / 5.1.19，Chrome 154.0.8037.97（二进制 SHA `6c792041b07547a662e1b17974d1dc34a3db630379b45d9d89ddd7e3e68cc587`），页面 textarea 为自有离线文件。测试在各一次性客机预置插件、自启动 Fcitx 并重新登录；Wayland 中，26 的 Fcitx DebugInfo 显示 `program:gnome-shell frontend:ibus`；24 的记录只显示 `program:` 为空、`frontend:ibus`，不能据此确认进程身份。两系统均检查了 Chrome 的 Wayland compositor/toplevel/keyboard 事件。Xorg 中检查了活动 x11 会话、DISPLAY、Chrome 的 X11 命令行及页面焦点。未传入禁用浏览器沙箱选项，但本实验没有独立认证全部 renderer 的 sandbox 状态。

每格两个独立样本，分别测试20、200字；每个样本用**一个真实 DefaultAutoOutputRouter 输出会话**逐标量调用真实桥，夹具不额外延时。每次记录实际选中 `fcitx`、返回尝试数、页面文字、事件及最终焦点。切焦场景页面收到首字时将焦点从 A 转到 B，最终焦点均为 B；静止场景一直为 A。所有样本逐字精确且所选路由为 Fcitx：

| 系统和会话 | 自动 | 手选 | 原始记录 |
| --- | --- | --- | --- |
| Ubuntu 24 GNOME Wayland | 8/8 | 8/8 | [自动](ubuntu24/candidate-auto40-r2.log)、[手选](ubuntu24/candidate-explicit40-r2.log) |
| Ubuntu 24 GNOME Xorg | 8/8 | 8/8 | [自动](ubuntu24/candidate-xorg-auto.log)、[手选](ubuntu24/candidate-xorg-explicit.log) |
| Ubuntu 26 GNOME Wayland | 8/8 | 8/8 | [自动](ubuntu26/candidate-auto40-r2.log)、[手选](ubuntu26/candidate-explicit40-r2.log) |

每套8例各覆盖两种长度、静止/切焦和重复两次。其200字测试从发送开始到末次接收观察结束约9.09–9.18秒，其中包含发送及额外0.5秒延迟检查；40 ms 的逐次间隔本身在200次尝试间引入约7.96秒，属于明显性能代价。本间隔不是目标应用消费或显示确认；有限样本无法证明在所有负载、应用、输入法或焦点变化下无丢失。测试不重发任何已尝试内容。候选内固定的 Fcitx 提交间隔，与产品设置里的 X11 接收窗口绘制提示等待上限是不同机制。

真实拼音使用客机 QMP 虚拟硬件键建立 `ni`，Chrome 的 composition 事件和文字在自动 Fcitx 任务期间保持，桥返回 `fcitx_composition_active`、0次尝试；空格完成“你”，之后正常输出3字。Ubuntu26 的 [完整记录](ubuntu26/hardware-guest.log) 和虚拟键回执已保存；Ubuntu24 Wayland 的原结果从测试结束时完整只读归档重新恢复，见 [恢复结果](ubuntu24/wayland-preedit-results.json)。恢复客机独立写层正常关机，QEMU/容器退出0、无 OOM，归档 SHA `5b9ef8a301459580744d8002953470bc823a339d4e0987b1c1fcec07a0fedb77`，解压流校验通过。24 当时 QMP 原始键回执被后续 Xorg 夹具覆盖，恢复的结果保留了页面组词和保护状态，但不能独立审计那次键请求回执。两系统分别以手选 Fcitx 验证首字后取消，页面只收到“甲”，1.3秒后无尾部：[24](ubuntu24/browser-cancel.log)、[26](ubuntu26/browser-cancel.log)。这些是程序控制取消及虚拟硬件建立组词，并非物理 ESC 或实体键盘验收。

Ubuntu24 Xorg 的 Chrome 手选取消也通过：[记录](ubuntu24/xorg-cancel.log)。**Xorg 真实拼音未验证**：首次 `ni` 没有产生 composition，随后增加普通 `a` 虚拟键正对照也未进入页面，两次均在发送正文前严格停止；见 [首轮](ubuntu24/xorg-preedit-r1.log) 和 [正对照](ubuntu24/hardware-guest.log)。QMP 请求成功不等于目标收到按键，不能将其称为组词保护通过，也不能据此归因产品缺陷。

## 先前的对照及失败

最初10 ms 候选 `fcitx5.py` SHA `8105513f3ae5e0fadff7e517a5c4290646b9a9992931dc8a52ea1d408d8b6bb3` 的 Ubuntu26 自动矩阵中，1个200字切焦样本尝试数200、A收到1字、B收到198字，合计199且顺序不符；其余7例精确。该版夹具**没有逐例记录所选路由**，所以不能仅由此将该失败断言为 Fcitx 路由；[原始日志](prior/candidate-auto.log) 保留。手选 Fcitx 的8例精确：[原始日志](prior/candidate-explicit.log)。

独立客机内曾将该10 ms 代码仅改常量为40 ms，SHA `5719b424ef00a6de8a1c7b81ba0b5a19a585bb6bafbc07815549c0044f350c6d`，与最终 `709331bf…` 注释不同，不能当成同哈希验收。其26普通负载8例、高负载8例均页面精确；高负载为两路有界 CPU 工作进程，启动时观测各约90%以上 CPU。该早期自动夹具同样未逐例记录路由，不能单凭这些记录声称实际选择了 Fcitx，见 [普通](prior/candidate-auto40.log)、[负载](prior/candidate-auto40-load.log)。

更早的未限速基线，稳定焦点和切焦均可在页面观察到丢字/乱序；具体32例和重登录前前端未连接的失败见 [原始实验](../fcitx-native-chrome-20261031/README.md)。这些结果未证明丢失发生在哪个具体异步组件。不得将尝试返回或固定等待解释为接收确认。

## 复现和清理

使用指定版本的隔离客机快照、只读父盘和独立 RAM 写层，导入冻结源码与插件，准备私有候选清单和依赖。客机独立备份 Fcitx profile，通过标准图形会话自启动 Fcitx 并正常重新登录，检查 Wayland 上 Fcitx 的 IBus 兼容上下文是否已建立；仅当 DebugInfo 有明确 program 时才认定对应进程身份；否则 Chrome 原生 text-input-v3 可能出现 no_target。客机内只对自有页面运行本目录脚本，不能向宿主应用或真实用户桌面发送键。各脚本依赖此前夹具提供的 dbus-next、websockets、QMP 和只读 Chrome 程序。先确认会话、焦点、目标与插件身份，再执行，保存所有失败，绝不以未知投递为依据重放。

24 清理恢复原 profile、自启动和插件描述并重新登录 Xorg，观察原 ibus-daemon 恢复：[记录](ubuntu24/restore.log)。客机/QEMU退出0、无OOM，完整写层归档 SHA `c413fd233d49ba6ffe2346335dad8d4f90d040d32c1bfc4a756a660e9f259f5d`，解压流校验通过。26 同样恢复、重登录并观察 ibus-daemon：[记录](ubuntu26/restore.log)；客机/QEMU退出0、无OOM，归档 SHA `0a8b7e19d9dba6766a8ce779c69778e20bea034bae9dc264cf55f62629c32ce7`，解压流校验通过。

未测：最终候选的 Ubuntu26 Xorg、两系统 GTK 目标、真实第三方网站、跨窗口任意时刻焦点切换、真实硬件麦克风/快捷键、真实云服务及完整 Session；没有用同一个正式 AppImage 完成两系统包验收。这些结果不证明完整目标或发布门已满足。
