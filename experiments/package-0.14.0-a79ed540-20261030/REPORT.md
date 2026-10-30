# 0.14.0 同一 AppImage 的 Ubuntu 24/26 实际包验收

2026-10-30；候选包，供独立审查。没有发布、tag、更新稳定入口或修改产品源码。本报告仅覆盖列出的实际会话、后端和自有控件，不是任意应用兼容保证。

## 产物与隔离

- 产品来源：干净版本提交 `0a13b3af12c764992e09622fa6a745067f70cd1d`，版本 `0.14.0`。
- 唯一产物：`dist/candidate-0.14.0-0a13b3a-20261030/source/dist/InkEcho-0.14.0-x86_64.AppImage`，104425976 bytes。
- SHA-256：`a79ed5409e6d935ac1d4f4420f06e5ec6bc454fc20bdfe04c6db1e8ed6def055`。两系统、各次 FUSE 挂载和 GUI 探针均使用这一份，未追加源码覆盖层。
- 包内版本、模块来源、冻结源码字节对照通过；独立清单核验 3707 regular files、1048 symlinks，七份 bounded owned 资产一致。见 `raw/artifact-verification.json`、`raw/inventory-verification.json` 及各 stage 的 package-audit。
- 两台虚拟机顺序运行，宿主无并行桌面任务；只读快照/父盘、独立 RAM 写层、无外网，仅自有 fixture/output 共享目录。没有访问宿主浏览器、输入法、用户正文或真实供应商凭据。Chrome 使用新私有 profile、正常 sandbox，测试页为本地固定自有 textarea/contenteditable。
- 完整原件、截图、完整停止子盘归档保存在上述候选目录的 `vm24/output`、`vm26/output`；此补丁保留选定文本原件、复现夹具和 pins，不携带浏览器 profile、TLS 私钥、配置凭据、磁盘镜像或大二进制。

## 会话与实际结果

| 系统 / 实际会话 | 实际包检查 | 结果与边界 |
|---|---|---|
| Ubuntu 24.04 / GNOME 46 Wayland | GUI、HTTP ASR、Qwen 实时 VAD/本地协议、provider UI 与包内协议测试 | 完成；GUI 首轮有夹具 PNG 写入读取竞态，严格原探针在独立目录重跑通过，原失败保留 |
| 同上，native Chrome 154 / 旧完整 V5 | 新客户端 direct auto | 明确 `ibus_upgrade_required`，零正文、无迟发；复现并验证 0.13.0 诊断修复 |
| 同上，显式安装并启用新 bounded 七资产 | native Chrome textarea，旧客户端拒绝/旧方法隔离/过期期限/混合22码点/切焦1+21/取消1/待产取消0 | 8项通过；旧客户端只是发布版旧 client 模块配当前解释器，不称完整旧 AppImage |
| 同上，真实 Fcitx 无目标→owned | native Chrome textarea 12项，含前后/连续 LF、同步和原文输出、切焦与取消 | 精确接收检查通过；四项保持 UNCONFIRMED，详见下文 |
| 同上，官方 IBus libpinyin | 自有 native GTK 控件，真实 QMP `n`/`i` | 实际预编辑“你”、正文空；输出被保护，1.3秒后预编辑仍在、正文仍空 |
| Ubuntu 24.04 / GNOME Xorg | 严格 GUI；键盘 normal/cancel；实际 Fcitx 自动路由/官方拼音/预编辑/完整 pipeline/取消 | GUI通过；键盘22码点精确、取消1；Fcitx22码点精确、取消2；切焦旧窗空、无迟发、键平衡和资源检查通过 |
| Ubuntu 26.04.1 / GNOME 50.1 Wayland | GUI、HTTP ASR、Qwen 实时 VAD/本地协议、provider UI、包内 provider 226 tests | 通过；当前包运行身份由 FUSE origins 与 package-audit 记录 |
| 同上，新 bounded / native Chrome 154 textarea | 11项协议/旧客户端/期限/混合 Unicode/LF/切焦/取消 | 全部精确满足检查；见 `bounded014-direct-r3-textarea` |
| 同上，真实 Fcitx 无目标→owned | native Chrome textarea 12项 | 接收检查通过，四项保持 UNCONFIRMED；见 `bounded014-handoff-textarea` |
| 同上，new bounded / native Chrome contenteditable | 混合22码点、切焦1+21、取消1、待产取消0 | 4项通过；保留关闭时 dbus-next warning |
| 同上，官方 IBus libpinyin | native GTK，自有真实 `n`/`i` 预编辑 | 实际预编辑“你”、正文空，输出后不破坏；恢复原输入源 |
| 同上，owned 禁用 | native Wayland GTK 键盘完整 pipeline / 部分取消 | 22码点精确、取消1、旧窗空、1.3秒无迟发，native map/group/modifier 前后一致 |
| 同上，owned 禁用、Fcitx 真实零发送 | native Chrome textarea 自动 keyboard fallback | 全文22、取消1、无迟发通过；没有重放未知输入 |
| Ubuntu 26.04.1 / XFCE 4.20 Xorg | 严格 GUI；键盘 normal/cancel；真实 Fcitx 自动路由/拼音/预编辑/pipeline/取消 | 通过；键盘22/取消1，Fcitx完整全文与部分取消、切焦及清理见原记录。不是 GNOME Xorg |

