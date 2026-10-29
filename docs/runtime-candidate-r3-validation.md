# Fcitx 超时修复候选包验证

2026-10-28 从隔离冻结源码构建候选 `InkEcho-0.10.2-x86_64.AppImage`，
SHA-256 `23b1b77e41e4e3a8fdd30a9a6a892d5b5babeaa9e303fdbcc3b37731e5a1e105`。
这是未发布的候选，不是正式版。冻结源码及包位于被忽略的
`build/runtime-candidate-r3/`，可能被清理；构建日志、包内清单和源码
哈希清单保存在 `experiments/fcitx-runtime-version/candidate-r3-evidence/`。
源码清单 SHA-256 `f6a4a2ac92fbf0aba2f716b1f4142770bfb430d78a0e1f1fd2d6183b259a9ffb`，
构建后全部通过复核。包 squashfs 内 `fcitx5.py` 与冻结源码均为
`bf07c2476489590ba56f6ea20d5c65dea15b7f410394bf0efc443806856cfee1`。
构建最初因网络不可用失败，重试采用此前缓存且构建脚本核验哈希的
系统依赖，成功完成；未更新稳定入口。

## Ubuntu 26 GNOME 原生 Wayland

同一候选直接经 FUSE 启动，mountinfo 显示只读 `fuse.InkEcho.AppImage`
挂载，应用报告可见、产生五张截图并退出 0。原始日志包含 VA 加速
和 Qt Wayland textinput 提示，不能据此推断音频设备或焦点均已验收。

在私有 Fcitx 服务和自建原生 GTK 简单控件中，通过包内真实路由使用
固定合成文字：自动模式先选 Fcitx，收到 `no_target`、已接受 0 且
结果无不确定性后回退真实键盘；完整 10 字准确、取消后保留 5 字前缀、
自然切焦两控件分别收到 8 和 52 字，拼接准确。已发送文字不可撤回。
该实验不验证真实音频、云服务或其他应用。首次运行副本缺可执行权限，
修正后又因桌面锁屏控件未获取焦点；两次失败均保留，解锁后重跑通过。

原始截图、脚本和日志在 `candidate-r3-evidence/ubuntu26-wayland/`。
输入测试 `run.log` SHA-256
`88ded11f523ee14815df7472fc10e7d1722f04ebfac1f68a0f4f7394e7a533fc`，
FUSE `run.log` SHA-256
`d6484df73ba164d22c6e0bef0ccfb9670936579c48c1106d7b70c5a0fab0b606`。
复现需将 `probe-original.txt` 和 `cross-target.py.txt` 分别复制为脚本中
要求的 `.py` 文件，并按 `run.sh`、`probe.sh` 使用一次性配置及候选包。
测试后私有服务退出、D-Bus owner 为 false、无残留 AppImage 挂载，
测试目录删除，虚拟机正常关机退出 0。

Ubuntu 24 同包检查仍待其他测试结果；物理麦克风、快捷键、实际云端、
完整 UI 和集成等均未由本轮完成。该候选不能据此视为完整包验收或发布。

## Ubuntu 26 XFCE X11 补测

同一 r3 包在隔离 XFCE X11 会话（`loginctl` 报 `Type=x11`）验证；
这不是 GNOME Xorg 会话。私有 Fcitx 和包内真实 Session 使用自建 GTK
控件、固定合成输入：自动和显式 Fcitx 模式在受控切焦各输出 A 1 字、
B 199 字且拼接准确；两种模式取消后各保留 2 字前缀。测试在首字后
暂停发送，确认 B 焦点后恢复，因此不是自然切焦验证。

另用包内真实 OutputRouter 和自建简单输入控件：自动模式先选 Fcitx，
返回 `no_target` 且已接受 0 字、无不确定结果后回退真实 X11 键盘；
10 字完整准确，取消后保留 2 字前缀，自然切焦 A 2 字、B 58 字且
拼接准确。直接通过 FUSE 启动同包 GUI，挂载类型为
`fuse.InkEcho.AppImage`，可见且产生 5 张截图并正常退出；日志保留
VA 加速提示。这些是固定合成输入与特定自建控件测试，不能推断其他
应用、真实语音或完整包验收情况。

