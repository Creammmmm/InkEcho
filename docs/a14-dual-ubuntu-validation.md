# a14 同一 AppImage 双 Ubuntu 验收

2026-10-17：同一 a14 AppImage 已在 Ubuntu 24.04.5 KVM GNOME 46 的真实
Xorg 桌面，以及 Ubuntu 26.04.1 GNOME 50.1 Wayland 主机通过下述限定实际包门禁。
两系统均验证可见界面、Qwen 实时配置、本地 TLS/WSS/SSE 夹具、X11/XWayland 当前
光标输入与部分取消；主机另验证原生 Wayland Chrome 的有限 BMP 输入路径，并完成
一次已授权官方 Qwen 实时公开音频能力请求。它们不是全桌面兼容、准确率或真实麦克风
语音端到端验收。稳定入口已部署 a14，Qwen 已切实时模型/协议，现有 F4 与16 kHz
保留；正常用户 profile 已由稳定入口启动并核验为实际 FUSE 挂载的 a14，现有意保持
运行供用户使用。公开 v0.1/a8 未更新。

本文只使用这次 a14 实际证据，不将 a13、旧 a9 或源码测试回填为 a14 结果。

## 用户问题与本次修复

修复调查的初始只读核查发现：当时本机桌面稳定别名解析到 a9，SHA256
`3c18b8773ec95632fd864ffc21a63a08c465b4780c939237f5f27e2dddfc1d07`，
该包没有 Qwen 实时模块/协议选择器。早期工具未检出应用进程，不足以证明主机会话
没有实例；部署前实际 host 视图发现已运行 a13，不能因不同进程视图推定它是在早期
诊断之后才启动。已保存的 Qwen 配置为 `qwen3-asr-flash` 与 `{}`，即 HTTP，
不是 Ubuntu26 禁用实时协议。
旧配置不自动改写为实时；升级后需用户明确选实时模型、转写方式、16 kHz 并保存。

源码另修正了协议提示的两个独立 UI 缺陷：当前方式不匹配曾被笼统称作“不支持”，
切协议后旧红色/tooltip 不刷新。配置错误不再误标为全表模型协议不支持。
源码改动与部署是两步；后续实际稳定入口替换记录在本文部署节。

## 固定来源与已完成本地检查

- UI 修复：`02a90c5148e404b66b9f93cb515ec40d24547d0b`。
- 双系统打包规则：`334f2981dc26a859b5c2f6efb00d29fd1f8e38bb`。
- a14 产品：`43c20edcd652020bfe51b959b85f2f90d8b75059`；三处版本元数据一致。
- prebuild clean 检查：1395 passed、3 skipped，37.29 秒；它不替代新包实际运行。
- 受验 artifact：`dist/InkEcho-0.1.0a14-x86_64.AppImage`，108907000 bytes。
- Artifact SHA256：`bce09c895d51c01c11c73b67aef709632a7514545f0a7fdb6114748c70c8cc96`。
- 静态审计已通过：3958 files、1048 links、43 源文件、71 许可文件、17 个实际 origins。
  证据 `build/a14-static-r1/{baseline,runtime-audit,post-static-preservation}.json`；
  三份 SHA256 依次为
  `3512f591fa71730ec23eebb5bce6fc1ff1a3762d99d1614f1cbc264b9c9a5292`、
  `9802233018ad359fc866fb0dfe192dd6461682034ff1b84dd03454d89bca1a66`、
  `41216543a15d01ed843f2d86b2bdb985ff73220226692e8c6ca7d55ff1c63d20`。
- 包含 CPython 3.13.15、Qt 6.12.0；审计使用包内解释器与 `packages`，没有产品源码覆盖。
- 验收工具的实际 18 origins/full inventory 另行核验；静态 17 origins 与运行时 18 origins 是不同检查集合。
- 同包双系统验收后已实际替换本机稳定入口为 a14；未推送或更新公开 release。

## 构建过程（保留失败，不归因用户配置）

