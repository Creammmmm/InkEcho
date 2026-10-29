# 包含 Fcitx 服务变化保护的候选包

2026-10-28 隔离冻结当前源码构建候选 `InkEcho-0.10.2-x86_64.AppImage`，
SHA-256 `852a9e53efd66c7a19806e2473726d1ae5cdae5306804992fbf7d925eb583a48`。
这是未发布候选，未更新稳定入口。冻结源码和候选包位于忽略目录
`build/runtime-candidate-r4/`；构建日志、包清单、源码哈希清单保存在
`experiments/fcitx-runtime-version/candidate-r4-evidence/`。源码清单 SHA-256
`d0b76e05d1b9f2185383f811db06afb5ab2223f527e28d9514ff75a5f291887c`，
构建后全部复核通过；包内 squashfs 的 `fcitx5.py` 与冻结源码 SHA-256
均为 `ec6fa4434a31ebd94222777d4f63d9755952d08acb2c46ab4b92b8e5799322f9`。
缓存构建依赖由构建脚本按固定哈希验证。

## Ubuntu 26 GNOME 原生 Wayland

使用同一包内代码与私有 Fcitx 服务，在自建原生 GTK 控件和固定合成
输入上测试自动及显式模式。两种模式的受控切焦测试各为 A 1 字、
B 199 字且拼接准确；两种取消各保留 1 字前缀。发送在切焦期间被
暂停，因此不能当作自然切焦。

另使用简单 GTK 控件和真实键盘：自动模式先选 Fcitx，`no_target`
确认零字已接受且结果明确后回退键盘；10 字准确，取消保留 6 字前缀，
自然切焦 A 8 字、B 52 字且拼接准确。私有 D-Bus 模拟服务切换测试中，
旧连接仍存活但失去服务名，桥报告 `owner_changed`，旧服务只收到
先前一个字；该服务为模拟对象，且等待了信号，不能证明检查和发送
之间竞态为零，详见 `docs/fcitx-owner-change-validation.md`。

相同包直接通过 FUSE 启动 GUI，可见并产生五张截图，退出 0；日志
保留 VA 及 Qt Wayland 提示。上述为固定合成数据和自建控件测试，不
证明真实语音、云端、其他应用或完整双系统包验收。

原始日志、脚本及截图在 `candidate-r4-evidence/ubuntu26-wayland/`。
Fcitx 受控、键盘回退、模拟 owner 切换和 FUSE 日志的 SHA-256 分别为
`2ed4038ca22119bc523a3d0a9a4b832dd813585c9ad3f603597a6137de2e7b34`、
`d2a16a0dee3565a4818a55383bbba6b5d7159485e45f88ab844b770b82d29633`、
`75055b991c38b40b94ae27235c0f46c9cdcb576cee6d85c28d7609ba6dbf46d6`、
`2ef19edd41076b32f76878bad4ec059882e2b68c82470f1cef56e5205d97b663`。
复现需按脚本要求将 `.py.txt` 原文复制为 `.py`，在隔离桌面使用候选
包及私有配置；owner 测试须使用私有 D-Bus 会话。结束后 Fcitx owner
为 false、未见残留挂载、测试目录删除，客机正常关机退出 0。

Ubuntu 24 同包验证及其他完整包验收项仍待完成；本报告不授权更新
稳定入口或发布。

## Ubuntu 26 XFCE X11 补测

同一 r4 SHA 的包在隔离 XFCE X11 会话（`Type=x11`）检查；这不是
GNOME Xorg 会话。固定合成输入与自建 GTK 控件上，自动和显式 Fcitx
模式受控切焦均为 A 1 字、B 199 字，拼接准确；两种模式取消均保留
1 字。切焦期间发送进程暂停，因此不是自然切焦。

另用真实 X11 键盘及简单 GTK 控件：自动模式先选 Fcitx，`no_target`
确认接受 0 字、无不确定结果后回退，10 字准确；取消保留 3 字前缀；
自然切焦 A 2 字、B 58 字，拼接准确。同包直接经 FUSE 启动 GUI，
实际挂载类型为 `fuse.InkEcho.AppImage`，窗口可见、产生五张截图并
正常退出。日志保留 VA 提示，不能推断真实音频或其他应用表现。

