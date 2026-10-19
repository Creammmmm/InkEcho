# 五页工作台 0.4.4 双 Ubuntu 实际包验证

2026-10-20。本地交付已完成，后续0.4.5是报告与验证fixture的普通提交计数，AppImage保持本报告绑定的0.4.4与产品提交。

本报告区分源码提交、AppImage 运行字节和后续文档提交。没有创建新的 GitHub release。

## 绑定

- 产品提交：`4b11a200ae0af658cb41168d849670e820d62c8e`，包内版本 `0.4.4`。
- `dist/InkEcho-0.4.4-x86_64.AppImage`：104278520 bytes；SHA-256 `068f07c2c7e7b8c3827bce11d98b3ca77e7a5f5e565248fe026b5b3a7473a976`。
- 同名校验文件 SHA-256：`67c6c49ca01388c28b1ee964486b9a8b0019119089d14b98c0874ff1d80246f9`。
- inventory SHA-256：`8530dcfbe99a2363e99ec2e77ede2e2d659c7085d9e12c406bb6fa0184c7ace8`；3670 个文件、1048 个内部链接，61 项产品文件逐字节绑定冻结源码。
- 冻结提交431个tracked文件；构建 / 提取各原始Popen自然wait0，66个不可变保护路径通过；用户真实配置只做普通文件hash观测，不解析、写入或还原。
- Root 对该干净提交执行完整本地 workflow：Ruff / 338文件格式检查通过，2035 passed、3 skipped、67.53s。

## 需求与界面

仅五个导航：概览、模型配置、风格、设置、帮助。概览没有「准备就绪 / 开始录音」卡片；默认快捷键开始 / 停止，任务准备中与进行中仍可用窗口底部取消。详细状态保留在状态栏。统一InkEcho app identity与单实例IPC；关闭有托盘则隐藏，无托盘保持可恢复的最小化入口。

概览显示字符 / 录音时长 / 次数、最近七天数值图、ASR / 润色选择与显式余额刷新；只保存数值。首次空安装不预建平台或名称，必须自行填写保存，旧合成配置和凭据逐字节保留。语音 / 润色合并配置页，转写方式按平台协议过滤；JSON、可选实时地址隐藏，超时集中在设置。关闭润色后，概览润色选择、模型配置的润色页以及设置中的关联选项实际灰显；风格自定义编辑仍可用。四个内置风格可复制自定义。帮助显示版本并只读手动检查正式版，不自动安装。

官方DeepSeek余额需adapter与精确官方URL共同匹配；UI mock覆盖金额 / 币种 / 可用状态、缺key、并发切换防旧余额串入、其他平台控制台入口。未用真实密钥查询，也没有虚构费用。当前新包不据此承诺真实账户余额或云ASR质量。

## Ubuntu 26.04 本机实际包

实际环境：Ubuntu26.04.1 LTS / kernel7.0.0-38-generic / GNOME Shell50.1，原生Wayland会话，并分别使用原生Wayland与XWayland自有目标。

`build/v0.4.4-ui-acceptance/host-progress-r1.json` 八项顺序自然wait0：workspace、身份IPC、实际AppRun五页、本地TLS/WSS/SSE、native正常 / 第8字取消、XWayland正常 / 第8字取消。

工作台13项检查全部通过，实际导入50项产品模块，显式审计36来源 / 61产品字节。图位于 `work-r1/workspace-ui/pages` 与 `work-r1/apprun-pages/pages`；包含七日3/8/2/6/9/4/7非零图、润色启用 / 禁用、真实widget的离屏合成Siri图。截图不赋予生产宿主任意文件输出能力。

原生Wayland关闭请求由自有子进程 `xdg_toplevel.set_minimized` 证实并验证恢复；协议不提供当前最小化状态，未把Qt瞬态flag当作compositor外观确认。原生app_id与desktop文件一致，第二个`--show`正常返回并复用原进程；不据属性断言每一种Dock外观。

四个实际输入测试均 exact readback / route正确：正常100字、取消8字；每字按下 / 释放配平，无guard拒绝，取消后0.5s没有尾发，native / X映射恢复、目标自然退出和cleanup通过。不使用剪贴板或系统输入法。带自有fresh-focus guard的测试耗时不作为无探针生产速度承诺。

## Siri 抢焦修复

旧0.4.3候选在Siri检查处发现真实夺焦，原失败保留，未稳定部署。原生ToolTip没有transient parent不能可靠映射；实测选择仅悬浮独立XCB ToolTip / override-redirect宿主，主设置仍原生Wayland。宿主仅接受stdin白名单显示快照，草稿在RAM、无凭据 / 模型 / 音频 / argv正文 / 日志正文，不向目标提前发送partial。

本机四个真实包代理宿主均在持续visible / exposed及固定草稿长度52的ACK之后，采集6个新鲜document / field focus样本全部通过；取消ACK长度0、hide确认，EOF宿主自然exit0。正常语音最终屏障与当前光标输出语义不变，不追踪或恢复目标焦点。没有宣称跨桌面置顶或点击穿透均已验证。

源码诊断身份准确区分：外层诊断54680、原生Qt代理54900、XCB宿主54914。源证据不是包验收；包证据如上独立完成。

## Ubuntu 24.04 实际包

同一AppImage实际在KVM中的Ubuntu24.04.5 / kernel6.8.0-142 / GNOME Shell46.0 / session1原生Xorg、active unlocked会话通过。`guest-progress-r4.json` 七项原始SSH / guest child自然wait0：提取、工作台、身份IPC、实际AppRun五页、本地TLS/WSS/SSE、正常100字、取消8字。

