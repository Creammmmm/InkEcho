# 输入与兼容性页面隔离渲染

2026-10-29，在 Ubuntu 24.04.5 GNOME X11、Ubuntu 24.04.5 GNOME Wayland 和 Ubuntu 26.04.1 GNOME Wayland 会话分别渲染 `CompatibilityPage`。两个一次性 QEMU 快照的原系统盘、基础盘、seed 只读，容器无外网、不挂密钥，仅宿主使用客机测试 SSH 密钥；Ubuntu 24 的 Wayland 只在快照内启用。测试候选包 SHA-256 `602dab02b4837bb8d30c864dbe50d0413d58d53afb53d9695c7f96f50cdfb756`，解包后仅用当前工作区 `information.py` 覆盖该单一文件用于测试界面；覆盖文件 SHA-256 `cbaeadf908c6ca0ca2e31b89a81750b99ea1640db7ddde098aabdb321bf993f9`。不是对原包或最终包的完整验收。

以 Qt 实际 xcb 或 wayland 后端创建真实页面控件，窗口包含内存假 Session 和假 Settings，未连接输入服务或读写用户设置。三个样本分别报告桌面系统/会话、自动模式、X11 映射等待与绘制反馈超时均 40 毫秒；依次程序化选择自动、模拟键盘、Fcitx5、IBus，模拟存储值及页面状态提示匹配；改变数字到 73 和 74 后模拟存储反映新值。此测试只说明控件与内存替身交互，不证明真实配置持久化、输出框架检测、输入功能或接收窗口帧同步。页面明确标注两个设置是 X11 参数：不能将其称为跨后端统一 40ms 或目标应用完成绘制的确认。

`ubuntu24-x11.png`、`ubuntu24-wayland.png` 和 `ubuntu26-wayland.png` 是 `CompatibilityPage.grab()` 生成的整个页面像素图，包含合成状态，无用户内容；并非完整应用窗口、实际屏幕截图或人工点击测试。检查到的文案展示了 X11 与 Wayland 的条件限制，没有把全部环境宣称已支持。两份 Wayland 日志保留 Qt textinput disableSurface 提示，运行脚本退出 0。仅检验当前页面宽度下的呈现，未验证小屏缩放、实际托盘、真实授权按钮或各输入功能。

复现只在隔离图形客机中：将 `probe.py.txt` 去后缀复制到 `/tmp/inkecho-ui-test`，解包上述同哈希 AppImage，将 `information.py.txt` 覆盖解包目录 `packages/inkecho/ui/information.py`，以正确的 Wayland 或 X11 会话环境以及包内 Python/PYTHONPATH/LD_LIBRARY_PATH 运行 probe。探针程序化修改内存替身，不改变桌面用户配置。两个客机分别 sudo poweroff，容器 docker wait=0、ExitCode=0、OOMKilled=false，容器已删除；快照内未逐项恢复，原盘只读。

`probe.py.txt` SHA-256 `1759e6fcbc5d38e3172b843b4f5ba5b6aeee351fc53c5043b961cab96ba722f8`；三张图依次 `a2786836df8c93e81b3dc526e14958e8ecdaded1156d3ec0a8293aa3a95becbe`、`26552ab3bec9958ac3601facfb2abcc1dab5be68b1cbf29f9f5a60e9fb8d7e49`、`1a9dae730ff2c2c4f5563b0eeb20c5e3dfe317efb7accc47638b2d6f`。