`build/a14-build-r1.log` 记录继承的 SOURCE_DATE_EPOCH 与 mksquashfs 显式时间戳
参数冲突，构建自然退出 1。r2 去掉该环境变量后正常退出 0，日志
`build/a14-build-r2.log`。这是打包命令环境问题，没有改用户协议、密钥或录音配置。
复现命令模板必须避免重复指定时间戳：

```sh
env -u SOURCE_DATE_EPOCH .venv/bin/python scripts/packaging/build_appimage.py
```

## 同 SHA 双系统实际结果

| 系统/会话 | 模式 | 实际结果 | 原始证据 |
| --- | --- | --- | --- |
| Ubuntu24.04.5 Noble / KVM、kernel 6.8.0-142-generic、GNOME Shell 46.0、真实 Xorg session20 | 可见协议 UI、AppRun 九页、合成采集/输入本地WSS、四项 X11 字段/取消/切窗 | 七项验收及独立提取过程的原 owner 全自然退出 0 | `build/ubuntu24-perf-vm/output/a14-acceptance-r1` |
| Ubuntu26.04.1 host / kernel 7.0.0-38-generic、GNOME 50.1、Wayland；XWayland 目标另测 | 可见协议 UI、AppRun 九页、本地WSS、五项原生输入及四项 XWayland 字段/取消/切窗 | 十二个 mode 原 owner 全自然退出 0；有限范围通过 | `build/a14-acceptance-preparation/results-r1` |
| Ubuntu26 官方 qwen3-asr-flash-realtime | 已完成公开 WAV 单次能力请求；无麦克风/桌面输入 | 202 字符，954.919 ms；已审通过 | `build/a14-cloud-capability-r1/results/qwen-rt-capability.json` |

双系统汇总 `build/a14-acceptance-preparation/dual-os-results-r1.json`，SHA256
`115e9775c31c0d9f540c271889fe1d9ffc98466c9a574ae356534230447b1926`，
包含逐结果 SHA、输入/取消/清理与同包判定；主 Agent 已独立核对原始结果、18 origins、
终态及实际截图。Noble 是独立 kernel/systemd/图形会话，不是 offscreen 容器；GNOME
原 owner PID26971、session20。主机 kernel 是定稿时只读核查值。
本地固定识别/润色夹具、真实麦克风、官方能力请求、物理快捷键、native 输入、
FUSE/安装/自启动必须各自分开；完成一项不自动证明其他项。

## 本机 Ubuntu26 八项实际包验收

同一 a14 的冻结来源 manifest 为
`build/a14-acceptance-preparation/frozen-r1-manifest.json`，SHA256
`9dcc07e16a8efb167b0a836dbc8a03563059415a2eb5018acc6e75f12ca2a4cd`，
219 个冻结文件中的 43 个产品源文件与该包 baseline 一致。完整已审 argv 与环境增量在
`build/a14-acceptance-preparation/host-preview-r1.json`，SHA256
`dc4a9b06dff2ebd286d53c34f0db5e3b8fd5e5f9517dc680d4da56a9b16c7020`。
实际桌面 preflight 为 Wayland、真实图形 logind 会话、屏保未激活；产品行为未修改。

| mode | 实际结果 | 原 owner PID/start（均自然退出 0） |
| --- | --- | --- |
| ui-protocol | 原生 Wayland 可见控件；HTTP 标红→实时清除→HTTP 重新标红，私有配置保存/重载，不声称 OS 不支持；5/5 checks | 678610/43061496 |
| local-wss | 实际 TLS/WSS/SSE、本地合成采集与受控输入；25 字符 exact，第二任务取消后仅追加 1 字且无尾部；清理通过 | 678698/43063981 |
| apprun-pages | 实际 AppRun，九页截图，`--quit-after 1` 正常退出 | 678751/43066574 |
| native-textarea | 自有原生 Wayland Chrome textarea，29 字符 exact、29 press/release、first callback 1 | 678821/43067813 |
| native-contenteditable | 自有原生 Wayland Chrome contenteditable，29 字符 exact、29 press/release、first callback 1 | 679352/43070481 |
| native-cancel | 8 字符前缀 exact 后 input_cancelled，8 对按键；再观察 0.5 秒无尾部 | 679841/43071218 |
| native-nonbmp | 非 BMP 输入提前返回 unsupported_text，0 字符、0 按键、first callback 0 | 680116/43071656 |
| native-mixed | 单任务三段，24 字符走 native、5 字符走 XWayland，合计 29 字符 exact、29 对按键、first callback 3 | 680347/43071978 |

