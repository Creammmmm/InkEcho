# Fcitx 运行时版本与生产路由：双系统隔离测试

2026-10-28，将 Ubuntu 24.04 构建的候选输入桥和本轮工作树的 Python
源码复制到独立工作副本，测试实际系统框架检测、安装校验、运行时版本
查询和 `OutputRouter`。候选 `libinkecho.so` 的 SHA-256 为
`532ef632385bfe9ae3b76312b74874a7cc562c58435bb07f430e704179ebd139`；
构建来源及独立插件测试见 [候选验证记录](fcitx-runtime-version-candidate-validation.md)。

副本中的 `fcitx5_staging.py` **仅修改候选摘要**以指向该实验二进制，
源码哈希为 `26721345632ac8a7de8fb082ee0b15c87ef977ab0b287a87677905198a5825e0`。
实验时工作树的固定载荷和固定摘要均未替换；后续已集成该候选，仍须
完成最终包验收。实测各 Python 模块的字节副本和
SHA-256 校验表保存在 `experiments/fcitx-runtime-version/frozen-route/`；
其中 `text_normalization.txt` 属于 `inkecho` 根目录，其余属于
`inkecho/platform`。测试使用 `dbus-next` 0.2.3。

| 隔离桌面 | 运行时版本 | 实测结果 |
| --- | --- | --- |
| Ubuntu 24.04，GNOME Xorg，自建 GTK 控件 | Fcitx 5.1.7 | 自动和显式各输入一字，取消和服务更换均无额外文字 |
| Ubuntu 26.04，GNOME Wayland，自建 XWayland GTK 控件 | Fcitx 5.1.19 | 自动和显式各输入一字，取消和服务更换均无额外文字 |

两次使用相同候选与脚本；均通过当前图形会话的 D-Bus 和真实系统
框架检测。输入甲、乙后，控件精确为甲乙；取消第三字返回
`fcitx_cancelled`。在另一个任务准备后停止原 Fcitx 并启动新进程，
旧连接发送返回 `fcitx_delivery_unknown`，控件没有收到丁，也没有
重放。键盘使用一旦被调用就抛错的测试替身，故本实验不验证真实键盘。

26 前两次尝试因客机默认 umask 导致测试目录和文件可被同组写入，被
产品安装校验拒绝，未成功选择输入桥；收紧权限后完整重试通过。
26 实验后原输入法环境恢复、Fcitx 服务 owner 消失，自有进程和临时
目录清理，客机正常关机、容器退出 0。24 结束后 Fcitx owner 和进程
消失、输入法环境恢复为 IBus、临时目录清理；随后将仍运行的客机交给
另一项实验继续验证，其最终关机由接手者负责。

## 保留与复现

原始实测脚本 `experiments/fcitx-runtime-version/route_probe_measured.txt`
SHA-256 `ebface886f5a2db0436e5252aa271ac09d6c28c48ac456ea5f2ffd404d977a4b`；
运行脚本 `run_route_probe.sh` SHA-256
`ba32b18eb9c5ee730736bf6ae852a1f6630c02917e3be1655fb4b90e55b62b83`；
自有 GTK 窗口 `experiments/ibus-gnome-shell/auto_detection/target.py` SHA-256
`d5ecb06be3fd9dfaa5c2e249bb42f2c0702e422624a9bb393f472cdd8317e76c`。
同目录 `route_probe.py` 在实测后仅调整格式，调整版尚未重跑。可在
`frozen-route` 目录执行 `sha256sum -c SHA256SUMS` 检查保留模块。

在一次性、已登录图形桌面的隔离客机中，准备 `/tmp/inkecho-route`：
放入上述候选、`dbus_next` 0.2.3、相应 `inkecho` 源码目录；用保留模块
替换对应 `.py` 文件；将原始实测脚本复制为 `route_probe.py`，并放入
`run_route_probe.sh` 和 `target.py`。以测试用户设定该会话的
`XDG_RUNTIME_DIR`、`DBUS_SESSION_BUS_ADDRESS`、`DISPLAY` 和
`XAUTHORITY` 后运行 `/bin/sh /tmp/inkecho-route/run_route_probe.sh`。
脚本拒绝替换已运行的 Fcitx，临时修改图形用户管理器的输入框架环境并
在退出时恢复，因此不可在宿主用户桌面或共享会话执行。

## 局限

本结果不是 AppImage 实际包验收，也不证明原生 Wayland、真实键盘后备、
长文本、真实程序或发送过程中服务消失等情况。服务更换发生在任务准备
之后、开始发送之前；无收到确认的已尝试请求仍不得重放。两个桌面使用
同一原生二进制，但不代表最终 AppImage 已构建或完成双系统验收。
被忽略的实验目录中的候选文件不保证长期保留；需按候选验证记录重建并
核对摘要，不能用不同哈希的产物替代已测候选。
