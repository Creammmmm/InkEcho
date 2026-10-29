# Ubuntu 26.04 候选包定向桌面测试

2026-10-29，候选 AppImage 版本 0.10.2、SHA-256 `207b97eb667e5439137b51963a2aa09515c7ba50a83496d9c10070e989252685`；采用同一 AppImage，在隔离 Ubuntu 26.04 QEMU 写时复制快照内分别执行 GNOME 原生 Wayland 和 XFCE X11。容器不连接外网，原系统盘和基础镜像只读；实验使用自有 GTK3 输入控件、合成固定音频和固定本地转写，不读取用户正文或凭据、不接触剪贴板，包内代码**未覆盖**。测试仅观察输入路径，不是完整产品验收。

包由 `--appimage-extract` 解包后调用包内 Python；包内 `app.py` SHA-256 `af654c3a436a05a1c10cb3450ec0af851e6b74414e502c2b12425149a85d4605`，`streaming_output.py` `147fff1ed12852c83a34caca13368162a2dd5b7047ef7fcb41c9b249d911cdfd`，`platform/ibus.py` `a6a7e19984fc5dabb43bca9ee844a32beaf88997fe6078fa777f0df2fe5f2ac5`，`platform/output_router.py` `6056b6073b2fc7a8564f61f01cf6db2c4c35ad15fef41ba21672c5508630d58b`。`loginctl` 验证 Wayland 和 X11 会话分别为 active、对应 type；X11 是 XFCE，`run.sh.txt` 却强设 `XDG_CURRENT_DESKTOP=ubuntu:GNOME`，故与实际桌面不一致，这一测试不能证明桌面识别配置正确。X11 会话登录配置只在快照修改，客机关闭后销毁。

Fcitx 测试将随包扩展安装到隔离私有 Fcitx 配置，分别以 auto、fcitx 运行正常和首字后取消，然后以 simple 输入控件测试 auto 的零前缀回退：

- `wayland-result.log`：auto 和 fcitx 正常样本均准确收到 200 字且 succeeded，取消样本均保留首字、cancelled；simple 样本 Fcitx 报 `no_target, accepted=0, offset=0, uncertain=false`，经 `hybrid_connect/hybrid_authorize` 回退准确收到 200 字且 succeeded。原脚本 `passed=false` 是旧断言只识别 X11 `keyboard_insert_started`，未识别 Wayland hybrid，不改写原日志。
- `x11-result.log`：auto 和 fcitx 正常样本均准确收到 200 字且 succeeded，取消样本均保留首字、cancelled；simple 样本零前缀 no_target 后走键盘，准确收到 200 字且 succeeded。五个原脚本断言均 passed。

IBus 只在 GNOME Wayland 显式选择模式下测试：在隔离快照安装包内扩展，重启后手动启用并核对 ACTIVE；原客机未受影响。`ibus-full.log` 自有 GTK 控件准确收到固定 200 字、记录 200 次 Commit 发起，应用报告 `ibus_delivery_unknown`、提示用户检查、结果 failed。`ibus-cancel.log` 首次字符到达后向发送进程发 SIGUSR1，最终收到前 2 字、记录 2 次 Commit、cancelled，未观察到后续字符或重放；第二字符可能已在取消信号到达前派发。`ibus-target.py.txt` 继承 Fcitx 专用旧断言，因此两次 `passed=false`；以上依据原始 JSON 内容、Commit 数和实际结束事件独立核对，不改写日志。此测试无法证明任意目标接收或解决虚拟焦点问题。

复现：在隔离客机把候选包放在 `/tmp/inkecho-r4-test/InkEcho-0.10.2-x86_64.AppImage`，将本目录带 `.txt` 后缀的 run、Fcitx sender、Fcitx target 复制到 `probes/run.sh`、`probes/sender.py`、`probes/target-focus.py`，在对应会话执行 `bash probes/run.sh 207b97eb667e5439137b51963a2aa09515c7ba50a83496d9c10070e989252685 wayland` 或 `x11`。IBus 测试采用单独的 sender 与 target 覆盖 probes 同名测试脚本（不覆盖包代码），将包内 `inkecho/platform/ibus_candidate` 的四个文件放到临时用户扩展目录、重启并启用；设置运行环境 `XDG_RUNTIME_DIR=/run/user/1000`、`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`、`DISPLAY=:0`、`WAYLAND_DISPLAY=wayland-0`、`XDG_SESSION_TYPE=wayland`、`XDG_CURRENT_DESKTOP=ubuntu:GNOME`、`GDK_BACKEND=wayland`、`GTK_IM_MODULE=ibus`、`XMODIFIERS=@im=ibus`，用系统 Python3 分别运行 target 的 `full` 与 `cancel`。扩展及会话配置仅可在一次性隔离客机中改动。

未覆盖：Ubuntu 24、GNOME X11 下 IBus、IBus 自动选择、虚拟目标与提交切焦竞态、Chrome/终端、实际麦克风与云端、物理快捷键、真正首次授权、全部 UI 和桌面集成，以及完整双系统包验收。正常关机后 docker wait=0，容器及写时复制磁盘已删除。该包仍为候选。

日志 SHA-256：`wayland-result.log` `d9094964acef9a9136d0c8fdaf988cd0ed0cacd46d945975e9292c12b2d6fb8f`；`x11-result.log` `646b212309868968beb69eff2a34548d483ac667a988efb99ac5907edd7bb105`；`ibus-full.log` `55f8ab45d6b29da896a0999498b7994ecf5bad729ec0e99539f7190dfabb637a`；`ibus-cancel.log` `1c3ecb09a3ae60cd4d6ca8895ddf874fe632af65c8de407ed4fd2bb0e3175073`。