原生字段实际观察到 Wayland surface 与 xdg_toplevel，目标进程不继承 DISPLAY；样本含
中文、English、café、Ω、组合字符与换行。该样本通过不表示 emoji 可用：本次非 BMP
明确拒绝。五项输入模式的目标/worker 原 owner 均终态 0，fixture_errors 为空，映射
SHA、group 与 depressed/latched/locked modifiers 前后相同；没有剪贴板或系统输入法。
混合路由是当前光标语义的一次有限测试，不外推所有应用或桌面。

local-wss 的 `real_microphone=false`、`real_desktop_input=false`：虽然使用真实包运行
Session 与真实本地加密协议，采集和输入均为受控夹具，不能称为真实桌面语音端到端。
其固定 normal SSE 为 3 段、每段延时 0.35 秒；预览不参与输出，取消无尾部，HTTP 连接
复用和 fixture 线程清理均通过。它没有真实凭据、云请求或真实麦克风。
ui-protocol 使用一次内存固定模型列表且真实 key reads 为 0；不是官方模型发现/能力请求。
实际 protocol 截图和 AppRun 九页由主 Agent 视觉审查，不以截图代替真实输入读回。

## 两系统 X11/XWayland 与 Noble 实际界面

主机四项 X11 工具来自 `frozen-r2`（220 files），manifest SHA256
`28e6d011aec783bebdce951743577435bf2a6c950dd79a67f4bfec0d7d9ac2a3`；
原始 host-X11 preview SHA256
`a1077f56d26a6eee9b5a9ba71751011fee7a73bb2fde89fab18969cd83942a02`。
43 产品源文件仍与同一 a14 baseline 一致，没有第二个产品版本。

| 模式 | 两系统实际结果 | host PID/start | Noble PID/start |
| --- | --- | --- | --- |
| x11-textarea | 自有 Chrome 字段31字符 exact，31 press/release、31 mapping writes、1 successful restore call | 681429/43081216 | 59857/16363092 |
| x11-contenteditable | 同上，独立 contenteditable 字段 | 681853/43081654 | 60285/16363704 |
| x11-cancel | 8字符前缀 exact、8对按键，9 writes/2 successful restore calls，取消后0.5秒无尾部 | 682242/43082087 | 60712/16364334 |
| x11-currentcursor | 同一个 output_session 内两次 insert，当前光标切窗后精确 [5,26]，31对按键、31 writes/1 restore call | 682471/43082372 | 61005/16364793 |

31码点样本含中文、Latin、café、Ω、组合字符、emoji 和换行；所有 guard_rejections
为0、mapping_restored/driver_closed 为真，目标自然退出0。观察器仅透明计数成功的
原始方法调用，另加新建自有目标的输入安全检查；没有重写 map/send/等待或补做恢复。
切窗是预先审查的自有测试窗口，不向用户应用投递正文。

Noble 的 `ui-protocol`（59582/16361707）与主机相同五项 checks 全真，实际 Qt 平台
为 xcb；私有配置保存/重载成功。`local-wss`（59666/16361934）为同一合成录音/受控
输入协议夹具，25字符最终结果、取消无尾部、线程清理通过，server_errors为空。
`AppRun`（59746/16362636）在 Xorg 实际可见，九张1120×731截图包含 a14 关于页，
主 Agent 已查看；`--quit-after 1` 自然退出0。独立提取过程 owner59501/16361534
也自然退出0。主机九页为2240×1700、Wayland可见并正常退出。
Noble 的八个原 owner 与主机十二个原 owner 的 `*-terminal.json` 均为原 Popen
观察的 exit0；不是以 PID 后来消失作为成功证据。

## 本机 Ubuntu26 官方 Qwen 实时单次能力证据