证据在 `candidate-r4-evidence/ubuntu26-x11/`；Fcitx、回退、FUSE 三份
`run.log` 的 SHA-256 依次为
`2850c1cfd3f091f216021917e90ebaf6a871a8fb91412c9f5bb60ee14f65ee5d`、
`fef5ef2558c864404129218890e4fac00453d7dec589150f61c4276afde874d9`、
`98929ecac0929aa9742477bb845bab6d5e1b553c985a7db138d9fb73a31fdc89`。
原始 `run26.sh`、`fallback-run.sh` 及 FUSE `probe.sh` SHA-256 分别为
`aa76c6bf5fbe2312509eac9343d095e6fc1c9df82e4eb98dc8a5b467b14d90da`、
`496543ca81db86a47b18d4d3123e8cfb87398f9365dfeb26ead137f99f1032ea`、
`4ef6debd0cd1a368b566fb5df993cc28efa509aa61a4c5d0e58763b826c04ec7`。
复现将 `.py.txt` 原文件按各脚本路径复制为 `.py`。GDM、账户配置从
持久备份恢复并逐项 cmp，Fcitx owner 为 false，未见残留挂载，测试
目录删除，客机正常关机退出 0。该项不是完整双系统验收。

## 两系统虚拟音频与中断测试（存在未解决清理失败）

同一 r4 包在 Ubuntu 24 X11 和 Ubuntu 26 GNOME 原生 Wayland 使用包内
真实 Session、Recorder 和私有 Pulse 虚拟音频源，连接本地 TLS Qwen
模拟转写服务与流式润色服务，再经真实 Fcitx 输出到自建 GTK 控件。
正常任务两系统均收到 1601 个音频标记样本，固定文本完整到达，任务
返回 succeeded；模拟服务返回预设文本，未验证识别准确率、真实麦克风
或真实云端。

首字后主动取消时，两系统任务均报告 cancelled，约 1.2 秒观察后目标
均为一字前缀。26 运行进程退出 0 且报告默认音频设备未变；24 虽有
相同前缀观察，但运行以 1 退出：探针即时检查发现默认音频设备前后
不一致。两个取消日志均包含本地模拟润色服务在 TLS 关闭时的未处理
`TimeoutError`，不能称两项清理完全通过。24 原始失败及报告均保留。

26 另在同一音频链首字发出后结束私有 Fcitx 守护进程：任务返回
failed，约 1.2 秒后控件为一个字；探针最终因默认音频设备即时检查
不一致退出 1，故这不是完整通过的链路验收。初次尝试因桌面锁屏未
获取焦点，保留失败日志。另在私有 D-Bus 使用模拟服务验证旧 owner
仍存活但失去名称后未收到第二字；该模拟检查不等同实际守护进程
保持存活并释放服务名，也不能消除检查与提交间竞态。

失败后两客机均核实 Fcitx owner 为 false、未见测试虚拟音频模块，
稍后当前默认输出和输入分别为 `auto_null` 和 `auto_null.monitor`，
临时目录删除且虚拟机正常关机退出 0。测试探针只记录了设备是否
相同，未保存失败场景原始设备名称，故不能证明稍后的默认设备与
原始值逐项一致；不得将此记录视为环境精确恢复或完整包验收。

