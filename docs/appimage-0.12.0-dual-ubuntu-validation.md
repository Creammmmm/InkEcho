# InkEcho 0.12.0 同包 Ubuntu 24 / 26 实际验收

本轮对发布准备提交 `895d03bed245aebb21c7124fabbf7df96d6a4aec` 构建的一份候选 AppImage，顺序完成项目规范第 24.3 节要求的双系统实际包检查。两客机全部必要样本完成并正常关机，资源检查通过，写入层完整归档并作解压全流校验。候选包仍等待主 Agent 审查；本记录不执行发布、tag、推送或稳定入口更新，也不表示所有桌面、应用和云端组合均已支持。

## 产物及来源

- 版本 `0.12.0`，发布源 `895d03bed245aebb21c7124fabbf7df96d6a4aec`。
- AppImage：`dist/candidate-0.12.0-895d03b-20261030/source/dist/InkEcho-0.12.0-x86_64.AppImage`，104,417,784 字节。
- 两系统同 SHA-256：`7488566c708d3fc12de665d35dfc7c26a1902908c9fec63e3c905b1446757a78`。
- 构建使用干净提交的 `git archive`、既有构建脚本及经过核对的 13 份依赖缓存。没有改配方或跳过校验；实际来源、命令和缓存清单见 [构建记录](evidence/appimage-0.12.0-748856/build-run.json)。
- [产物核对](evidence/appimage-0.12.0-748856/artifact-verification.json)：实际包完整清单 3,708 个普通文件、1,048 个符号链接；94 个应用源码/资源与冻结源码逐字节一致；runtime 前缀和外部 SHA 文件一致，libei 版权文件保留。清单自身另行核验，不把它的自包含计数当成产品文件缺失。
- 官方许可的 Fcitx 插件 ELF SHA `f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44`，467,136 字节，neighbor-batch 协议 4。没有源码覆盖、运行时 SHA 放行覆盖或替换候选插件。
- 各会话重新挂载这同一 AppImage，用实际动态 FUSE APPDIR 的打包 Python 和模块进行协议/输入检查；GUI 启动采用 AppImage 的 EXTRACT_AND_RUN 模式。每次均保存包内来源/版本/清单审计。没有用源码运行替代包验收。
- 发布准备提交完整本地 workflow：2,612 passed、2 skipped（87.39s），Ruff 412 files 通过。精确提交回执 `.git/validation/895d03bed245aebb21c7124fabbf7df96d6a4aec.json`；完整日志保留在 `dist/release-prepare-0.12.0-895d03b/workflow.log`。后继证据提交仍需对其干净 HEAD 重新执行完整检查。

## 实际会话和输入范围

| 系统与实际桌面 | 实际会话 | GUI / 本地协议 | 实际 Unicode 当前光标、取消与回退 |
|---|---|---|---|
| Ubuntu 24.04.5，GNOME 46.0 | Xorg / X11 | 五页 GUI、生命周期、HTTP、Qwen TLS WebSocket / VAD、供应商配置界面通过 | Fcitx 5.1.7、键盘、零发送回退；Chrome 154 自有 textarea 11 项通过 |
| Ubuntu 24.04.5，GNOME 46.0 | GNOME Wayland | 同上，安装自有扩展后正常重登录 | Fcitx 5.1.7 的 XWayland GTK 目标、键盘 XWayland 目标通过；原生 IBus 实际全文可见但产品结果未确认；没有宣称 GNOME 46 原生键盘支持 |
| Ubuntu 26.04.1，XFCE 4.20.4 | Xorg / X11 | 五页 GUI、生命周期及上述本地协议通过 | Fcitx 5.1.19、键盘、零发送回退通过；这是 XFCE Xorg，不能称为 GNOME Xorg |
| Ubuntu 26.04.1，GNOME 50.1 | GNOME Wayland | 同上，安装自有扩展后正常重登录 | Fcitx 5.1.19 的 XWayland GTK 目标、原生与 XWayland 键盘目标通过；原生 IBus 实际全文可见但产品结果未确认 |

桌面上下文及逐项命令见 [Ubuntu 24](evidence/appimage-0.12.0-748856/ubuntu24/) 和 [Ubuntu 26](evidence/appimage-0.12.0-748856/ubuntu26/)。每台系统另使用打包解释器运行相同冻结测试清单的 226 项供应商协议检查：24 用时 23.80s，26 用时 24.01s，均通过。这里的 HTTP 和 WebSocket 均连接客机本地固定服务；音频是生成样本或专用虚拟 PulseAudio 设备，密钥为公开测试值。没有访问用户密钥或真实云端。

五页 GUI 在两系统两会话均实际启动，20 张截图的可见区域已人工检查：中文可读，主要页面布局和版本/会话显示正确。模型和设置页面可滚动，本次不把首屏检查称为所有滚动区域均已检查。生命周期覆盖 show/toggle/cancel/quit、IPC、配置前后未变，以及损坏配置退出 1 的预期边界。

