# 0.10.10 AppImage 候选实际包验收（受限范围）

此记录验证提交 `34f8ee9b643f82bb30e44d7eaa5a3e30e9c7050e` 的候选，并不表示全部发布门槛已完成。未修改稳定入口、未发布，未在宿主安装或切换输入法。

- 版本：0.10.10，三处版本一致。
- 同一 AppImage：104,409,592 字节；SHA-256 `ad355d622d6888b8092381988327f589f71669791cb32465c0b5e825573bcf23`。
- 持久候选：`/home/lth/github/InkEcho/dist/candidates/InkEcho-0.10.10-x86_64-ad355d62.AppImage`，已复核完整 SHA；原始构建文件仍在 `/run/user/1000/inkecho-candidate-0.10.10-7h_6ed20/source/dist/InkEcho-0.10.10-x86_64.AppImage`。
- 原始构建目录为用户私有可执行内存盘。主任务随后将候选保存至上述项目 dist 路径；完整原始输出、夹具及两份客机写入层归档另存 `dist/acceptance-ad355d62-20261030`（301 文件，120,735,348 字节，manifest.json 记录逐项 SHA）。未删除原始 RAM 数据。
- 构建使用冻结 git archive、原项目构建器、锁定依赖和已有校验通过的下载缓存；未改生产源码。包内 3,706 个常规文件、1,048 个符号链接完成清单核验，93 个应用源码/资源与冻结源码逐字节匹配；libei 许可保留。
- 包内 addon SHA `acd896aae8ab38ecca2685c0dd8639f2910e841176eadccf59ee4943b158c4de`；实际 staging 使用正式资格表，**没有测试临时放行**。双系统实际包 audit 均记录了相同 AppImage SHA，包内 Python、模块来源和资源。

## 实际会话与结果

| 系统/会话 | Qt 实际包 GUI | 文本接收窗口与输入后端 | 本轮结果 |
|---|---|---|---|
| Ubuntu 24.04.5 / GNOME 46 / X11 | xcb，五页均查看 | 系统 GTK3 Xorg 控件，真实 Fcitx5/Pinyin | 下列样本通过 |
| Ubuntu 24.04 / Wayland | 未测 | 未测 | 不宣称支持 |
| Ubuntu 26.04.1 / GNOME / Wayland | 原生 Wayland，五页均查看 | 系统 GTK3 **XWayland** 控件，真实 Fcitx5/Pinyin | 下列样本通过，不能等同原生 Wayland 文本输入 |
| Ubuntu 26.04 / Xorg | 未测 | 未测 | 不宣称支持 |

每套实测环境均完成：

1. 实际 AppImage 五页截图、中文字体及布局查看；IPC 显示/退出、冷启动 toggle/cancel/quit、配置不变、损坏配置保留。主进程正常退出；截图是滚动页面当前可见区域，不代表页面所有控件已人工交互验证。
2. 实际 FUSE 包内解释器执行本地 HTTPS ASR、Qwen TLS/WebSocket VAD 正常/取消及 provider UI 配置协议检查。供应商协议测试严格使用包内解释器 `-I`、经哈希清单限定的纯测试框架和纯冻结源码，24 为 **226 passed / 23.89s**，26 为 **226 passed / 22.48s**；无 skip、无源码模块覆盖包内容。框架清单 SHA `b01175767169904824c36199b10e07b21c4f417ce0ee39783b744be199084792`，测试清单 SHA `f7942311852a1c31ea4e92e24d68a976aace8cc9fc17d1af361d5f4261a118ab`。
3. 默认自动路由实际选中系统 Fcitx；普通中文正常到达。QMP 虚拟硬件按键建立真实官方拼音 `ni`，目标观测到长度 2 的预编辑；新任务得到 `fcitx_composition_active`，发送计数 0，原正文与预编辑保持。用户虚拟 Space 完成“你”后再启动新任务，取消样本仅确认一个字符，等待 1.2 秒无尾部追加。不是 XTest 伪造预编辑，也不等同物理键盘实测。
4. 实际 Session、虚拟 PulseAudio 音源、本地 TLS Qwen WebSocket、本地 SSE 润色、真实系统 Fcitx 与自有 GTK3 目标串联。正常收到完整 22 字符 `你好 InkEcho，café Ω\n第二行。`（其中 `\n` 为真实换行）。录音期间夹具切到另一个自有控件，旧控件不变、新控件收到全文。另一次以接收窗口观测到前三字符 `你好 ` 触发取消，等待 1.3 秒无追加。夹具为测试创建并激活自己的控件，不改变产品焦点策略。
5. 预编辑 actor 退出 0；Fcitx daemon 退出 0，临时输入法环境提示恢复。流水线目标在夹具清理时收到 SIGTERM，退出 -15，此为显式测试清理，不冒称正常退出 0。
6. 卸载本次 FUSE mount；最终资源检查确认本次候选进程、capability 文件、虚拟音频模块及测试键/修饰键残留均为 0，锁可重新获取，Fcitx 服务无 owner，mount 消失。
7. 客机正常关机，QEMU 与容器退出 0，无 OOM。每份完整改变写入层归档后做全流解压 SHA 校验；父盘、原始快照、密钥文件只读。