工作台13项全部通过，包括空安装与首次完整保存、旧合成配置 / 凭据字节保留、润色启禁、七日非零图、准备中取消、真实Xorg最小化恢复和mock余额 / 更新。来源审计36 / 产品文件61，实际导入50项产品模块。自有主窗口PID3158的WM_CLASS为InkEcho / InkEcho、icon属性存在；第二个--show PID3193正常返回且原实例仍在，最后原始wait0。AppRun五页与合成图位于 `build/ubuntu24-perf-vm/output/v0.4.4-ui-acceptance-r1/work-r1/`。属性一致不冒充各桌面Dock视觉保证。

两项实际Xorg输入各自6个Siri显示中document / field新鲜聚焦样本全部通过，取消清空并隐藏；正常与取消分别收到100字 / 8字、按下释放数匹配、guard拒绝0、目标exact readback / route正确、0.5秒无尾发、X映射恢复且cleanup为空。这里沿用的factory-xwayland测试目录名是历史模板名，实际会话是Xorg；native_mapping_restored为不适用，不写成GNOME46原生Wayland支持。

基础设施失败原样保留：r1的Docker exec发现专用VM已在本轮前正常停止；恢复启动后r2的SSH在banner阶段超时；r3发现重启后预设9p挂载未恢复。三次均没有启动guest-owner或产品child，不算产品失败或成功。专门诊断确认现有QEMU用尽soft nofile1024，临时将其提高到8192（hard524288不变）后QMP / SSH恢复；仅恢复既有input只读 / output读写9p挂载，不重建磁盘、重stage或修改fstab。UDP / DNS套接字来源尚未根治，不声称永久修复。正式r4在挂载、已知SHA、stage440和会话新鲜身份核验后才执行。验收结束通过专用VM中的正常systemctl poweroff关机，容器自然exited0，未强制停止或删除磁盘。

最终Ubuntu guest输出位于 `build/ubuntu24-perf-vm/output/v0.4.4-ui-acceptance-r1/`，local WSS为 `results-r2/local-wss.json`，其余为 `results-r1/`；host原SSH owner / terminal / 不可变保护及真实配置hash观测为 `build/v0.4.4-ui-acceptance/guest-owner-results-r4/`。配置观测窗口内没有差异，未解析或恢复真实配置。

## 真实 FUSE 候选

独立私有HOME / XDG / config、同一版本化AppImage直接启动，实际观察自有 `/tmp/.mount_InkEchAoFeal`，核对全部3670文件 / 1048链接 / 61源码；五页与原始wait0通过。结果 `candidate-fuse-r1/result.json`。未向正在运行的用户实例发IPC、未使用真实配置、未录音或请求云服务。

## 稳定入口与边界

同SHA双系统与FUSE通过Root审查后，已单次精确更新本机既有稳定入口 `dist/InkEcho-0.1.0-alpha-x86_64.AppImage` 与同名`.sha256`。原0.4.0稳定字节备份在 `build/v0.4.4-ui-acceptance/deployment-r1/backups/`；新stable SHA与版本化0.4.4包完全相同，sidecar核验通过。仅这两文件被备份后原子替换，未改运行实例、真实配置、桌面文件、图标缓存或历史版本；没有发送退出 / 重启命令。已在运行的旧实例仍须正常退出后再启动，避免单实例IPC仅唤起旧版本。交付结果为 `deployment-r1/result.json`。

不新增Windows / macOS或GNOME46原生Wayland支持；不把容器审计代替Ubuntu guest真实桌面输入。此次没有真实麦克风、物理快捷键、真实云账户、ASR准确率、真实余额以及guest FUSE认证。私有测试仅固定合成文本 / PCM与本地服务；正常用户配置编辑只记录hash差异、不还原。

## 复现入口与证据

受控私有验收命令已保存于 `build/v0.4.4-ui-acceptance/host-preview-r1.json` 和 `guest-plan-r1.json`，精确helper / 原始Popen owner / terminal均保留；已执行的排他输出目录不得原地重放。重新验证应从同一产品提交新建私有目录，显式seed合成ASR / 润色配置与假key，保持真实配置隔离、固定artifact SHA并在两个实际桌面分别运行，不能用全局默认平台掩盖首次空安装。

`performance_package_probe.py` 在新空配置语义下显式保存合成DEFAULT_PROVIDERS并设置语音 / 润色引用；此为本地WSS fixture前置修复，不恢复产品默认平台。0.4.4实际包已在两系统运行同一私有补丁版本，随最终报告将该5行fixture修复纳入源码。产品包不重建，不把报告提交的新版本计数冒充包版本。

原生Wayland的键盘输出边界仍为项目既有BMP支持范围；emoji / 非BMP明确拒绝，不提供剪贴板或输入法回退。以上成功仅覆盖固定自有测试目标、列明的会话和路线，非任意应用认证。余额、升级检查和实时草稿仍遵循[界面源验证](ui-redesign-validation.md)列明的协议 / 安全 / RAM边界。

最终报告 / fixture 局部验证：`tests/test_performance_package_probe.py tests/test_versioning.py` 47 passed、3.10s；全仓Ruff、格式检查339文件与diff空白检查通过。报告提交后的完整干净HEAD检查另由Root执行，不借用产品提交的receipt推送后续提交。
