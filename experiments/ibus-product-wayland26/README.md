# IBus 应用会话结束提示：Ubuntu 26 Wayland 隔离试验

2026-10-29，使用 Ubuntu 26 GNOME Wayland 一次性写时复制客机、无外网容器，原客机及基础镜像只读。候选 AppImage SHA-256 `f6ceb6311069f85b180bafd446f546247b5e592735ba26035455a571c5eb5164`，解包后将本地 `src/inkecho` 覆盖包内同名目录（源码归档 SHA-256 `5afeddff85737830f945f86c5d410030cfd37bd442abdd48e30591947cff3a2d`），因此不是最终包验证。会话代码 `app.py` SHA-256 `af654c3a436a05a1c10cb3450ec0af851e6b74414e502c2b12425149a85d4605`，`streaming_output.py` 为 `147fff1ed12852c83a34caca13368162a2dd5b7047ef7fcb41c9b249d911cdfd`，`platform/ibus.py` 为 `a6a7e19984fc5dabb43bca9ee844a32beaf88997fe6078fa777f0df2fe5f2ac5`，`platform/output_router.py` 为 `6056b6073b2fc7a8564f61f01cf6db2c4c35ad15fef41ba21672c5508630d58b`。测试环境和参数见 setup.sh.txt 及下文；脚本仅可在隔离客机中运行，因为它会启用 GNOME 用户扩展。

在客机设置临时扩展并重启，使用 `gnome-extensions enable inkecho-ibus-v2-prototype@local.invalid` 后查到 ACTIVE；会话 `loginctl` 报告 `Type=wayland, Active=yes`。运行 `setup.sh.txt` 使用 source.tar 覆盖并安装实验扩展。重启清空 /tmp 后重新复制 AppImage、源码包与两个脚本并运行 setup。运行前设置 `XDG_RUNTIME_DIR=/run/user/1000`、`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus`、`DISPLAY=:0`、`WAYLAND_DISPLAY=wayland-0`、`XDG_SESSION_TYPE=wayland`、`XDG_CURRENT_DESKTOP=ubuntu:GNOME`、`GDK_BACKEND=wayland`、`GTK_IM_MODULE=ibus`、`XMODIFIERS=@im=ibus`，然后使用系统 Python3 分别执行 `target-focus.py full` 和 `target-focus.py cancel`。探针创建自有 GTK3 文本框，启动包内 Python 执行 `sender.py`，模拟固定录音和本地转写，不读取真实音频、凭据、云端或用户正文。使用显式 IBus 模式。

- `ibus-full.log`：自有控件确实收到 200 字，内容与固定测试文字完全一致；记录 200 次 Commit 发起。最终出现 `ibus_delivery_unknown`、中文检查提示及 `finished=failed`，未发生自动重试。这里只证明这个控件的这个样本，面板调用仍不保证任意目标收字。
- `ibus-cancel.log`：控件首次变化后向发送进程发出 SIGUSR1，最终正文为固定文本的前 2 字、出现 2 次 Commit 发起、`finished=cancelled`。第二次 Commit 可能已在取消通知到达发送进程之前派发；本次没有观察到后续字符或重放。未测任意线程竞态，不说明已派发字符可撤回。

原目标脚本从 Fcitx 实验复用，其 `passed` 字段依赖 Fcitx 特有的事件及成功状态，两个 IBus 试验均报 `passed=false`；这是不适用的旧判定，未改写日志。上述结果根据原始 JSON 的自有控件正文、Commit 次数与会话事件独立核对。首次无日志完整运行也输出了 200 字；正式留存为第二次运行。本试验未覆盖虚拟焦点、焦点并发切换、其他应用/输入法、24.04、真实麦克风、全自动检测、最终 AppImage 或双系统验收。IBus 的虚拟焦点仍可能使面板调用未送达真实目标，因此不应据此启用自动路由或宣称 IBus 通用可用。

原始日志 SHA-256：`ibus-full.log` `6219868671a3fdc79e57efbb1dc4630e773a83bd3c0bfa370002ac6b86011a7f`；`ibus-cancel.log` `a61464dfe8328c68468d5a02d59877b8fbf8ce221f42236a2d8b07ba2649c1f3`。