24 子盘归档 48,387,889 字节，SHA `161d3abe376ac27cbd5401094fc7617af5c9224e71642185572bb1f21739a538`；解压后 SHA `2a01fb684fe8c4fa06653b219b8109a0ca6d5741d4f9355c5978112930e58186`。26 归档 63,182,297 字节，SHA `577effc2c5ff3a2713e564ae70d290efa9f4aba1a6205ed009438b81b31478f5`；解压后 SHA `4f9c8fd2683c595a99083a8848d6addd7b212d282216f854dca7ec63cbd4babc`。归档另已保全至上述已忽略的 dist 私有验收目录；本证据补丁不包含客机个人配置、音频 cookie 或密钥。

## 保留的失败与修正

Ubuntu24 启动初次 SSH 超时，等待网络完成后才连通；一次控制脚本在未挂载 share 时继续运行而找不到 guest.py，后改成严格顺序/失败即停。真实 Fcitx 首轮目标没有激活，另轮 xdotool 默认 OR 查询导致多个窗口，严格断言在发送前拒绝继续。改用 PID/标题 AND 查询后仍无激活；截图查明 GNOME 启动 Overview 打开。仅向隔离客机发送虚拟 Escape 退出 Overview，随后目标实际 active/focus 检查通过；未放松产品保护。各失败日志仍在 ubuntu24/output 的 r1/r2/before-overview-escape 文件中。

provider 测试初次未用 `-I` 被严格 driver 拒绝，改正后又因构建树带 AppDir 符号链接被拒绝。最后供应同提交的纯 git archive（无 build/dist）作为测试来源，保留 driver 的隔离、哈希和模块来源断言后通过。失败日志未覆盖。一次宿主 RAM 写入因默认沙箱拒绝而未改变文件，随后以已授权的隔离验收权限执行；无自动审批拒绝。上述是本次夹具/环境准备失败，不作为产品功能通过或回归排除的依据。

## 复现入口与原始记录

[证据目录](evidence/appimage-0.10.10-ad355d/) 保存 build receipt、包审计、原始协议结果、截图、Fcitx/流水线接收窗口状态、清理记录、退出记录与隔离夹具；`evidence-manifest.json` 给每个文件大小及 SHA。原始宿主启动器和各 input 脚本作为记录保留，含本次环境绝对路径；重跑须使用对应只读基础镜像/快照、独立 RAM 子盘以及实际新 mount 输出，不能重用已退出 mount 路径。

原环境可复现顺序：先验证候选 SHA；分别由 `start-package-gate.py`、`start-package-gate26.py` 创建**顺序**隔离客机；对应 `package-gate24-host.py` / `package-gate26-host.py` 运行 `mount`、`prepare`、`gui`、`protocol`、`provider-tests`；再由 `package-gate24-hardware.py` / `package-gate26-hardware.py` 协调包内 `fcitx` 与虚拟硬件 mailbox。执行 `cleanup`、`resource-check`、`shutdown`，等待容器正常结束与写入层归档 receipt。每步失败即停止后续步骤；先检查 guest ready、实际桌面及足够配额，不跳过安全断言。`input/guest.py` 中记录包内解释器/环境、确切 driver 参数及命令，`input/fcitx-package.py`、`pipeline_suite.py` 记录目标断言。测试框架与冻结测试文件依清单从同提交复原。

## 未完成项与发布限制

本候选尚未完成默认 IBus/GNOME-owned、键盘回退与零发送回退、无目标回退、任务过期/替代、旧 addon 跨版本的实际包样本；已通过的源码单测不能替代实际包样本。24 Wayland、26 Xorg、原生 Wayland 文本目标、Chrome/DeepSeek/Codex、其他输入法引擎/隐藏客户端预编辑、密码框与实际 held-modifier 条件也未覆盖。没有采集物理麦克风或调用真实云端认证服务，没有重验全局 Ctrl+F4/F13/F14、原生 Escape Portal、所有悬浮/桌面集成及自动启动边界。不能用本轮样本证明用户 Chrome 故障已修复，也不能将两系统有限样本标为全部矩阵/完整发布验收。

最终宿主 MemAvailable 约 10 GiB，两台本次客机均已停止；磁盘用户配额仅余 50,685,952 字节（不是文件系统 free）。候选/完整子盘现另已保全至上述项目 dist 持久目录，该文件系统空间充足；非敏感证据另存 /tmp。主任务已授权继续本 SHA 缺口验收，后续增量单独记录，不改写本轮通过范围。未更改用户配置、凭据、快捷键或稳定入口。

原始 Python 夹具以 `.py.txt` 保存，复现时恢复后缀；这是证据保存，不参与应用导入。

原始 Python 夹具以 `.py.txt` 保存，复现时恢复后缀；这是证据保存，不参与应用导入。
