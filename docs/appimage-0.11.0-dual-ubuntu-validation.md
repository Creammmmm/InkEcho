# 0.11.0 同一 AppImage 的双 Ubuntu 实际包验收

本报告绑定正式版本准备提交 `7203ba160d9975b620c06e1378b2c6f77dffb815`，不是旧 0.10.10/ad355d 的继承结果。下列第24.3节必要实际包样本通过，仍待主 Agent 审核；未发布、未更新稳定入口或自启动，未修改宿主用户配置、输入法、快捷键或凭据。

## 产物、源码与构建

- 版本：**0.11.0**；三处元数据一致，冻结源为上述干净提交的 git archive。
- 唯一候选：`dist/candidate-0.11.0-7203ba1-20261030/source/dist/InkEcho-0.11.0-x86_64.AppImage`，**104,409,592 字节**。
- SHA-256：`51d20c74a31beb7f01008378a76876a491fd8a3cdc6b61bda440a79bf11c966f`。两个客机、各次新挂载均检查此值；最终再次核对一致。
- 构建位于独立、持久、已忽略的项目 dist 目录。使用原项目构建器、uv 管理的 standalone CPython3.13.15、锁定运行时依赖和已有下载缓存，未修改配方或安装宿主软件。13份系统依赖归档逐一校验 SHA，官方 AppImage runtime SHA `156f4bdbde9c52d01814600013e0a273f0118dc2de98975f3c8c63427ec79074`。
- 从实际新镜像提取后完整核验 **3,706 常规文件、1,048 符号链接**，无额外文件/链接，所有链接位于包内；**93 个应用源码/资源**与7203冻结源逐字节匹配。sidecar、runtime前缀及包内版本一致，libei许可保留。
- 包内 addon SHA `acd896aae8ab38ecca2685c0dd8639f2910e841176eadccf59ee4943b158c4de`，真实 staging 使用正式 pin，**没有测试临时放行**。
- `artifact-verification.json` 的 pending 是进入客机前的静态检查状态；最终状态见 `final-receipt.json`。不能把新报表后继提交的版本当作这个0.11.0产物源码。发布仍须绑定7203提交并遵守最终干净提交 workflow。

## 环境与实际范围

两台 KVM 客机顺序运行。原始基础盘、停止父盘、快照及SSH测试密钥只读；分别恢复完整校验快照到独立 RAM 写入层。Docker network none、cap-drop ALL、no-new-privileges，客机4GB/3核、容器6GB限额。所有可变目标、配置、生成音频和固定凭据均在隔离客机，不访问真实云端或物理麦克风。

| 实际系统与桌面 | 会话及目标 | 输入/协议实际结果 |
|---|---|---|
| Ubuntu24.04.5 / GNOME Shell46.0 / Fcitx5.1.7 | Xorg，GTK3 Xorg | 默认auto Fcitx/Pinyin、auto keyboard、Fcitx明确零发送后keyboard回退通过 |
| 同一24客机经GDM切换 | 原生Wayland GUI；GTK3原生Wayland及XWayland分别记录 | autoIBus→原生GTK3；Fcitx/Pinyin及keyboard→XWayland；明确零发送回退通过。未声称GNOME46原生keyboard通过 |
| Ubuntu26.04.1 / GNOME Shell50.1 / Fcitx5.1.19 | Wayland，GTK3原生Wayland和XWayland | autoIBus→原生GTK3；Fcitx/Pinyin→XWayland；keyboard→两类目标；明确零发送回退通过 |
| 同一26客机经GDM选择已安装XFCE4.20.4 | **真实XFCE Xorg**，GTK3 Xorg | Fcitx/Pinyin、auto keyboard及明确零发送回退通过；不能称GNOME Xorg |

GUI四组各五页全部查看中文字体、布局和实际帮助页版本/系统/会话。主应用通过实际AppImage入口、`APPIMAGE_EXTRACT_AND_RUN=1`运行；这不同于FUSE主窗口验收。协议、provider widget、真实Session及guardian使用同一镜像实际FUSE挂载中的解释器与模块，均核验来源，不用源码启动代替。可滚动页面截图只覆盖当时可见区域。