原始日志、报告和脚本分别在 `candidate-r4-evidence/audio-ubuntu24-x11/`
及 `candidate-r4-evidence/audio-ubuntu26-wayland/`。24 的 normal、cancel
日志 SHA-256 依次为
`3229cae1d9b74c2c933523c22893fce1ff099a21d22053341cb45cff6db9c947`、
`4f5a3b5064c8b0e3b2998a024bbdb3ed1689e527e9dc5fba141b09428b7f4b89`；
26 的 normal、cancel、owner-loss、owner-live 日志依次为
`75b0fe16adab8af5a126c561e54ead991811177a72c4f4e6d8492bb4d02780df`、
`90c9ee6908223ef25b9a156dcf1b4de957cb0ebcb9d675be4a9b51d04d2ba112`、
`1e6694cfa3b151bcbbe6996955e88b2cdce35b2683dc600b521b548c12711cbb`、
`75055b991c38b40b94ae27235c0f46c9cdcb576cee6d85c28d7609ba6dbf46d6`。
复现时将归档 `.py.txt` 按对应脚本路径复制为 `.py`，使用同一 r4 包、
隔离用户会话与虚拟音频模块；owner-live 必须运行在私有 D-Bus 会话。

### 音频清理探针补测

修订后的探针在创建虚拟设备前记录确切默认 sink/source，卸载后最多
等待五秒，要求连续三次读取都与原值完全一致，并保存全部读取；不会
调用设置默认设备的方法。模拟 TLS 服务关闭最多等待一秒，超时则
中止本地连接并在报告中明确记为 `timeout_transport_aborted`；不将
强制中止描述为正常 TLS 关闭。此前失败证据仍保留。

26 GNOME Wayland 的首字取消和首字后结束私有 Fcitx 服务两次运行均
退出 0，目标在约 1.2 秒后的读取均为一个字，任务结果分别为 cancelled
和 failed。两次设备基线均为 `auto_null` / `auto_null.monitor`，清理
后各连续三次读取与基线一致且清理错误列表为空。服务中断例模拟 TLS
服务报告 `closed`；取消例报告 `timeout_transport_aborted`，这是有界
清理但不是完整 TLS 握手。Fcitx owner 为 false、未见测试音频模块，
临时目录删除，客机正常关机退出 0。这些实验仍使用虚拟音频、模拟
服务和自建目标，不能代表真实麦克风或云服务。

24 X11 三次尝试均在录音之前因自建 GTK 控件未获得焦点而退出；其中
两次窗口激活报 `_NET_ACTIVE_WINDOW` 错误，第三次改用 `windowfocus`
仍无控件焦点。检查时会话活跃、LockedHint=no，原因未确认，不作
产品通过或失败的推断。未进入虚拟音频链，也未得到新的设备基线；
服务退出、测试目录删除，客机正常关机退出 0。24 的取消和中断
清理复验仍未完成。

后续 24 Xorg 复验已完成，见下节；上述失败记录仍保留。

原始日志与复现脚本位于 `candidate-r4-evidence/audio-rerun-ubuntu26-wayland/`
及 `candidate-r4-evidence/audio-rerun-ubuntu24-x11/`。26 的 cancel、
owner 日志 SHA-256 分别为
`b8c60ef55a9e63ab49b0bb7923f7e9b0d05ff3da1720b99cfaa29eadbf0c825f`、
`1b9b50c672c35932de0a7f08ec9844e2102771dbcad0321032ecd0eacadd517c`；
两份对应报告为
`c49acefb225779ce49add92f9de9dd829a43be5111488f0342797d450e22dae8`、
`41e4f9ebfab74c1c46b365b21e16b5a3eba042a825d4cbe8eb2458a643841832`。

### 24 Xorg 焦点确认后的音频复测

使用同一 r4 包，调整隔离探针先请求活动窗口及输入焦点，并独立核对
活动窗口 ID、X11 键盘焦点、窗口 PID 与自建目标进程一致，再核对
GTK 文本控件获得焦点，所有条件满足后才开始固定合成音频测试。两次
测试分别在首字后主动取消和终止私有 Fcitx 进程，任务结果为 cancelled
和 failed，约 1.2 秒后的目标均为一个字；本地模拟服务收到 1600 / 1601
个标记样本，两个探针进程均退出 0。不是测试真实麦克风、云端或
实际 Fcitx 保持存活同时释放服务名称。

