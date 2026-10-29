# 602 Ubuntu 24 Wayland Chrome 导航隔离诊断

2026-10-29，继续 `experiments/candidate-cd51-chrome-navigation-ubuntu24`：Ubuntu 24.04.5 GNOME Wayland active 独立 QEMU 快照，系统盘、基础盘、seed 只读，容器无外网、不挂密钥，仅宿主使用客机专用 SSH 测试密钥。候选 AppImage SHA-256 `602dab02b4837bb8d30c864dbe50d0413d58d53afb53d9695c7f96f50cdfb756`，未覆盖包源码；快照临时 Fcitx 与输入桥，Chrome 154 程序副本、空白 profile、本机合成网页，无个人数据或剪贴板。

三轮均用原生 Wayland Chrome 测试副本及隔离专用 `--no-sandbox`、关闭 GPU、扩展、代理等标志；不代表正常浏览器的安全环境。每轮 Python 测试进程自身访问本地 HTTP 服务 `/a` 得到 HTTP 200，不能把自检 GET 视为 Chrome 的请求。直到页面和控件取得焦点才会启动包外 sender，三轮均未满足，因此没有 Fcitx、回退、切焦或取消结果。

* `probe.log` 增加 `--single-process --no-zygote`：日志显示 DevTools 一度监听、V8 Proxy resolver 无法在单进程模式使用及 crashpad 错误，之后 CDP 连接被拒，未观察到 Chrome 页面 GET。该实验标志非常规，不说明正常浏览器是否可用。
* `nozygote.log` 去掉 `--single-process`：CDP 读取的页面仍是 `about:blank`、focus=false，显式导航等待 2 秒超时，服务器未观察到 Chrome GET；不能据此证明永远无法导航或具体原因。
* `connect-trace.log` 以客机内 `strace -ff -e trace=connect` 启动相同 `--no-zygote` 测试副本。测试端口 41529 上记录了 3 次至 127.0.0.1 的非阻塞 `connect(...)=EINPROGRESS`，还有多次至客机本地 DNS 127.0.0.53:53 的连接调用；未检查 connect 的最终完成状态，不可把 EINPROGRESS 写成连接成功。服务器记录的唯一 GET 是 Python 自检；日志仍显示 about:blank、CDP 导航超时、未发送输入。被跟踪进程与真实正常浏览器不完全等价。

测试之间的客机内存检查记录 `MemAvailable=5006312 kB`、`SwapFree=0 kB`，并非运行期间连续监测，不能排除瞬间资源问题。尝试 poweroff 时 SSH banner 超时，`shutdown.log` 保留失败；对本次容器定向 docker stop，记录 `ExitCode=0 OOMKilled=false` 并移除，没有客机内正常关机确认。系统盘只读。未保存截图。网络、沙箱、浏览器版本或测试夹具的根因均未证实，不能归因 InkEcho 产品。

保留各轮实际输入脚本 `browser-single-process.py.txt`、`browser-nozygote.py.txt`、`browser-trace.py.txt`、`browser-run.sh.txt` 和未启动的 `sender.py.txt`；复现方式参考 `experiments/candidate-cd51-chrome-navigation-ubuntu24`，必须一次性隔离客机，禁止在真实桌面执行带 strace、无沙箱及 Fcitx 服务更改的测试。此为诊断，不是完整包验收。

SHA-256：`probe.log` `e13ae44c25b62eb43f4dd7a1896b2930d5ae7b6cad0819029b855cc3a23cbd53`；`nozygote.log` `5306a4b73c0fa159d610d1a29d6174aed999528c14fd8c866914f6d783dc4df1`；`connect-trace.log` `dd729ac1f44b200fc8fe08f8190be862e9709793489501cb7908be3bb927bb45`。