实际 a14 为上述同一 SHA；运行时 18 个实际 origins 及完整包清单已核验。
能力计划 manifest SHA256 为
`e0ab3ecd94a33096a4899bbc9439e6425f04b9be33e4bfa0ada6534569d5a696`，
固定能力工具 SHA256 为
`562ebe0d9a23d66b8e527799782e6c3dc073092470b49c418299dfb9f0228c67`。
原始安全结果 SHA256 为
`f4d33adf0a0a4f1a225b8cd919c561ff8d6f43c447e00ce84a22543777b6204f`。
唯一请求使用既定 17.645125 秒公开 WAV，SHA256
`0d650ab4f08bd3a5d3d59fd67d085fd0765ddabe4729294f4106fceece321fdf`；
ASR reserved/max 为 1/1，DeepSeek 调用 0、重试 0，无真实麦克风和桌面文字投递。
原 owner PID676102/start43006863 自然退出 0，stderr 为 0 bytes。
返回 202 字符，完成 WAV 能力请求耗时 954.919 ms；这是已完成音频的协议能力测试，
不是停止录音到首字、边录边识别或真实麦克风延迟，也未评估识别准确率。
这次成功确认当前本机 Ubuntu26 与该已配置官方服务组合可用，不证明所有账号、区域、
网关或双系统界面/输入均通过。

用户已明确要求修复本机并支持实时；本次云范围仅此一回 Qwen 请求，0 DeepSeek。
使用现有系统密钥服务，密钥仅保留在内存并用于向用户已配置的 Qwen 端点进行 TLS
认证，不写普通文件、日志或 argv；返回正文只在内存，不新增持久化正文。

## 协议提示、持久化和实际旧配置

记录 HTTP 默认发现 realtime 模型的提示、切 Qwen 实时后的标注刷新、保存和重开
还原 protocol/JSON：本机实际可见 UI 的五项 checks 已通过，使用独立私有配置。
该内存固定列表验证未做真实发现请求；官方单次能力请求另见上节。
官方可推导 WSS，自定义服务需明确地址，实时仅接受 `asr_protocol` 与可选
`realtime_url`。保留 HTTP 专用字段会报配置错误，不会静默删除。
没有真实 API Key 或音频/转写正文进入普通配置、argv、日志或报告。

## 已知存量问题与范围

切换供应商或 Base URL 后，旧发现列表和“连接成功”状态可能保留；这是存量 UI
结果归属问题，不是 a14 新回归，本次未扩改。实际能力测试仍使用当前 provider 的
地址/模型/key_ref，不能据此认为请求发往旧供应商。
本机原生 Wayland 仅按上述自有 Chrome BMP 字段样本记录；Noble 新包验证的是
Xorg，不将历史 GNOME46 缺少原生键盘 API 的边界改写为已支持。该版本未新增真实麦克风、
物理快捷键/F13/F14、悬浮提示焦点、准确率或可靠性分布验收。Noble 只验证提取后
AppRun，没有 FUSE 挂载或安装集成实测；主机另已完成稳定入口替换和正常 FUSE 挂载
启动，未新增图标安装、路径修复或登录自启动验收。
本地协议夹具、桌面键盘测试和官方能力请求是独立测试，不能组合称作已实测的完整
桌面云端语音链路。旧 a11/a12 慢流失败及 a13 有限性能报告原样保留。

## 退出、保留与实际部署

双系统通过后，主 Agent 按用户已授权的本机修复范围审查具体替换动作；唯一操作者
串行执行，没有为部署再次要求用户授权。实际证据分为下列三个步骤，失败记录保留。

1. 首次部署 r1 原 owner684594/start43114838 自然退出2，在任何写入前停止；不是
   自动审批拒绝。原因是仍有旧用户实例 PID667824/start42815371，实际挂载版本为
   **a13**，同时磁盘稳定别名仍为 a9，Qwen 保存的仍是普通 flash/HTTP。运行版本和
   稳定别名不是同一事实；不能把这个在运行的实例写成 a9。首次检查未创建部署输出
   目录，原配置和稳定 hash 均未改。
