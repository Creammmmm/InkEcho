# cd51 Ubuntu 24 Wayland / Chrome：未完成的焦点诊断

2026-10-29，独立 Ubuntu 24.04 GNOME Wayland 快照，active 会话；候选 AppImage SHA-256 `cd510bade9fbb01e4f321fa33785df9c9f4d0627a1336db9e430f2d51073d1a8`，不覆盖包源码。QEMU 系统盘、基础盘与 seed 只读，容器无外网且不挂密钥，仅宿主使用客机专用测试 SSH 密钥。仅快照内启用 Wayland，使用临时 Fcitx 配置和应用桥，未切换输入法引擎。Chrome 程序是 `/opt/google/chrome` 的临时副本（154.0.8037.97），每轮空白临时 profile、自建本机网页和固定合成字符串；使用 `--no-sandbox` 仅为测试副本，不能说明正常安装 Chrome 的沙箱行为。不访问个人网页、剪贴板或用户正文。

`chrome-x11.log` 使用 `--ozone-platform=x11 --gtk-version=3`，候选包哈希通过，full、cancel、switch 三个尝试都在发送端启动之前报告 `initial_focus_missing` 且事件数组为空，无法判断页面是否获得焦点、Fcitx 是否找到目标或实际输入行为；包装脚本捕获这些错误，不应把其总退出码视为通过。不会据此宣称 Chrome、Fcitx 或候选包本身失败。

第二次尝试将 Chrome stderr 保存在客机临时文件并合入 `x11-diagnostic.log`：仍为 `initial_focus_missing`，Chrome stderr 包含 DevTools 监听信息，表明该进程至少启动到调试端口就绪；这不证明测试网页已加载。随后准备 `browser-diagnostic2.py.txt`，拟在等待期间查询本机 DevTools 页面，但 SSH 断开，代码没有成功传入或运行，`x11-diagnostic2.log` 仅显示连接中断。再尝试重连时 SSH banner 超时；原因未确定。隔离容器被定向 docker stop 后 `ExitCode=0 OOMKilled=false` 并删除，未得到客机内正常关机确认，原镜像只读。

因此本轮没有实际发送文字，也没有 `no_target` 状态、键盘回退、切焦、取消、Chrome 原生 Wayland 或正常沙箱验证；不构成发布验收。`browser.py.txt`、`browser-run.sh.txt`、`sender.py.txt` 为首轮输入脚本；`browser-diagnostic2.py.txt` 是未运行的诊断准备。隔离环境复现可参照 `experiments/chrome-fcitx-focus-dom-ubuntu26/README.md` 的测试布局，替换为本目录脚本和同哈希候选包，复制 Chrome 程序副本至 `/tmp/inkecho-browser/chrome/`，执行 `bash probes/browser-run.sh <SHA> wayland`。该脚本会启用临时 Fcitx 输入桥和访问本地合成网页，且需要测试副本的 `--no-sandbox`；不可在真实用户桌面直接使用。未保存截图。

SHA-256：`chrome-x11.log` `0d9de5f5a1a9532d6823182413132dd2caefba492088039bdc59f6b4e80e08ff`；`x11-diagnostic.log` `db52348a4e1002bfd6cf135d6220d2f6c950b7be078e381739a1ae8c7c7100f2`；`x11-diagnostic2.log` `c414bf93714ec20aa3ea8891a7dc5d4b98172d94bebcee035b8b5aa43f49f3df`。