默认 Session 的输入流水线使用真实生成音频、客机本地 TLS ASR / SSE 固定服务和实际自动输出工厂，`inputs_injected=false`；仅识别和润色服务内容受控。使用两个自有 GTK 文本目标，录音期间切焦，旧目标保持为空。普通混合样本为 `你好 InkEcho，café Ω\n第二行。`（22 个码点）；实际键盘路径全文一致，首字取消只保留前缀，延迟 1.3 秒复查不增加输入。独立事件/映射审计记录键按下/释放与恢复；不能把未采样的用户 held-key 组合也算作本轮实际通过。

Fcitx 测试使用包内官方插件和系统真实守护进程，在两个会话分别通过真实 QMP 物理按键建立 `ni` 拼音预编辑（按键前重新核对自有 actor PID、命令行、窗口活动状态，未向宿主发送按键）。提交被 `composition_active` 拒绝，零尝试，预编辑及已有正文保持；清除预编辑后普通中文正常，首标量取消只有一个字且不再增加。随后实际默认流水线全文与部分取消通过。Wayland 这里的 Fcitx 接收器是 XWayland GTK3，不冒充原生 Wayland Fcitx 资格。

无 Fcitx 前端的自有 SimpleIM 目标实际获得 `no_target`、accepted=0、unsent_offset=0、uncertain=false 后，才自动改用键盘；完整 15 字混合文本一致，取消后只增加一个字且无迟到输出。此结果仅证明明确整任务零发送的回退，不允许未知或部分投递后的重放。

### IBus 的明确限制

24 / 26 GNOME Wayland 的自有 V5 桥经安装、正常重登录和启用后，自动 IBus 路径均在原生 GTK 目标观察到精确全文 22 个码点；取消得到 3 个码点前缀，旧目标不变、延迟复查无增加。但普通结果仍是 `unconfirmed` / `ibus_delivery_unknown`，因此不能写成已确认投递或所有 IBus 应用支持。原始 Session、接收器、安装状态和禁用日志全部保留。该路径之后显式停用 V5，再独立验证 keyboard / Fcitx 回退。

### Chrome 24：本轮包的换行与焦点回归

只在 Ubuntu 24 GNOME 46 Xorg 的 Google Chrome `154.0.8037.97`、全新客机专用 profile、本地自有双 textarea 完成，不外推至 Ubuntu 26、原生 Wayland Chrome、contenteditable、DeepSeek 或 Codex。浏览器 sandbox 只在隔离 VM 内关闭，不能把此结果称为普通 sandbox 环境验收。

使用实际包 Default Session、官方插件协议 4；没有产品源码覆盖。逐项保存 Chrome 进程/可执行文件/profile 与 X11 活动窗口/输入焦点祖先证明，并与 DOM `document.hasFocus()` / active element 检查配合；没有 CDP 假焦点。11 项实际值和 1.3 秒稳定复查均通过：

| 样本 | 两目标实际收到的码点数 | 结果 |
|---|---:|---|
| 开头 LF、末尾 LF | 2 / 0（各自独立样本） | 精确匹配 |
| 中文之后连续 3 个尾部 LF | 4 / 0 | 精确匹配 |
| 同步输出、润色失败原文回退 | 7 / 0（各自独立样本） | 精确匹配 |
| 混合 Unicode / 多行 | 22 / 0 | 精确匹配 |
| 首次输出后取消 | 1 / 0 | 不再增加 |
| 尾部缓冲等待中取消 | 0 / 0 | 零发送 |
| 准备期间切焦 | 0 / 22 | 送入新目标 |
| 输出中切焦 | 1 / 21 | 后续进入新目标 |
| 开始即手选 keyboard 对照 | 3 / 0 | 精确匹配 |

[Chrome 摘要](evidence/appimage-0.12.0-748856/ubuntu24/chrome-summary.json) 和 [原始结果](evidence/appimage-0.12.0-748856/ubuntu24/output/browser-package-012/results.json)。实际输出通道证据在 `session.dispatches` 的 `route_after=fcitx`、protocol=4；同步包装会另记录一个 route 为 None 的外层条目，不能当成重复原生投递。

取消缓冲样本后保留了一条 `Future exception was never retrieved / dbus_next ... BrokenPipeError(32, Broken pipe)` 关闭警告，见原始 `suite.log`。后续目标、取消和无迟到断言均通过，浏览器/守护进程正常退出，hints 恢复；本报告不删除该警告，也不把它冒充零错误日志。父线程另行复现了 dbus-next 关闭竞态；本轮仅以这里的实际断言和清理结果限定影响。

## 复现输入、顺序与证据

