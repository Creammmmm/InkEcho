# InkEcho 0.15.0：自动 IBus 与接收等待补充验证（2026-10-30）

实际发布包 SHA-256 `94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a`；源码版本 0.15.0、提交 `76aeb33`。两个单独的隔离客机顺序运行，均使用同一个只读包；包内模块来源和清单由 `guest.py prepare` 检查。录音与提供商使用合成 fixture。未访问剪贴板。

## 实测结果

- Ubuntu 24.04.5 / GNOME 46 原生 Wayland，正常沙箱 Chrome154，显式安装并启用包内 GNOME owned 扩展，测试配置 `auto`。textarea 与 contenteditable 中，混合 22 码点（含中文、重音、希腊文与换行）准确；首字符后取消只收到 1 码点，输出前切换至同窗口另一控件收到 0/22。textarea 待发送取消收到 0。逐次 dispatch 记录 `ibus`；整次会话依协议报告 unconfirmed，不能当作目标回执。
- Ubuntu 26.04.1 / GNOME 50.1 原生 Wayland，配置和 Chrome 场景同上，textarea 与 contenteditable 均得到同样结果，textarea 待发送取消 0。两系统各自独立的 `results.json` 记录实际焦点、DOM 字符、路径和协议尝试。名称以 `browser24` 开头的 24 文件仅对应 24，26 文件名对应 26；输出前切换是同窗口控件，不代表跨应用切换。
- Ubuntu 26 原生 Wayland Chrome 使用 Fcitx5 时，auto 先调用 Fcitx，返回 `no_target / accepted=0 / uncertain=false / unsent_offset=0` 后转 keyboard；混合文本、取消及输出前控件切换通过。Chrome 进程 maps 样本未发现 Fcitx 模块；不能算 Fcitx 原生直接投递通过。
- Ubuntu 26 / XFCE Xorg，实际包键盘路径、真实 GTK3 TextView、仅观察型埋点。保存 20/40/80ms 设置，抑制目标绘制提示并正常输出 8 个 `a`，各档各 7 次 eligible 等待分别为 20.37–20.80ms、40.18–41.03ms、80.13–81.08ms；字符准确且无迟发。取消样本从进入等待到退出共约 5.16–5.23ms；测试在进入等待约 5ms 后触发取消，该数值不是取消到退出的延迟，未在取消后继续按键；测试窗口切换后的剩余字符进入新焦点。切换期间的绘制提示使 40/80ms 样本约 33ms 提前唤醒，这不代表等待上限精度。等待上限和绘制提示均不是目标应用已处理或显示的确认。

## 环境、复现与限制

`raw-byte-archive.json` 保存了逐文件原始字节的 gzip/base64、解码大小与 SHA-256；解码并核验后，可查看实际宿主命令、包审计、被更改为 auto 的隔离测试脚本、DOM 证据与时序事件。独立运行目录为 `dist/auto-audit-0.15.0-20261030`；同目录的二进制包、客机父镜像、浏览器及停止快照并不包含在本补丁中，不能将本补丁视为完整系统镜像。两份测试分别使用实际包内部 Python/模块，未覆盖包内源代码。测试代码复制旧验收入口并将所选输出模式改为 auto；时序脚本仅改包版本与哈希，另增加无绘制提示正常输出样本。

24 客机测试中输出末尾出现一次 dbus-next `BrokenPipeError` 异步关闭告警；不掩盖或视作成功确认。26 恢复首次因使用未创建 mount.json 的 stage 而失败，第二次资源审计通过后因以 xorg stage 校验已恢复的 Wayland 而断言失败；两次未重跑输入，之后分别使用正确 stage 完成资源审计与会话/输入源检查。两客机扩展文件与设置恢复、包挂载消失，残留进程/能力文件/按键/虚拟音频无异常，Fcitx 服务 owner 不存在；QEMU 和 Docker 均正常退出 0、无 OOM。停止快照完整流解码验证结果分别见各 `output/ram-overlay-archive.json`。

未测试 24/26 的 Xorg IBus 正向、本轮 Wayland Fcitx 直接正向、24 键盘等待上限、本机物理快捷键/麦克风、真实云端、任意浏览器或应用、真实跨窗口输出及所有取消竞争。现存 GNOME owned 原生到 XWayland 中途安全停止问题不因此解决；完整目标和全部组合尚未验收。
