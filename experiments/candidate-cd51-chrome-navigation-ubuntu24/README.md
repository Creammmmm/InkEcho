# cd51 Ubuntu 24 Chrome 本地服务与 CDP 导航诊断

2026-10-29，继续 `experiments/candidate-cd51-chrome-diagnostic-ubuntu24`。独立 Ubuntu 24.04 GNOME Wayland QEMU 快照，系统盘、基础盘、seed 均只读挂载，容器无外网、不挂密钥；宿主仅用客机专用测试 SSH 密钥。客机内使用候选包 SHA-256 `cd510bade9fbb01e4f321fa33785df9c9f4d0627a1336db9e430f2d51073d1a8`、临时 Fcitx 配置及空 profile 的 Chrome 154 程序副本。只启用隔离快照 Wayland，不访问用户资料或剪贴板。Chrome 测试副本使用 `--no-sandbox`、`--disable-gpu`、`--disable-dev-shm-usage`、`--disable-extensions` 和 `--no-proxy-server`，不代表实际桌面配置。

`probe.log` 的 XWayland 样本首先由 Python 进程自身请求合成本机服务器 `/a`，服务器记录 GET、返回 HTTP 200；此 GET 是自检，不能视为 Chrome 的请求。Chrome 目标注册 URL 为本地测试页，但 CDP `Runtime.evaluate` 显示当时执行环境 `about:blank`、`ready=complete`、`focus=true`。之后探针先发送 `Network.enable`、再发送 `Page.navigate`，等待导航回复 2 秒超时；该超时不证明 Chrome 永远不能完成导航。焦点窗口最终报 `initial_focus_missing`，因此未启动文本发送。脚本在观察期间没有记录其他服务器 GET。

XWayland 探针之后、不是其运行期间的 `resource-after.log` 显示客机 `MemAvailable=4982632 kB`、`SwapFree=0 kB`，且该时刻没有统计到名为 chrome 的进程；不能用此静态快照排除运行时资源问题。`native-probe.log` 将测试 Chrome 后端改为原生 Wayland，保留同样服务器自检与 CDP 探针：自检 HTTP 200，查询时页面 `about:blank`、focus=false，显式导航等待 2 秒超时，未启动发送。无法据此确定环境失效原因或归因于产品。

本实验未观察到 Chrome 测试页面接收 Fcitx 输入，也未测试 no_target、回退、取消或切焦。测试目标不是实际麦克风、云端识别或最终包验收。`native-browser.py.txt` 为原生样本测试脚本；`x11-browser-reconstructed.py.txt` 通过将同一脚本的后端和循环次数恢复为上一轮参数重建，未进行逐字哈希复核，因此不能声称其字节与实测脚本一致。`browser-run.sh.txt` 和 `sender.py.txt` 是实验输入，后者未实际启动。没有保存截图。

在一次性隔离客机复现：参考前一诊断的浏览器和候选包布置，将脚本去 `.txt` 放入 `/tmp/inkecho-r4-test/probes/`，分别以测试版本为 `browser.py`，执行 `bash probes/browser-run.sh <SHA> wayland`。测试脚本会启动临时 Fcitx 并安装桥，仅可在隔离环境使用。测试后客机 sudo poweroff，容器 `docker wait=0`，`ExitCode=0 OOMKilled=false`，容器已删除；未逐项恢复快照内配置，原盘只读。

SHA-256：`probe.log` `624d11056d1cdaba1241f454d6c0aaf077b64f39c00c7f7a8ad1dbe05041a6f2`；`native-probe.log` `f7a29b60f5136a094192d863a3bfb84517070f1f8faab7c57db51d3345102ba3`；`resource-after.log` `e73f9a9082c87e320b404722909b7cf6409ae14e399cdf93b7e95d40a4d99ae2`。