四组AppImage GUI/lifecycle均主进程退出0；IPC show/quit、冷toggle/cancel/quit不复活、私有配置/数据hash不变、损坏配置退出1并保留原件通过。没有将这些页面检查当作真实语音端到端证明。

## 第24.3节实际包门

| 检查 | Ubuntu24 | Ubuntu26 |
|---|---|---|
| 包SHA、版本、清单、93源码资源与包内模块来源 | Xorg/Wayland实际新挂载通过 | Wayland/重登后Wayland/Xorg新挂载通过 |
| 实际AppImage五页、IPC、冷控制、配置边界 | Xorg和nativeWayland通过 | nativeWayland及XFCE xcb通过 |
| 本地HTTPS ASR、Qwen TLS WebSocket/VAD配置与provider UI | 两会话包内运行通过 | 两会话包内运行通过 |
| 完整选定供应商本地协议测试，包内Python `-I` | **226 passed，22.80秒** | **226 passed，22.16秒** |
| Recorder→本地TLS QwenWS→SSE润色→实际默认Session→系统Fcitx | 两会话各完整22字/部分取消3字通过 | 两会话各完整22字/部分取消3字通过 |
| 当前光标、部分取消、无迟到、资源清理 | 下述独立目标及最终检查通过 | 下述独立目标及最终检查通过 |

226例使用按哈希清单限制的纯测试框架与7203纯冻结测试源；不把生产源码混入包内模块，不跳过失败或跳过测试。框架清单SHA `b01175767169904824c36199b10e07b21c4f417ce0ee39783b744be199084792`，测试清单SHA `f7942311852a1c31ea4e92e24d68a976aace8cc9fc17d1af361d5f4261a118ab`。本地固定服务和合成音频与真实供应商认证、真实麦克风明确分开。

## 输入语义、安全边界及观测

- 四会话真实Fcitx/Pinyin：普通中文可发送；自有控件焦点经验证后，由QMP虚拟硬件a/n/i/Space按键建立真实官方拼音`ni`预编辑，观测长度2。新任务返回`fcitx_composition_active`、发送0，原正文/预编辑保持；用户虚拟Space完成“你”后，新任务首字符取消仅留下“己”，1.2秒无尾部追加。不是XTest伪造预编辑，也不是物理键盘验收。
- 四会话真实默认Session完整链路：实际Recorder仅捕获生成的PulseAudio marker，经本地TLS实时ASR和SSE润色，输出固定22字符`你好 InkEcho，café Ω\n第二行。`（其中为真实换行）。录音期间夹具创建并切到新的自有GTK3控件，旧控件始终空，新控件收到全文。独立接收触发取消各留下3字符`你好 `，1.3秒无追加；Fcitx提交不产生伪造键盘事件。
- 两个GNOME Wayland会话：包内V5显式安装、正常重登、校验并启用，真实默认Session不注入输出inputs/router/factory，实际自动选择IBus向原生GTK3发送22字符；取消各留下3字符且无迟到。**正常产品结果仍为unconfirmed / ibus_delivery_unknown**。独立控件确实收到全文也不是跨应用端到端确认ACK。
- V5不存在或已显式停用后的auto keyboard：24 Xorg、24 Wayland→XWayland、26 Wayland→XWayland、26 Wayland→原生GTK3、26 XFCE Xorg，均完整22字、接收取消1字“你”、旧控件空且延迟无追加。每组独立目标观察22press/22release，取消1/1，held集合空。产品取消记账可为0确认字符而目标已收到1；二者如实保留，不重放。
- 五组keyboard样本各有独立映射检查：Xorg/XWayland三组的X映射恢复；26 Wayland两种目标的四个正常/取消样本，独立Mutter前后keymap SHA、group和depressed/latched/locked均一致。检查不代表任意用户预先held修饰键、系统组合键或其他应用的全部边界已验证。
- 四会话真实Fcitx无目标回退：simple IM自有GTK Entry没有Fcitx目标。实际返回两次`no_target / accepted=0 / unsent_offset=0 / uncertain=false`后，auto keyboard才发送完整15字符`无目标 fallback Ω。`；另任务第一字符后取消仅增加“甲”，1.2秒无追加。只转发观察实际错误，不替换响应或放松任务保护。V5启用时的Fcitx→GNOME-owned交接未在本轮实际包测试。
- actor和Fcitx daemon正常退出0，临时系统输入提示恢复；流水线目标由夹具显式SIGTERM清理，退出-15，不能写成目标正常退出0。最终FUSE卸载，本候选进程/capability/虚拟音频模块/所查询生成键残留为0，锁可获取、Fcitx无owner。两客机正常退出0、无OOM。