原始完整证据和冻结源保留在 `dist/candidate-0.12.0-895d03b-20261030`。提交候选只拷贝公开原始日志/结果、上下文、执行命令及小型复现驱动；没有私钥、credentials.json、浏览器 profile、用户内容、TLS 私钥、完整 VM 镜像或原始配置目录。文件 SHA 清单见 [evidence-manifest.json](evidence/appimage-0.12.0-748856/evidence-manifest.json)。含原始末尾空格的文本无损 gzip 保存，以免为了 whitespace 检查改写原始证据。

1. 核验候选包与 `build-run.json`、包清单及只读父链身份；`control.py launch 24` 启动专用 child，`guest.py prepare` 校验同 SHA 并记实际动态 APPDIR。
2. Xorg 中依次运行 `guest.py gui`、`protocol`、`provider-tests`；`control.py hardware 24 24-xorg xorg-fcitx-pinyin`；`gap.py suite-keyboard`、`fcitx-zero`；24 再运行专用 `launch-browser-012.py`。
3. `guest.py cleanup`、`resource-check` 后运行 `select-wayland.sh`。新的 `*-wayland` 阶段重新 prepare / context / gui / protocol，安装自有扩展后 cleanup，再正常重登录。
4. 新的 `*-wayland-owned` 阶段重新 prepare / context，`gap.py enable`、`suite-ibus`、`disable`、`suite-keyboard`、`fcitx-zero`；26 另运行 `suite-keyboard-native`。最后再次运行 hardware 拼音套件。
5. cleanup / resource-check 后 `sudo systemctl poweroff`；`control.py wait` 保存容器状态，wrapper 完整归档 child 并做解压全流校验。24 完全停止后才启动26；不要同时启动两客机或复用旧 APPDIR。两台各阶段完整命令在顶层 JSON，驱动在 `input/*.txt`，QMP 真实按键和新鲜所有权检查在 `*-keys.json`。

这份拷贝不包含整个 frozen/framework 树或测试密钥：需依据 source commit 恢复冻结源码，按照 `tests-manifest.json` / `framework-manifest.json` 核验相应既有测试框架，并重新生成客机专用测试 SSH/TLS 密钥；不可从用户环境读取密钥。原始只读父盘和完整冻结树在持久 dist 中留存，`parent.json` / 输入 manifest 记录身份。磁盘空间不足时不得启动半成品客机。

## 失败、边界与清理

- 测试准备的第一次静态检查把 `TESTED_CANDIDATE_SHA256==...` 误认为赋值，停止于启动 VM 之前；修正为精确赋值检查后继续，未改产品或包，原失败见 `harness-setup-failure.json`。
- 24 首次启动 SSH 等待约两分钟，serial 记录 systemd-networkd-wait-online 延迟；保持同一 QEMU 进程，未用反复启动掩盖。26 Xorg 中首次 `xfce4-session --version` 因命令未导入 DISPLAY 返回 1，原上下文保留；后续实际 Wayland 环境中该命令返回 4.20.4。Xorg 当前 XFCE 会话由 user environment 和 GUI 帮助页独立确认。
- IBus 未确认及 Chrome 关闭警告如上。GNOME 46 原生 keyboard Unicode 能力不在本轮通过范围；可用 XWayland 路径是独立实际检查，不能替代其原生限制。
- 两台最终 cleanup 后检查均为：候选进程空、capability 空、锁可获取、虚拟音频空、Fcitx 服务无 owner、无本次生成的 held keys / modifiers、FUSE mount 已消失。
- 两容器正常退出 0、Pid 0、OOMKilled=false；24 child 203,096,064 字节，SHA `8e873ceb6dfc51547ca85cc3c3848bd25f82aa4997f7e3c6a99dcf5d190d2fce`，归档 52,328,762 字节，SHA `34d34e269a6a8c5ae6b57db9832ac76bc9c8422503e0d70f25d9b3f78a43f579`。
- 26 child 360,513,536 字节，SHA `8d29dbc6ef562a2c281f9d6986f97383d3e22e81f79e7631e378ecd9f6f759cc`，归档 128,060,381 字节，SHA `59d7e91af3d136b0469c451f20057bb780184dd4ed742a9284abb35ba5a97dff`。两者全流解压校验通过，QEMU exit 0。完整 archive 留存 dist，不纳入 Git。
- 未实际验证：宿主真实麦克风/真实云端、用户 Ctrl+F4/F13/F14 桌面绑定、物理录音链路、悬浮窗不抢焦点、桌面安装/自启动全流程、用户各种 held-key 状态、所有目标应用、DeepSeek/Codex 网站、26 Chrome、正常 sandbox Chrome、两系统其他桌面/输入法组合。GUI IPC toggle 不能替代物理快捷键；配置前后不变也不能代替真实云端鉴权成功。

[最终机器可读回执](evidence/appimage-0.12.0-748856/final-receipt.json) 将产品源码、同一包 SHA、两系统必要检查与完整归档绑定。最终支持说明应保留上述范围与限制。