原始日志和脚本保存在 `candidate-r3-evidence/ubuntu26-x11/`。
`fcitx-run.log`、`fallback-run.log` 和 FUSE `run.log` 的 SHA-256 分别为
`8284d66ecfeed83f0b3f0efe20c6d7b29129ca69302c8a5a394d6da8d14c2ac2`、
`2d1303f5ccd9ab994a5491b31c8b3e956603fb01d99835e8e919a5372fd95333`、
`09dbfba896bd6709aef8cb407b6a07053e5be968cd3b37008be97829e9aae392`。
`run26.sh`、`fallback-run.sh`、`probe.py.txt`、`cross-target.py.txt`、
`probes/target-focus.py.txt`、`probes/sender.py.txt`、FUSE `probe.sh` 的
SHA-256 依次为
`58b131a7c75d765e88e073cbb8555f4925346cbc77f520403625877016b289a8`、
`0fa5d494560475df8b9607e7f8627cf7fc494af048052642cc6cd6910b932ec7`、
`dc1edbe0e30ee69eec11bda3c80f6d097c7b3f8353c701cec3da65afd5e5b7a0`、
`4cfed26ed856bbf68bced39f9bf837abc083a625aa6b2ac1126746268b196e9c`、
`821789723ade582db91d68627dc32a5043dd0620ddc85b807f60193ba8beea42`、
`c57667db94206bd714010df3ce986221b168bd6cb049bc6464ec193585d72c13`、
`063d21116fa016f8106039eb8be4565706698c98d66ad99645e67326997980ce`。
复现时需按脚本的路径将 `.py.txt` 原文复制为 `.py`。测试后 Fcitx
owner 为 false、无残留挂载，临时目录删除；GDM 和账户设置从持久备份
恢复并逐项 cmp，虚拟机正常关机退出 0。

## 两系统本地合成音频任务链

同一 r3 包在 Ubuntu 24 X11 和 Ubuntu 26 GNOME 原生 Wayland 隔离会话
各完成一次：真实包内 `Session` 和 `Recorder` 采集 PulseAudio 私有
虚拟音频源，由本地 TLS Qwen 实时协议模拟服务接收；服务固定返回
转写文本，本地 TLS 模拟润色服务以流式响应；包内真实 Fcitx 路由将
结果送入自建 GTK 输入框。两次各检测到 1601 个音频标记样本，输入框
均完整收到固定文本“本地完整链路测试。”，任务结果为 succeeded。
包内路由准备时记录选择 `fcitx`，包内模块来源及哈希在各自报告中。
这是合成音频与固定模拟响应，不测真实语音识别准确率、物理麦克风、
认证云接口或其他目标应用，也不是完整应用 GUI 和发布验收。

24 首轮任务实际输出完整文本，但探针在任务结束后读取已重置的路由
状态导致断言失败；修正探针为准备时记录状态后通过。失败日志与报告
保留。两系统日志均保留了可选 VA 库提示；报告确认系统默认音频设备
未变、清理错误为空。私有输入服务和虚拟音频模块退出，客机临时目录
删除，两台虚拟机均正常关机退出 0。

证据在 `candidate-r3-evidence/audio-ubuntu24-x11/` 和
`candidate-r3-evidence/audio-ubuntu26-wayland/`；各 `run.log` SHA-256
分别为 `5f4ee2a1b174c3bf2c58acdb953574cdc9396e61a5d2bb9a534a92427b070f47`、
`b3fda46b5056759740a35098edd68da0cb767bfad75419ec414aa83cab9e3647`，
各 `report.json` SHA-256 分别为
`1e1d709eac1503a7966ee3b09b3ce7fec4eb3f2a0a15ae3f282ae8d177c28eca`、
`959406f18472ba758d7c40a5ef929e14ecd0b7c9da1ef003d20067dc22775393`。
两系统的相同 `pipeline.py.txt` 和 `target.py.txt` SHA-256 为
`54310ad5934cabb98e110d1e5a67c0e259024bf295efa4dbbee519e9328a93e8`、
`ea12126ddd38d34bc178c1e69b784e3d1f912957fb3db2db22f3a5dbf314681c`；
24 的 `run.sh` 和 26 的 `run26.sh` SHA-256 分别为
`bbec1a48e25b14bf0b948865dc017863c9985267dd49d08f25e60206001069f8`、
`1fa0bb3fdfc2942a76454911ef5d53a4fe524f3f0cef45a0b73fbad2c49d3df2`。
复现时将同一候选包及两 `.py.txt` 原文按各脚本路径复制到隔离客机并
去掉 `.txt` 后缀，确保允许使用临时 Pulse 模块及私有用户目录。