所有 pipeline 使用固定公共文字“你好 InkEcho，café Ω\n第二行。”（22码点）、生成音频、本地 TLS HTTP ASR 与 SSE 服务，实际包 Session/Router/worker 向真实自有 GUI 控件发送。不是实际麦克风或真实云端识别。等待 1.3 秒检查无迟发不是目标 ACK，也不能证明任意系统负载下永远没有延迟。

## UNCONFIRMED、取消及协议语义

两系统 handoff 各四项 `direct-two-lf`、`direct-three-lf`、`synchronous`、`original-fallback` 实际 DOM 精确接收 2/3/7/7 码点，仍报告 `ibus_delivery_unknown`。这是 direct Router session 完整投递后的未确认语义；Session 的同步/原文样本保留 UNCONFIRMED/full attempts，不升级成普通成功或目标确认。其余精确 DOM 样本同样不代表生产服务获得跨应用接收 ACK。

新服务旧 API 硬拒、外来 Cancel 不改变现有任务、过期期限零发送均实际验证；server-expired 使用已经过期的手动 deadline，不是异步 context 等待时恰好到期的完整桌面竞态样本。部分取消已发生的正文无法撤回，未发送部分和待产任务停止，未自动重放。预编辑样本返回 `ibus_delivery_unknown` 并保持原组合状态，不能把它解释为已送达。

## 保留的失败与基础设施限制

1. 24 GUI 第一轮在共享 9p 路径看见 PNG 文件就读取，尚未写完时格式断言失败；最终文件 CRC/IEND 完整、五页自然退出。原记录及 `gui-race-diagnosis.json` 保留，严格原探针在独立输出目录通过。没有放宽图像检查或修改产品。
2. 24 inherited select-xfce 夹具选择了未安装的 XFCE，实际仍 Wayland；旧 `xorg` 目录不作 Xorg 支持证据。后续以真实 Xorg 进程、seat/session 和 GNOME 环境确认，使用独立 `xorg-r3`。
3. 24 Xorg 首个 GUI 临时输出放在392MiB用户 tmpfs；extract-and-run缓存使其写满。保留 NoSpace、部分缓存和失败原件；仅在无活动引用、完整 tar 内容与 SHA 核验后归档并删除自有可重建完整缓存（释放293548032B）。后续 GUI 使用客机磁盘 `/tmp`，严格原探针通过。
4. 24 Xorg 键盘 r1/r2 没获焦，r3 共享9p JSON读到 Extra data，均发生在正文发送之前。一次私有夹具生成还出现语法错误，未修改产品。r4 将实时状态放客机磁盘，核验自有新 PID/XID 后真实点击，保持原 focus/正文/取消检查，完整通过。原 EWMH 初始警告仍在日志，未静默丢弃。
5. 26启动快照没有自动挂载9p，第一轮缺 helper 文件；显式挂载只读input与独立output后继续。首 Chrome 缺少私有 `session_product_r2` helper，零发送；补齐与24一致的测试 helper 后另起目录。
6. 26 r2 在旧服务还运行时错误开始“新服务拒旧客户端”检查；原 introspection 只有旧 Begin/Commit/Cancel，该失败是新服务未 staging 的前置条件错误，不能算新服务已通过。原因是私有 gap helper 将完整旧安装 verified 误当新安装完成。随后执行严格旧完整集保护、备份、显式新七资产 FILES 字节校验、正常 GNOME 重登/启用/重登，r3 完整协议检查通过；未覆盖失败记录。
7. 辅助恢复/查询曾因遗漏参数、在 Xorg 调用 Wayland 专用检查、或缺少 XAUTHORITY/WAYLAND_DISPLAY 失败。原控制记录全部保留；后续完整白名单图形环境调用通过。没有据错误辅助调用宣称产品输入失败或成功。
8. 部分 Chrome 套件关闭时出现 dbus-next `Future exception was never retrieved` / `BrokenPipeError`；退出0、断言及 no-late 结果保留。未隐藏警告，也不在本候选中修复第三方库。

