# 602 Ubuntu 24 Fcitx 服务真实替换复测

2026-10-29 在 Ubuntu 24.04.5 GNOME 46 的隔离 QEMU 快照分别测试 X11 和原生 Wayland；系统盘、基础盘、seed 只读，容器无外网且不挂密钥，仅宿主使用专用客机 SSH 测试密钥。Wayland 只在快照内启用。候选 AppImage SHA-256 `602dab02b4837bb8d30c864dbe50d0413d58d53afb53d9695c7f96f50cdfb756`，两次运行都校验；包源码没有覆盖，`fcitx5.py` 哈希均为 `c8918f6235325036a4bf605edc76579b2813e71d04343ca41e5edec981a7c6b5`。使用私有 Fcitx 与配置、自建 GTK 文本控件和固定合成文字，录音及识别为替身；未访问用户正文或剪贴板。

采用 `experiments/fcitx-owner-replacement-ubuntu24` 修正探针：首个真实桥 Commit 状态为 1 后，查询原服务唯一 owner，结束隔离 Fcitx 进程，由另一测试 D-Bus 连接申请服务名；验证新 owner 与替代连接一致、原唯一名称已消失。替代连接不实现输入桥。

* `x11.log`：原 owner `:1.94`，新 owner `:1.112`，旧连接已不存活；目标只收到“风”，路由报告 `owner_changed`、accepted 1、停止并报告部分输入，日志无键盘回退或重放；测试判定 passed。
* `wayland.log`：原 owner `:1.94`，新 owner `:1.115`，旧连接已不存活；目标只收到“风”，同样 `owner_changed`、accepted 1，日志无键盘回退或重放；测试判定 passed。

Wayland 测试启动命令误将查询固定为 session 6，日志记录该查询失败；同一日志的会话列表显示当前桌面为 session 7，测试后 `shutdown.log` 核实 session 7 为 active/wayland。不能用错误查询本身证明会话类型。客机在 sudo poweroff 后容器 `docker wait=0`、`ExitCode=0 OOMKilled=false`，容器已删除；原盘只读，快照内未逐项恢复。没有截图。

这是一次由测试包装器控制在首个 Commit 响应之后更换服务的样本，不覆盖请求在途所有竞态、不同应用、真实麦克风/云端、物理按键或完整包验收。桥状态 1 是提交状态，目标接收内容由自建控件独立记录。

隔离复现：把本目录 `run.sh.txt`、`sender.py.txt`、`target-focus.py.txt` 去后缀放到 `/tmp/inkecho-r4-test/probes/`，同哈希候选放到其父目录，分别在 active X11/Wayland 会话运行 `bash probes/run.sh <SHA> x11` 或 `wayland`。脚本会结束其自己启动的 Fcitx 并替换该隔离会话的 D-Bus 服务名，绝不可在真实用户桌面运行。包外实测 sender SHA-256 `2ff7a5bd81e7a66bb25488b3d3cf4b49f68d7ec3b627ac4ea439b972ce8b8b53`，客机关机记录再次核实；`run.sh.txt` `91f998564a04f0733d923a86413175c671646448ebd7b51e234a2b6cbf907d24`，`target-focus.py.txt` `aec02fa1891be8e814f676d690b86fe6d91c0d50259e21b68cf315ce34648eba`；`x11.log` `18eb3b0cb7364bfc8141f4ff4abc5f3fb539ec9e5a1420c7644aeac9bc8a45fe`，`wayland.log` `136b8d94221752f535ce04f2c47faac9dffaca6e7dc6ff9b74b6e98cfbd8d32f`。
