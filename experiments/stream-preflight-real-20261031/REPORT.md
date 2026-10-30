# 真实 Fcitx 的流式预检失败与重入：隔离探针

2026-10-31，在本机使用 `b11f1d4a54cf963894bbab25b5ae5d9250b22bfd` 源码运行隔离探针。Python 实际导入的 `output_router.py` SHA-256 为 `dcf2ae288e96e8cef2f6488d77dccbc1c7d7fe16634d2105ef22a1b1473a3499`。真实 Fcitx 来自先前准备的 Ubuntu 软件包解压目录，其可执行文件 SHA-256 为 `f55185cbcaa95dd9185837abe895e0f714e3992282d61f3f2ba9452ee028c38c`。实验不安装软件包、不修改产品代码。需要现有已按 `experiments/fcitx-xwayland-gtk-private-20261030/README.md` 准备的 Fcitx 解包环境；本地执行 `bash dist/stream-preflight-real-20261031/run.sh`，复核结果在 `result-verified.log`。

探针使用 bwrap 私有 PID/网络命名空间、私有 D-Bus、临时 HOME/配置与运行目录，禁用 Fcitx clipboard 插件；未连接宿主用户总线或显示。根文件系统为只读绑定而非保密沙箱。私有总线回报的服务 owner PID 与由探针启动的真实 Fcitx 进程一致。该服务未加载 InkEcho 插件，`/inkecho` introspection 返回错误；测试用状态固定为 `unknown`，检测器返回实际私有总线 owner，键盘是计数替身。

预检失败后，真实桥连接和中止各调用一次，抛出 `input_capability_unknown`；调用方在同一 scope 捕获后重试输出，返回 `output_failed`，真实桥 insert 和键盘替身发送均为零。取消样本在真实桥收到服务 owner 查询回复后，由测试子类刻意暂停，再对运行任务执行 `cancel()`；捕获 `CancelledError` 后，同一 scope 的重试同样返回 `output_failed`，桥与键盘替身均零发送。两样本随后启动新的显式键盘任务，替身各接收一次调用，说明后续任务可继续；这不证明真实键盘授权或文本接收。测试未观察实际插件 Commit，也未以完整 Session 驱动识别、润色或图形窗口。

最终脚本 SHA-256：`run.sh` 为 `8d8686e82cd06569b8c75827ebb80d63401817151c687c0d3e600c48a15aaa32`，`probe.py` 为 `166176dac14109b5b8c2fe26ca941ca7a3e8cb77cba8a46d353a4d4a396246b0`，`result-verified.log` 为 `ad8b6608df0349ae09ec38136b31bc87edfe9e849bc0630f43fa4a2e88e80ea1`。运行以 0 退出，外层脚本 trap 结束自启 Fcitx，bwrap `--die-with-parent` 清理命名空间，独立扫描 `/proc` 未发现上述 Fcitx 可执行文件进程。该次扫描未覆盖系统崩溃或所有清理故障路径。

此结果是私有总线中的真实服务与受控客户端交互，不是 Ubuntu 24/26 桌面实际包验收；状态和检测器由夹具控制，取消时序人为构造。未验证完整 Session、真实输入法预编辑、目标窗口、Portal 授权或真实文字显示。不能据此扩大兼容支持声明。