2. 单次正式 IPC `--quit` 客户端684968/start43133496 的原 owner 自然退出0。
   旧实例随后已不再匹配同一 PID/start，未强杀。旧实例不是此次拥有的 Popen，
   其退出码为 null/未知；不能由 IPC 客户端退出0推定旧应用退出0。
3. r2 审查脚本685068/start43137962 的原 owner 自然退出0；
   `build/a14-acceptance-preparation/deployment-r2/result.json` 为 passed=true，
   稳定别名 `dist/InkEcho-0.1.0-alpha-x86_64.AppImage` 已是受验 a14 SHA
   `bce09c895d51c01c11c73b67aef709632a7514545f0a7fdb6114748c70c8cc96`。
   部署结果 SHA256 为
   `bf80c21f5ea829b4f03390c6cdeaa8291febcc495ca5908c11134946904cb0fb`。
   Qwen 模型改为 `qwen3-asr-flash-realtime`，参数协议为 `qwen_realtime`；只改了
   Qwen 模型和协议，key_ref 不变。现有16 kHz和快捷键 **F4** 保留，未改 GNOME
   binding。此前当前摘要沿用的 Ctrl+F4 不是这次真实设置，不应作为本次部署事实。

r2 将六个原文件备份在 `deployment-r2/backups`，目录0700、备份文件0600；
`deployment-r2/backups.json` 保留原路径、mode 和 hash。settings 原 bytes/SHA
`3f3ccf62bf403bb89dfb3f1f516fcaec629bd9933b800ba3f64e2fc191a06098` 保持不变；
DeepSeek 配置、托管 desktop 文件、图标和自启动未修改，原 a9 和其他旧 artifacts 保留。
部署步骤没有访问 keyring、调用云端或启动麦克风。备份回退材料包含原 a9 文件、
其 sidecar 和修改前 Qwen 配置；不得为了回退重置密钥或覆盖其他用户配置。

正常用户 profile 的启动观察已经主 Agent 验收：
`deployment-r2/installed-app-observation.json` SHA256
`db8be1bf67d249543932cf9d4d97ab9f5991a8b716aab8d332fcf1787739b7e7`，
verified=true。实际 desktop Exec 为 `[/usr/bin/env, --, stablealias]`，应用原身份
PID685116/start43141258，实际执行
`/tmp/.mount_InkEchBLmIhD/usr/bin/python3.13 -m inkecho`。挂载包 inventory 为 a14，
3958文件/1048链接及43个冻结源文件全部匹配；保存配置为实时模型、`qwen_realtime`、
16000 Hz、F4。这是实际稳定 AppImage 的 FUSE 挂载运行，区别于 Noble 的提取后启动。

首次只读启动观察脚本自然退出1，原因是观察器拼错 baseline 的 `src` 前缀，产生
`packages/src` 路径 FileNotFoundError。应用本身正常；修正只读路径处理后，在同一
PID/start 上通过核验，没有重新启动或强杀应用。原观察失败 checkpoint 保留，不能
写成应用启动失败，也不能省略观察器错误。

后验 `deployment-r2/later-application-observation.json` 曾因非提权工具的 `/proc`
视图看不到 PID685116 而记录 false；这是观察器视图问题，不是应用终态。随后授权的
实际 host 只读视图在 `deployment-r2/later-application-observation-r2.json` 中读取
stat 的真实 start_ticks=43141258，确认 `same_identity_still_running=true`，没有
重新启动或控制应用。保持早期误判记录，应用是否存活以实际 host 的同 PID/start
证据为准。最终只读收尾已通过主 Agent 验收：
`deployment-r2/post-preservation.json` SHA256
`f9d7757555b6a55f48ab86e33378a457503bc70ea44e645fa7ee91afed889173`，passed=true。
27个旧版本 artifact/sidecar 保留；settings、DeepSeek、launcher、8个图标、原自启动
缺省状态及 key_ref 均不变。Qwen 新 SHA256 为
`54a3fafcb898192e19782d6b25daefb2add196036c21e2de79587c95ac66bf9d`，只修改模型
与协议；stable 及其 sidecar 均核对为同一受验 a14 SHA。六个备份各与原 SHA 匹配，
目录0700、文件0600。授权的实际 host 只读视图确认同 PID685116/start43141258
仍运行 a14；收尾没有新云请求、麦克风或 keyring 访问。

