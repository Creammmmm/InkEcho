# Ubuntu 24.04 Xorg 的 Fcitx 终端和 Qt 受控测试

在无外网的独立 Ubuntu 24.04.5 GNOME Xorg 客机中测试，磁盘为临时写层。测试源码为 `b1289496502ffa7fbfdecbe7f3237874386e002d`；在客机用 Fcitx 5.1.7 SDK 编译当时的 `native/fcitx5`，所得插件 SHA-256 为 `f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44`。应用 Python 运行时来自旧 0.10.0 AppImage，应用源码覆盖为上述版本；这不是当前版本的包验收。使用真实 Session 和生产自动路由，识别、润色、录音均为合成输入。

- `third-run.log` 和 `terminal-qa-results.json`：两个真实 GNOME Terminal 窗口经 X11 窗口管理器切换，终端子进程从 PTY 原始读取。自动路由实际选择 Fcitx 协议 4；200 字分别收到 18、182 字，拼接与原文一致；首字后程序取消，分别收到 1、0 字，观察 1.3 秒未见其他输入。
- `qt-fourth-run.log` 和 `qt-qa-results.json`：两个系统 Qt 5 的 QPlainTextEdit 窗口，同样验证自动选择 Fcitx 协议 4，200 字分别收到 18、182 字，文本完全一致；程序取消分别收到 1、0 字，观察 1.3 秒未见其他输入。Qt 5、PyQt 和 Fcitx Qt5 前端从 Ubuntu 官方软件源获取，20 个包的 SHA-256 对照客机软件源元数据验证，仅安装在客机临时写层。
- `cleanup-login.json`：测试结束后 Fcitx 插件移除、输入法配置恢复，测试自启动及环境文件移除。客机关机回执另保存在 `shutdown-receipt.json`。

失败样本保留：`second-run.log` 的终端取消用例因夹具截断已经打开的文件、写入偏移未重置而出现 NUL；不能算产品测试通过或失败。`qt-run.log` 为客机缺少 Qt Fcitx 前端时的失败；`qt-second-run.log` 和 `qt-third-run.log` 为将 Ubuntu Qt6 输入插件用于旧 AppImage 自带 Qt 时的失败，第三份诊断确认 Qt 私有 ABI 符号不匹配。它们均没有成功验证 Qt6。另一次最初的运行因 AppImage Python 环境影响系统终端命令而在输入前失败，运行日志保留在本机 `/var/tmp/inkecho-terminal-qa/`（如该临时目录仍存在）。

这些测试仅覆盖所述受控窗口与固定的 200 字中文样本，不证明物理 Esc、真实麦克风或云端识别，也不证明任意切换时机及其他应用；Fcitx 提交回复并非目标应用处理完成的通用确认。不能据此推断 Wayland、Ubuntu 26.04 或 Qt6 的结果。

测试夹具在客机中手动设置 `XMODIFIERS=@im=fcitx`、`GTK_IM_MODULE=fcitx` 和 `QT_IM_MODULE=fcitx` 后再运行自动路由；因此仅证明这些指定环境下的自动选择，不证明自动发现未经干预的系统配置。

`input-hashes.json` 是事后对宿主侧冻结源码副本、候选插件文件以及下载包计算的 SHA-256 清单，不是客机身份认证或构建回执。客机当时显示 Ubuntu 24.04.5、Fcitx 5.1.7，并对 20 个包执行了与客机软件源元数据的 SHA-256 对照；由于没有单独保存这些身份及元数据核对的原始回执，这部分只能作为当时的观察，不能从本目录独立证明。`ram-overlay-archive.json` 和 `qemu-exit.json` 记录客机正常退出及写层归档完整流校验；原始写层归档目前仅位于 `/var/tmp/inkecho-terminal-qa/output/`，不属于本仓库中可复核的证据。