## 失败、夹具修正和限制

保留所有本次原始失败，未把它们改写成通过：24既有约125秒networkd wait-online使启动期SSH超时，26立即连接时端口尚未监听；此时没有运行产品测试。控制夹具复合命令的stage环境作用域在连接前修正，未影响已运行产品。第一份inline audit JSON固定写根目录，保全原件并复制同字节记录到阶段目录后，后续修正为独立路径。

24切Wayland后，providerUI严格拒绝复用Xorg已存在的work-root（exit2），后续IBus尚未执行；失败与此前HTTP/VAD结果保留在`protocol-r1-workexists`，仅把夹具work-root改为阶段独立，原严格driver重跑通过。只读版本采集曾因24没有xfce4-session而停止，保存失败并改为available=false后继续；不是24 XFCE通过。24的Xorg版本命令因SSH非console被wrapper拒绝，26 XFCE中同类版本命令也有Cannot open display记录；实际桌面/会话由用户manager、loginctl、工具包和GUI帮助页分别确认。26 XFCE4.20.4二进制版本在同客机Wayland阶段查询，无系统包更新。上述不涉及生产修复。

本轮未验证本SHA在Chrome/DeepSeek/Codex中的端到端输出、物理麦克风/真实云端认证、Ctrl+F4/F13/F14、原生Escape Portal、所有悬浮/桌面安装/启动器迁移/自启动、密码框、其他IM引擎/隐藏客户端预编辑、用户预先held修饰键、输出中跨任意应用切焦、实际任务过期/替代/迟到网络回复或旧addon跨版本。未宣称GNOME46原生keyboard或非Linux支持。40ms配置没有被误称为目标应用帧确认；本轮未重新逐值测其调节行为。不能由这些自有控件样本断言用户Chrome故障已解决。

## 记录与复现

[原始证据与实际夹具](evidence/appimage-0.11.0-51d20c/)包含build receipt、实际包完整审计、五页截图、各协议结果、接收窗口/按键/映射快照、预编辑保护、零发送回退、原始失败及最终退出/归档记录；`final-receipt.json`逐项核对，`evidence-manifest.json`绑定每个保存文件字节。`.py.txt/.sh.txt`是复现夹具记录，恢复后缀使用；尾空格日志无损gzip保留。客机私人配置、cookie、SSH/TLS私钥及完整磁盘归档不进入Git。

原环境复现：从7203 git archive运行记录的原build命令，先验证同一SHA与包清单；独立读取原只读快照/父盘链，通过记录的launch.json顺序启动24和26，SSH ready后挂载readonly input与private output。`control.py.txt`记录实际阶段和命令；依次guest prepare/gui/protocol/provider-tests、QMP协调hardware Fcitx/Pinyin、gap keyboard/zero。24安装V5并清理后GDM切Wayland，重新prepare/gui/protocol/enable/IBus/disable及Fcitx/keyboard/zero；26先Wayland基础/Fcitx，安装后正常重登，使用独立owned阶段重新prepare并验IBus/keyboard/native/zero，再清理切实际XFCE Xorg，重新prepare/context/gui/protocol/keyboard/zero/Fcitx。步骤失败即停止依赖并另存记录，不跳过安全断言或复用已卸载mount路径。

完整停止写入层已在候选根目录`vm24/output`及`vm26/output`持久保全，并全流解压SHA校验。24归档49,123,945字节，SHA `c456d6c849c1e1e404bcd44e232b3eeaba5fdff89705ac216d3f1b5c1dd1ef0d`；26归档64,268,324字节，SHA `e6a8ec7ed85c60cee8e83a085ad6053f695ac9443a28c282ae1d7cd3f2807dee`。原始基础盘和快照未改。最终共享工作树仍干净，HEAD仍7203；没有把候选部署或发布。