该进程是有意保持运行的用户应用，`validation_producer=false`；exit_code 为 null，
不要求为了验收而等待它退出，不能写成已自然退出0。启动观察没有新云请求、麦克风
或密钥访问；不证明物理 F4 或真实录音到云端桌面输入已测。已完成的各测试 producer
原 owner、完整 argv、独立 work/profile、日志和终态继续保留，不以 PID 后来不存在
替代原 Popen 终态。
公开 GitHub v0.1 仍为 a8，本次没有推送或发布。

## 复现命令模板与最终检查

这些是经审查的工具入口模板，不是自动运行全部桌面/云请求的脚本。先准备只读冻结
仓库布局（`src` 与 `scripts/validation` 同根），核对上述 manifest/43源/hash，再在对应
实际、已解锁桌面逐项运行；`qa` 必须是新目录，每个 work/output 不得已存在。保留
当前图形会话与音频服务变量，不输出环境；包内解释器只从受验 `packages` 加载产品。
原始完整逐 mode argv/environment_additions 保留在 host-preview-r1、host-x11-preview-r1
及 guest-plan.json（SHA256
`c4ccacf31a4834866a1e4ddf2a8c6326cdcaeb2bc2aaf6c6fc516c0d2bee8ca2`）。
文件名含 preview 的历史记录保留生成时的 `not_executed` 状态；实际是否运行以对应
owner/terminal/result 为准。

```sh
artifact=/absolute/path/to/InkEcho-0.1.0a14-x86_64.AppImage
appdir=/absolute/path/to/extracted/squashfs-root
frozen=/absolute/path/to/reviewed/frozen-repository
qa=/absolute/path/to/new-exclusive-output
sha=bce09c895d51c01c11c73b67aef709632a7514545f0a7fdb6114748c70c8cc96
qt_platform=wayland  # Noble 实际 Xorg 用 xcb
mkdir -m 700 "$qa"
run_probe() {
    probe_file=$1
    shift
    env APPDIR="$appdir" PYTHONHOME="$appdir/usr" \
      PYTHONPATH="$appdir/packages" \
      LD_LIBRARY_PATH="$appdir/usr/lib/inkecho" \
      QT_PLUGIN_PATH="$appdir/packages/PySide6/Qt/plugins" \
      PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
      QT_QPA_PLATFORM="$qt_platform" \
      "$appdir/usr/bin/python3" -B "$frozen/scripts/validation/$probe_file" \
      --artifact "$artifact" --expected-sha "$sha" \
      --package-root "$appdir/packages" --frozen-source-root "$frozen/src" \
      --expected-version 0.1.0a14 "$@"
}
run_probe ui_protocol_acceptance.py --expected-platform "$qt_platform" \
  --work-root "$qa/ui-work" --output "$qa/ui.json" --run-ui
```

本地 TLS/WSS/SSE 使用合成采集/受控输入，不读真实凭据或访问云：

```sh
qt_platform=offscreen
run_probe artifact_entry.py --origins-output "$qa/local-origins.json" \
  --tool performance_package_probe --run-local -- --output "$qa/local.json"
```

真实桌面输入要逐项执行、确认原 owner 已终态后再开始下一项。主机 scope 为
`ubuntu26-xwayland`；Noble 使用 `ubuntu24-xorg`，其 OS/KVM/logind 会话会实际检查，
不能仅替换标签冒充测试环境。`mode` 分别取 textarea、contenteditable、cancel、
currentcursor：

```sh
qt_platform=xcb
scope=ubuntu26-xwayland
mode=textarea
run_probe x11_acceptance.py --scope "$scope" --mode "$mode" \
  --work-root "$qa/x11-$mode-work" --output "$qa/x11-$mode.json" --run-host
```

