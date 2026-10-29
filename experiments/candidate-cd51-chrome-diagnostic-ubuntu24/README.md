# cd51 Ubuntu 24 Wayland Chrome 测试页加载诊断

2026-10-29，继续 `experiments/candidate-cd51-chrome-ubuntu24`：在独立 Ubuntu 24.04 GNOME Wayland 快照使用候选 AppImage SHA-256 `cd510bade9fbb01e4f321fa33785df9c9f4d0627a1336db9e430f2d51073d1a8`，不覆盖包源码；系统盘、基础盘、seed 只读，容器无外网且不挂密钥，宿主仅使用客机专用 SSH 测试密钥。只在快照启用 Wayland，使用临时 Fcitx 配置、桥和 Chrome 154 程序副本及空白 profile；无个人网页、输入正文或剪贴板。Chrome XWayland 测试副本带 `--no-sandbox`，不代表正常安装的浏览器运行条件。

第一轮 `diagnostic.log` 增加合成网页 HTTP 请求与 Chrome DevTools 目标列表记录：目标列表含本机测试页 URL，但服务器未记录该页 GET，也无页面事件，后续焦点等待失败，未启动发送端。stderr 曾有一次 GPU 命令缓冲失败，不能证明这是原因。第二轮 `diagnostic-flags.log` 仅对隔离 Chrome 测试进程增加 `--disable-gpu --disable-dev-shm-usage --disable-extensions --no-proxy-server`，仍未记录网页 GET 且焦点等待失败。

第三轮 `diagnostic-page.log` 用 DevTools 在该目标页面的 JavaScript 上下文读取 `document.readyState`、`location.href` 和 `document.hasFocus()`：得到 `complete`、`about:blank`、true；目标注册的 URL 仍是本地网页，测试服务器未记录 GET。它说明此次查看时页面执行上下文仍为空白，不证明导航最终状态，也不能证明服务器本身可正常处理请求或确定根因。

第四轮计划增加 Python 本机服务自检并延长观察时间，但 SSH 在执行前断开；`diagnostic-selftest.log` 只记录连接关闭，`browser-selftest-unrun.py.txt` 是准备版本，不能当作实测脚本或结果。再次连接在 banner 阶段超时。容器仍运行，因此只对本次专用容器执行 docker stop；容器 `ExitCode=0 OOMKilled=false` 并已删除，没有取得客机内正常关机确认；原系统盘只读。没有保存截图。

没有样本开始发送文字，故未验证 Fcitx 直输、no_target、键盘回退、取消或切焦。完整可复现脚本需进一步整理：初版脚本与测试布置见前一实验，本轮在测试 fixture 中加入临时日志、CDP 查询及可选隔离测试标志；所保存 Python 文件是自检未运行版本。不要在用户真实桌面运行，也不要从本实验断言 Chrome 或产品的实际输入结果。

SHA-256：`diagnostic.log` `5de0b2cc231a6ff3e4784fecd9c3005a50d988434af6e8fd661eb0010d219c1c`；`diagnostic-flags.log` `a92436c6b9f30dfb78844f0381efd17db4a25bbba950d2d1213c4bb685766bb1`；`diagnostic-page.log` `70b8e830eb3a2fdf17478f855d8058851b8f62487bf333aa4ac9d94ef8b28693`；`diagnostic-selftest.log` `c414bf93714ec20aa3ea8891a7dc5d4b98172d94bebcee035b8b5aa43f49f3df`。
