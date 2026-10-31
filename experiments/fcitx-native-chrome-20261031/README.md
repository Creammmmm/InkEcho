# Ubuntu 26 原生 Chrome / Fcitx 实验（2026-10-31）

这是隔离桌面上的源码夹具实验，**不是 AppImage 验收或通用兼容性证明**。测试内容为固定合成文字，不含用户页面、密钥或真实录音。产品实现未因本实验修改。测试输入目录从 `3d531d249f93b2a0f50d554c4caf3165b9e692b5` 的工作树复制；实际通过 tar 传入客机，没有对客机内所有源码文件逐一独立留存哈希，不能把此结果认作完整包身份验证。原生插件经过正式资格检查，SHA-256 `f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44`；客机系统为 Ubuntu 26.04.1、GNOME Wayland、Fcitx 5.1.19，Chrome 154.0.8037.97，Chrome 二进制 SHA-256 `6c792041b07547a662e1b17974d1dc34a3db630379b45d9d89ddd7e3e68cc587`。Chrome 使用自有本地页面、独立临时 profile，`--ozone-platform=wayland --enable-wayland-ime --wayland-text-input-version=3`，未传入禁用浏览器沙箱的选项；本实验没有独立核实每个渲染进程的 sandbox 状态。

浏览器禁用 DISPLAY，记录了 Wayland compositor、toplevel 和 keyboard 事件，以及页面焦点。在一次性客机中预先安装插件，配置 Fcitx 自动启动，重启显示管理器并重新登录，Fcitx 的 DebugInfo 观察到 `program:gnome-shell frontend:ibus`。页面输入走 compositor 的 text-input-v3 与 GNOME 的 IBus 兼容前端。夹具临时设置系统用户 manager 的输入法提示，使用真实 DefaultAutoOutputRouter/Fcitx 桥；恢复时按测试前值还原。

## 接收对照

表格为同一浏览器内，每种组合各运行两次；夹具每次向**同一输出会话**逐标量调用真实路由，0/10/20/40 ms 是夹具在调用间人为等待，并非现有接收窗口等待配置，也不是目标应用确认。切焦模式在第一个输入事件中请求页面从 A 切到 B，所有结果末态确认 B 焦点；静止样本末态为 A。每格分母为 2，括号为实际 A/B 接收长度。全部32例产品发送数均等于计划数，且无路由错误；该数**不代表页面已经收到**。

| 切焦 | 字数 | 0 ms 精确次数（实际长度） | 10 ms | 20 ms | 40 ms |
| --- | ---: | --- | --- | --- | --- |
| 否 | 20 | 1/2（20/0、19/0） | 2/2 | 2/2 | 2/2 |
| 否 | 200 | 0/2（163/0、193/0） | 2/2 | 2/2 | 2/2 |
| 是 | 20 | 0/2（1/18、1/15） | 2/2（1/19） | 2/2（1/19） | 2/2（1/19） |
| 是 | 200 | 0/2（1/180、1/185） | 2/2（1/199） | 2/2（1/199） | 2/2（1/199） |

原始每次页面输入事件、合成期望文字、输出时长、计数与页面焦点见 [browser-matrix-receipt.log](browser-matrix-receipt.log)，脚本见 [browser-matrix.py](browser-matrix.py)。10/20/40 ms 结果只是有限样本，无法证明可靠阈值。此前一次原样整段调用的 200 字短暂切焦样本，产品报告发送200，页面仅收到174且顺序不符，见 [browser-switch-receipt.log](browser-switch-receipt.log)；静止整段调用同样不精确，见 [browser-long-receipt.log](browser-long-receipt.log)。这些反例不能归因于切焦本身；不能重试或重放已尝试的文字。受控等待有改善，但无法由现有证据推出任务安全、跨应用顺序或接收确认；还需分析 Fcitx、GNOME 与 Chrome 各段边界并针对真实产品路径、双系统验证任何修复。

## 组词、取消与失败

QMP 向客机自有 Chrome 焦点发送虚拟硬件键 `n`、`i`，页面先收到真实 composition 事件。自动 Fcitx 在组合期间拒绝输出、尝试计数0，页面组合文字和事件不变；空格完成“你”，随后正常输出“甲乙丙”。[最终记录](hardware-guest.log) 与 [虚拟键回执](hardware-key-receipts.json) 已保留。首轮 [失败记录](hardware-preedit-r1.log) 因夹具错误假定组合文本不在 textarea.value，而 Chrome 实际将其包含在 value；只修正此断言后重测，未改变产品路径。

手选 Fcitx 首字后请求取消的独立样本，只收到“甲”，延迟1.3秒无尾部，见 [取消记录](browser-cancel-receipt.log)。自动模式普通3字通过，见 [登录后记录](browser-login-r2-receipt.log)。

先前的独立客机在 ibus-daemon 和 Fcitx 同时运行时，Chrome 原生 Wayland 目标得到 `fcitx_no_target`、0发送。额外实验停止 ibus-daemon，确认 IBus 服务的 owner PID 就是 Fcitx，但仍观测到 Fcitx 内无 GNOME 输入上下文；重登录后才建立此上下文。初次浏览器夹具曾因候选目录权限失败，另有一次因选择错误的 data_home 失败，均发生在目标发送之前。早期实验原始数据暂存 `/var/tmp/inkecho-fcitx-native-chrome-1031` 和 `/var/tmp/inkecho-fcitx-native-ibus-1031`，不以这些不完整配置宣称 Chrome 不支持。

## 复现和恢复

使用与本实验相同的隔离 Ubuntu 26.04.1 快照、只读父盘、独立 RAM 写层和隔离网络；不要对宿主现有桌面、真实应用或用户输入法发送测试键。客机中保存原 Fcitx profile，执行 [setup-login.py](setup-login.py) 安装通过资格校验的候选插件，建立临时输入法提示及 Fcitx 自启动，正常重启显示管理器并重新登录。确认 GNOME Shell 的 IBus 输入上下文确实属于 Fcitx，核对 Chrome 和插件哈希，使用本目录的自有页面脚本与 QMP 控制器运行单项和矩阵；脚本还依赖该隔离客机的源码及 `dbus-next`、`websockets` 测试依赖。不要绕过焦点、组词或计数断言。

完成后通过 [cleanup-login.py](cleanup-login.py) 停止测试 Fcitx、停用自有插件、恢复 profile、删除临时自启动和环境文件，并重新登录。独立 [restore-check.log](restore-check.log) 显示原 ibus-daemon 恢复、没有 Fcitx 进程和测试配置。随后客机正常关机，QEMU 和容器退出0、无 OOM；写层归档 SHA-256 `931ef9061f0c7f7c68610fc0d8aad5f535b43be9353b2ea24d08f0b51b8041af`，完整解压流校验通过。此处未测试 Ubuntu24、真实用户网站/物理键盘/云服务、其他输入法、应用间多窗口切换、任务替代或竞态，也没有验证已经确认接收的机制。
