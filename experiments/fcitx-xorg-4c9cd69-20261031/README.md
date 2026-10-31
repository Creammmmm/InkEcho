# Fcitx Xorg 源码候选补充验证（2026-10-31）

这是隔离客机的源码输出路由实验，不是正式 AppImage 双系统验收，也没有串联真实录音 Session。源码从提交 `4c9cd6943a0c97da7ca18e4c65f128c31db083d1` 工作树复制，客机实测 `fcitx5.py` SHA-256 `709331bf404a6a7ae59f0ea0670896ecf2cadb1896e27a7b6eaf2b9e9185f4c8`；没有对客机内所有源码文件逐项独立归档比较。插件 SHA-256 `f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44`。页面与文字均为测试自建，没有用户页面、密钥或剪贴板。

## Ubuntu 26 XFCE Xorg

一次性 Ubuntu 26.04.1 客机实际登录 XFCE Xorg，`XDG_CURRENT_DESKTOP=XFCE`、`XDG_SESSION_TYPE=x11`、`DISPLAY=:0`；Fcitx 5.1.19 通过临时自动启动配置运行。Chrome 154.0.8037.97（SHA-256 `6c792041b07547a662e1b17974d1dc34a3db630379b45d9d89ddd7e3e68cc587`）使用 `--ozone-platform=x11 --gtk-version=3` 和独立本地页面/profile，未传入禁用沙箱参数；未独立认证各 renderer 的沙箱状态。

真实 DefaultAutoOutputRouter/Fcitx 桥每次在一个输出会话逐标量发送20或200个合成字，夹具不添加间隔。每种长度与焦点条件分别重复两次：页面保持焦点，或首字输入后由页面将焦点从自有 A 框转到自有 B 框。自动模式和手选模式各8/8样本实际文本精确，逐例报告所选路由为 `fcitx`，切焦后 B 确为活动框：[自动原始结果](ubuntu26/candidate-xorg-auto.log)、[手选原始结果](ubuntu26/candidate-xorg-explicit.log)。这不是应用间任意时刻切换或持久接收确认。

手选首字后取消，页面仅收到“甲”，等待1.3秒无新内容：[结果](ubuntu26/xorg-cancel.log)。真实拼音由测试专用 XTest 发送，不是物理键盘；每次发送前均确认浏览器 DOM 焦点、X11 活动窗口和键盘焦点 XID 相等、窗口 PID 与测试 Chrome PID 相等。普通 `a` 的正对照确实进入页面；随后 `ni` 建立 composition，真实 Fcitx 保护返回 `fcitx_composition_active` 且发送计数0，组合和事件不变，空格完成“你”，随后正常输入“甲乙丙”：[原始结果](ubuntu26/xorg-preedit-xtest.log)。样本有限，不证明全部浏览器/引擎或窗口切换边界。

客机配置由测试前备份恢复，测试 Fcitx 退出、自有插件描述和自启动删除，再设置回原 Ubuntu Wayland 会话；[恢复记录](ubuntu26/restore.log) 显示新的 Wayland 会话及 ibus-daemon，采样时旧 Xorg 会话仍处于关闭过程，未将其写成已完全消失。客机正常关机，QEMU/容器退出0、无OOM，完整写层归档 SHA `42dc2634198aad258521a2a2257bcc7a4bc3dfd68a429bc119c883912e66ee13`，解压全流校验通过。

## Ubuntu 24 Xorg 组词诊断

在独立 Ubuntu 24.04.5 GNOME Xorg 客机上，实际会话 `XDG_SESSION_TYPE=x11`、`DISPLAY=:0`，系统 Fcitx 5.1.7 / Fcitx Pinyin 5.1.3。以同一Chrome版本和自有离线页面，测试专用 XTest 每次发送前校验页面焦点、活动窗口和键盘焦点 XID 相等，且窗口 PID 与测试 Chrome PID 一致。普通 `a` 正对照实际到达，`ni` 建立真实 composition；自动 Fcitx 桥保护返回 `fcitx_composition_active`、尝试0，组合文字及事件不变；空格完成“你”，随后正常输出“甲乙丙”。[原始记录](ubuntu24/xorg-preedit-xtest.log) 和 [测试脚本](ubuntu24/xorg-preedit-xtest.py) 可检查各阶段。

此前独立客机使用 QMP 虚拟硬件时，普通 `a` 与 `ni` 均未到达目标，严格前置中止；该失败及回执保留在 [双系统候选报告](../fcitx-pacing-dual-source-20261031/README.md)。这次严格校验后 XTest 对照通过，说明目标及受控 XTest 路径可用，**没有确定此前 QMP 不达的原因**，也不能把 XTest 当成实体硬件。客机恢复原 profile、删除测试自启动和桥描述，重新登录原 Xorg 并观察原 ibus-daemon：[恢复记录](ubuntu24/restore.log)。客机正常关机，QEMU/容器退出0、无 OOM，完整写层归档 SHA `8f9464e8d1c186eedf8185d37ec7469a26efed484f0dacbeded41d06adb1d40f`，解压全流校验通过。

## 复现及边界

使用指定版本隔离客机、只读父盘和独立 RAM 写层，导入候选源码及合格插件。备份原 profile，自启动 Fcitx，正常登录相应 Xorg 会话，准备测试私有 Chrome 程序与依赖。使用本目录脚本及已有安全的客机控制器，先独立确认会话、活动窗口、目标 PID、键盘焦点，再运行页面矩阵及 XTest 正对照；不向宿主或非自有窗口发送按键，不读取真实文本。清理时恢复 profile、移除临时自启动及插件描述、恢复原登录会话并关机，保留失败和归档身份。

未测试完整录音与云识别、实体硬件、真实网站、所有 GTK/Qt 程序、Xorg 中 IBus 直接桥、跨窗口焦点竞态或 Ubuntu 24/26 同一 AppImage 发布门。Fcitx 返回计数不是目标应用接收确认，40 ms 只是节奏控制；不得重放未知是否已发送的文字。