## 资源与恢复

两系统均恢复原完整 V5 七文件（逐文件哈希相等）、原三项 Shell 设置、原 Wayland 会话和 `xkb:us::eng` / `[('xkb','us')]`。正常重登后核验原系统 Mutter 加载路径；24还核对五库原系统哈希。每轮最终资源审计无候选进程、能力文件、虚拟音频或残留生成按键；锁可获取、Fcitx无owner、FUSE已清除。键盘实际报告 balanced=true/cleanup_errors=[]，26 native map SHA/group/modifier 前后相同。

24正常poweroff，QEMU/container退出0、PID0/OOMfalse；1119813632B 子盘 SHA `6c3626234913d5cd58682e01a1f5bcd8d1e5dfda31c0c29b938cce0174174f81`，归档309834263B/SHA `7ab1ea07533d3d7f03bc884333eb806fd2b07c1dabcb1f49a310701afe3049d0`。

26正常poweroff，QEMU/container退出0、PID0/OOMfalse；410320896B 子盘 SHA `8f66042339ae87a38f74c291e0c2f9f1022f17ce01157487d6e5c977a79e3246`，归档135205143B/SHA `dd5f5f9c9811c204308b0a01ef01846494a72d126504b233d98f0f9b2b983eb1`。两归档均全流解压校验；客机 `/run` 本来是 tmpfs，不在停止磁盘归档内，所需结果/截图/夹具已写持久 output。

## 未验及不能外推

本候选未实际测试真实麦克风、用户配置的全局快捷键、全部悬浮效果、用户桌面安装/自启动、真实供应商云端和真实网络认证，也未在 DeepSeek 网站、Codex、真实用户 Chrome profile 或其他用户应用测试。没有读取任何真实 key。24 GNOME46 原生键盘接口限制仍保留；本包24原生成功样本走 bounded owned，不把它称为原生模拟键盘通过。26 GNOME50没有GNOME Xorg入口，本轮X11是已安装XFCE。不同工具包/版本/负载、完整旧 AppImage→新服务、跨进程远端真实应用、任意大文本/任意预编辑引擎/所有取消竞态没有穷尽验证。40ms默认等待不代表目标应用帧确认，本轮未重做20/40/80ms计时研究。

## 复现与审核

`reproduction/` 保存本轮私有 harness、controller、launch/QEMU 配置和实际命令记录；其绝对路径指向隔离候选目录。产品源码应由上述 commit 的 git archive 取出，不使用未来 HEAD。产物 SHA 必须先独立核对；依赖只读父链与自有停止快照在原始候选目录/既有 VM 目录，不能仅凭本补丁独立重建整个操作系统。按 `raw/vm24/*.json` 和 `raw/vm26/*.json` 的 command 字段顺序执行，禁止并行运行两客机。

`pins.json` 对所附每个记录/夹具记录源相对路径、bytes和SHA256。7份带尾空白的原始日志副本使用确定性 `.log.gz` 无损封装，避免补丁空白检查改写历史原件；对应 pin 另外记录 `decoded_original_evidence_path`、`decoded_bytes` 和 `decoded_sha256`。使用 `gzip -dc <file.log.gz>` 查看，或 Python `gzip.decompress` 后核对解码 bytes/SHA；原 dist 日志保持原字节。截图与大归档保留持久目录。该补丁仅添加证据，尚待主 Agent 独立审查、正常版本化证据提交和最终干净提交完整workflow；不得据此称已经发布。
