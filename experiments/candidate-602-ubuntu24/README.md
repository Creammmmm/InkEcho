# 602 候选包 Ubuntu 24 X11 / Wayland 输入实验

2026-10-29：Ubuntu 24.04.5 / GNOME Shell 46.0，先 active X11 后 active 原生 Wayland；同一候选 AppImage `InkEcho-0.10.2-x86_64.AppImage` 的 SHA-256 均校验为 `602dab02b4837bb8d30c864dbe50d0413d58d53afb53d9695c7f96f50cdfb756`。独立 QEMU `-snapshot`，系统盘、基础盘和 seed 只读挂载，容器无外网、不挂密钥，仅宿主用客机专用测试 SSH 密钥；只在快照内切换 Wayland。Fcitx 使用临时配置和应用输入桥，自建 GTK 控件及固定合成文字，不切换输入法引擎、不读取个人正文或剪贴板。包源码没有覆盖；运行包内 Session 和输入路由，录音/识别是替身，包外测试 sender 使用监测包装。候选包内 `fcitx5.py` 在两会话均为 `c8918f6235325036a4bf605edc76579b2813e71d04343ca41e5edec981a7c6b5`；客机实测 sender 哈希见 `shutdown.log`。

| 会话 | 自动 / 显式 Fcitx | 零前缀模拟键盘回退 | 额外所有权替换探针 |
| --- | --- | --- | --- |
| X11 | 两种模式各正常 200 字准确、取消后保留首字，均报告 passed | 正常 200 字、受控切焦 1+199、取消后首字，均报告 passed | 未通过，首字后 delivery_unknown |
| Wayland | 两种模式各正常 200 字准确、取消后保留首字，均报告 passed | 正常、切焦、取消样本均失败，接收 0 字；状态 3 后 `no_target` 已提交 0，再报告 `unsupported_compositor` | 未通过，首字后 delivery_unknown |

逐样本原文及事件见 `x11.log`、`wayland.log`。切焦是在测试控制下暂停发送，第二窗口确认焦点后继续；取消由信号触发，不等于物理 Esc。所有权替换样本不证明替换服务已成功获取名称：已接收首字且结果不确定，程序停止并报告未重试；不得把它写为替换测试通过。桥状态 1 是提交状态，不是接收回执；本实验同时记录自建控件的实际内容。脚本会捕获部分子命令失败，外层退出码 0 不代表所有场景通过。

复现须在一次性 Ubuntu 24 图形客机中将本目录三个 `.txt` 脚本去后缀放到 `/tmp/inkecho-r4-test/probes/`，候选包放入该目录，按会话运行 `bash probes/run.sh <SHA> x11` 或 `bash probes/run.sh <SHA> wayland`，并核查每个 JSON 的内容、事件与 `passed`。脚本会在隔离快照修改临时 Fcitx 服务和环境，只适合独立测试。包外 sender SHA-256 `1264e9dff6ecd447a7b696b5b29ec230a7ec64478d1b69249fe7a6ba6f20930e`，`target-focus.py.txt` `aec02fa1891be8e814f676d690b86fe6d91c0d50259e21b68cf315ce34648eba`，`run.sh.txt` `433a3c1141d5de498c26b0d607f2b7171b33201ca512b3fddd927ddcd1dd4475`；日志分别 `e3cbbfe822b8c4f61b9eb7877736e7ba159b667263df3a9daffa346b67399ecd` 和 `ae2732e1b0af791ac63e3ea041657c3849a4d94bdecae244f385a01f380f45f9`。

客机 sudo poweroff 后 docker wait=0、ExitCode=0、OOMKilled=false，容器已删除，快照中未逐项恢复配置。没有截图。未验证真实麦克风、云端转写、物理快捷键、浏览器、真实终端、IBus 自动选择、全部系统组合或完整包验收；不能据此发布或宣称 Wayland 通用回退可用。
