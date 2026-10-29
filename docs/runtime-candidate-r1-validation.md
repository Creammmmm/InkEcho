# AppImage 开发候选验证（未发布）

冻结源码清单 `SOURCE-SHA256SUMS` 中 614 个文件构建后逐项校验通过；
候选 `source/dist/InkEcho-0.10.2-x86_64.AppImage` SHA-256 为
`6f7687b0574524e70a60199ee0dab970563801dc8afbc96e3f6dc649822ad8dd`。
该文件是当前未提交源码的隔离候选，不是正式 0.10.2 发布文件；未更新
稳定入口。实际包解压后的 Fcitx 插件 SHA-256 为
`532ef632385bfe9ae3b76312b74874a7cc562c58435bb07f430e704179ebd139`，
包内 `output_router.py`、`framework_detection.py` 与冻结源码逐字一致。
第一次构建显式设置 `SOURCE_DATE_EPOCH=0`，与 mksquashfs 的显式时间
参数冲突而失败；去掉环境变量后按脚本默认值重建成功。

Ubuntu 26.04 GNOME Wayland 客机实际校验包 SHA、从包提取实际 AppDir，
用包内 Python 和安装器在隔离目录安装候选插件，首次配置读出
`output_method=auto`、映射等待和绘制反馈超时下限各 40 毫秒。真实桌面
XWayland 自有 GTK 控件中，生产路由自动和手动各输入一字，焦点未改变、
文本为甲乙；取消任务返回 `fcitx_cancelled` 且无新字符；准备后更换
Fcitx 进程，旧连接返回 `fcitx_delivery_unknown`，无重放。键盘是拒绝
输入的测试替身，不证明真实键盘。测试脚本和目标在 `package-probe/`，
其中 `run_package_probe.sh`、`route_probe.py`、`target.py` 的 SHA-256 为
`40a16dd70565030125741da2b1d62fa62f506d79c51546d46aaf92665efc9292`、
`ebface886f5a2db0436e5252aa271ac09d6c28c48ac456ea5f2ffd404d977a4b`、
`d5ecb06be3fd9dfaa5c2e249bb42f2c0702e422624a9bb393f472cdd8317e76c`。
首次因测试控件未映射导致 X_SetInputFocus BadMatch，等待可见后完整重跑
通过；测试脚本的摘要对应成功版本。

实际 AppImage 用 `APPIMAGE_EXTRACT_AND_RUN=1` 在同一客机分别以 xcb 和
`QT_QPA_PLATFORM=wayland` 启动，均可见并生成 5 张页面截图，自动退出；
原生 Wayland 设置页经人工查看。截图和 xcb 重试日志在
`ubuntu26-ui-evidence.tar`。首次 xcb 关闭出现工具输出警告片段：
`RuntimeWarning: coroutine 'HomePage.refresh_balance' was never awaited`；
同参数重跑未复现，首次完整原始日志未另存，不能冒称保留。独立源码级
确定性复现位于 `page-cancel-warning-probe.py` 和 `page-cancel-warning.log`：
Page.run 创建任务后立即取消可能留下未等待的操作协程。它证明机制存在，
但不能证明首轮 AppImage 警告由该时序引起。Wayland 启动还有 Qt textinput
诊断警告，未见进程失败。26 实验后确认服务退出、输入环境恢复、临时目录
删除、虚拟机正常关机，容器退出 0。

Ubuntu 24.04 GNOME Xorg 客机核对**相同 AppImage SHA**与桥 SHA 后，
包内安装器正常安装，读取默认自动、40、40 毫秒。实际包生产路由在
自有 GTK 输入框中，自动和显式各输入一字，最终为甲乙；取消及准备后
更换服务分别返回 `fcitx_cancelled`、`fcitx_delivery_unknown`，没有
额外文字。实际 AppImage 经 `APPIMAGE_EXTRACT_AND_RUN=1` 启动，xcb
平台可见，生成 5 张截图并正常退出；设置页经人工查看。客机输入环境
恢复 IBus，Fcitx owner/进程消失，临时目录删除，正常关机、容器退出 0。
截图和原始应用启动日志保存在 `ubuntu24-ui-evidence.tar`。

这些是两系统同一候选包的**部分测试**，并非完整包验收。当前未验证
原生 Wayland 的 Fcitx 输出、真实键盘后备、服务在发送中变化、真实语音
链路、FUSE 挂载与全部用户目标；因此稳定入口更新和发布均未完成。
工作树在本候选快照后继续变更，此包不能代表最新源码。

## 证据保存位置

可纳入仓库的测试脚本、614 项源码摘要清单、24 与 26 设置页截图、24 原始
启动日志、26 xcb 复测日志及协程警告复现脚本保存在
`experiments/fcitx-runtime-version/candidate-r1-evidence/`。摘要清单自身
SHA-256 为 `d99c2da3c969edd09c6259cdd8a4f3a01b3fe93957f44bb2e6028bc64c00108a`。
路由原始脚本和目标脚本分别见 `experiments/fcitx-runtime-version/route_probe_measured.txt`
及 `experiments/ibus-gnome-shell/auto_detection/target.py`。
本文其他相对文件名指向被 Git 忽略的 `build/runtime-candidate-r1/`；
包括完整冻结源码、候选包与全部截图的临时构建目录可能被清理，摘要清单
不会单独保存文件内容，不能把它误称为可恢复的完整源码快照。