仅在本机已测原生接口环境运行 native 模板；mode 分别为 textarea、contenteditable、
cancel、nonbmp、mixed。nonbmp 通过条件是明确拒绝且不发键：

```sh
qt_platform=wayland
mode=textarea
run_probe native_acceptance.py --mode "$mode" \
  --work-root "$qa/native-$mode-work" --output "$qa/native-$mode.json" --run-host
```

AppRun 九页在新私有 profile 中启动（主机 wayland，Noble xcb）；启动前清除包开发
变量，保留真实 DISPLAY/Wayland/runtime/DBus，不从用户 profile 读取供应商配置：

```sh
qt_platform=wayland  # Noble 实际 Xorg 用 xcb
mkdir -m 700 "$qa/app-home"
env -u APPDIR -u APPIMAGE -u QT_PLUGIN_PATH \
  -u PYTHONPATH -u PYTHONHOME -u LD_LIBRARY_PATH \
  HOME="$qa/app-home" XDG_CONFIG_HOME="$qa/app-home/config" \
  XDG_DATA_HOME="$qa/app-home/data" XDG_CACHE_HOME="$qa/app-home/cache" \
  QT_QPA_PLATFORM="$qt_platform" PYTHONDONTWRITEBYTECODE=1 \
  "$appdir/AppRun" --config-dir "$qa/app-config" --data-dir "$qa/app-data" \
  --screenshot-dir "$qa/pages" --quit-after 1
```

官方能力是**另行明确授权**的一次历史请求，不包含在上述默认本地步骤或测试套件；
本次已执行且预算用完，不为复核报告重发。以下仅是其命令形状；新执行需要先审查
实际计划、固定目标/公开样本、原供应商配置 SHA 和预算。没有默认密钥、音频路径覆盖
或任意上传输入；`--run-cloud` 本身不代替授权：

```sh
# 仅已授权云能力计划；固定 /tmp/inkecho-public-asr-fixture.wav 及上述 WAV SHA
frozen=/absolute/path/to/reviewed/cloud-snapshot
run_probe cloud_realtime_capability.py \
  --expected-provider-sha caace5167457c5878b8e7ad1ec3f1855edf93dbf6c5ea22e209b301709e2cf3c \
  --output "$qa/qwen-rt-capability.json" --run-cloud
```

提交后的完整源检查使用本报告作为 evidence，正式结果由精确 HEAD 的 receipt 记录，
不在本文预先宣称新提交检查成功：

```sh
.venv/bin/python scripts/validation/workflow.py run \
  --module a14-dual-ubuntu --evidence docs/a14-dual-ubuntu-validation.md
```

以 `.git/validation/<HEAD>.json` 绑定的提交与所选 evidence SHA 为准。工作流证明
自动检查和报告身份；桌面/云事实来自上列原始回执及主 Agent 独立验收。

## 本机安全结果指纹

| 原始结果（results-r1/） | SHA256 |
| --- | --- |
| `ui-protocol.json` | `1c48486cb4412b4b358c2f30a22a40bdf1b771c35e26229fcc9d8248fd1253a8` |
| `local-wss.json` | `b733e8ae2f58222c59cb8fa06fa135b1d7824b0ebfabecdb4280d181024d43d2` |
| `apprun-pages-terminal.json` | `0e0114e2a1f75e8de9bbab16b100f93ac8eed6923cddb1029c31d7d0c352c299` |
| `native-textarea.json` | `26d0c1f76227339f7f65e81d3fab56986fc6abca75797bfbca1da218a9efdde2` |
| `native-contenteditable.json` | `83d30ca7c1a74800be0e3aad28506f9038ab8b28704cd7e36d23e50972ba3782` |
| `native-cancel.json` | `af6bce986fe060472d97be669e2afe5a4dc20dc6b0c45d553b7b25dd3fe71f8c` |
| `native-nonbmp.json` | `cde798d3105194be1e18a2f901120649537954e4b6f5c203c09b51cefdaee0e9` |
| `native-mixed.json` | `1fda25ff9e4875ccb0c83cd68135560992df347cfd3501d10eabc210bda035fa` |