两例录音前默认 sink/source 均为 `auto_null` / `auto_null.monitor`。
取消例卸载测试模块后首次读到 `@DEFAULT_SINK@` / `auto_null.monitor`，
随后连续三次恢复到原始基线；服务中断例清理后连续三次均为基线。
没有通过设置默认设备掩盖变化。取消例模拟 TLS 服务报告
`timeout_transport_aborted`，不是正常 TLS 关闭；服务中断例为 `closed`。
该观测支持之前即时检查可能捕获过渡状态，但先前失败的确切基线没有
留存，不能追溯断言其原因。Fcitx owner 为 false、未见测试音频模块、
临时目录删除，虚拟机正常关机退出 0。

原始脚本、报告与日志在 `candidate-r4-evidence/audio-rerun-r3-ubuntu24-x11/`。
取消和中断日志 SHA-256 分别为
`a34bb4d8d0b923b0d3678c472061b0f605e3b9015f38036afed4d08c45e3347a`、
`d17b014155d867911fcbf9a319ab633b4dce83451e771ed4e983117a93dca7c1`；
对应设备报告为
`7dfb3c7d332443d2c1dbade7e8ef8340903a4d795679a70c7851880fc263f20a`、
`89fc77ad814e154a951a90e33b3e588269fa27d6e747021aa956fcbe05bcdc5d`。
复现须按脚本路径复制 `.py.txt` 原文为 `.py` 并使用隔离桌面及同一包。

### 两系统桌面入口与隔离集成补测

同一 r4 包分别在 Ubuntu 24 Xorg 和 Ubuntu 26 GNOME Wayland 的私有
配置、数据和 HOME 目录中通过提取运行：应用自动切换并截图五个
页面，另一实例发送 `--show` 和 `--quit`，主进程退出 0；退出后冷
`--toggle`、`--cancel`、`--quit` 均退出 0 且配置未改，损坏的隔离
配置被保留并以退出码 1 拒绝。这里的控制是 CLI/IPC 模拟，不是物理
快捷键或托盘点击；亦未验证关闭窗口按钮行为。

两系统包内 `DesktopIntegration` 对临时目录实际执行安装、自启动项
启停、移动 AppImage 后修复路径及移除，合成配置文件得到保留。这是
私有目录的方法调用，不代表桌面菜单点击、真实用户的开机自启动或
现有启动器迁移已验收。十张截图已逐张查看：五个页面及选中风格在
两个分辨率下可辨识，模型页面下部需要滚动。帮助页桌面类型显示
`unknown`；该 SSH 测试环境未传入 `XDG_CURRENT_DESKTOP`，不能据此
判断正常桌面会话是否也如此。

24 隔离 GNOME 快捷键尝试：Ctrl+Alt+F12 因系统已有绑定被拒绝；随后
注册 F19 并用 X11 合成按键触发，六秒内测试命令未执行，原因未确认。
测试未证明快捷键功能。清理过程中快捷键列表从未设置变为显式空
数组；检查后仅重置测试产生的该键，最终 `dconf dump` 为空。26 未
进行实际或模拟快捷键测试，物理按键均未测试。两系统测试文件删除，
虚拟机正常关机退出 0。

截图、日志及复现脚本在 `candidate-r4-evidence/desktop-ubuntu24-x11/`、
`candidate-r4-evidence/desktop-ubuntu26-wayland/`；两系统页面/IPC 结果
SHA-256 分别为
`6bc344280d512be7359b64a75aad7a68cbd9f4b4c9cdd731159a621e3a33d4f2`、
`4eb2a7b0914eb598b5c71a62f04e59d56903dcf301fef4ca00795cdd876a0d53`；
私有集成结果均为
`176542914c953c1b7889f3a6469a60376c6b92ab1318e3c0090ce3539405565e`。
24 模拟 F19 的失败日志为
`d40346c0899defa9f99c083248fcd7cf2f2b9f9d1c739c441765db1464483bf4`。
快捷键脚本只可在全新隔离客机运行，需先保留精确 dconf 基线并核实
退出后恢复；不能将脚本中的列表重置当作可在用户系统使用的方法。
