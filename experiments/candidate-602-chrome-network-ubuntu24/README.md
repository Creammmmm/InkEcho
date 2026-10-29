# Ubuntu 24 Chrome 测试页的网络连接诊断

2026-10-29，继续 `experiments/candidate-602-chrome-ubuntu24`：独立 Ubuntu 24.04 GNOME Wayland QEMU 快照，系统盘、基础盘及 seed 只读，容器无外网且不挂载密钥，宿主仅使用客机测试 SSH 密钥。测试包 SHA-256 `602dab02b4837bb8d30c864dbe50d0413d58d53afb53d9695c7f96f50cdfb756`，不覆盖包源码。使用隔离 Chrome 154 副本、空 profile、临时 Fcitx 桥与本地合成网页；未访问个人资料或剪贴板。Chrome 启动带 `--no-sandbox`、`--no-zygote`、禁 GPU/代理/扩展等测试标志，非正常用户浏览器环境。

`probe.log` 中测试 HTTP 服务由 Python 自检并记录 `SERVER_GET /a`、HTTP 200；不是 Chrome GET。读取 `/proc` 显示服务测试进程、strace 父进程和 Chrome 启动主进程的网络命名空间均为 `net:[4026531840]`；遍历未证明所有浏览器线程和子进程都被枚举。`ss -nt` 显示测试端口 42057 有两对 ESTAB。相应原始 `connect-3343.log` 中该端口的非阻塞 connect 返回 EINPROGRESS 后，`getsockopt(SO_ERROR)` 多次为 0，确实说明所观察连接建立；CDP 页面在观察时仍为 about:blank，导航回复等待 2 秒超时，服务器没有记录 Chrome GET。服务进程初始负载快照为 `0.46 0.12 0.04`，不代表全部时间内的负载。

`write-probe.log` 与 `write-3782.log` 是新一轮：端口 42163 同样从 EINPROGRESS 到 SO_ERROR=0，HTTP 服务仍只有 Python 自检 GET，目标未获得可测试焦点；`strace -ff -tt -T -yy -e trace=connect,getsockopt,sendto,sendmsg,write,writev,close` 所保留网络进程跟踪中没有向对应测试端口输出的上述发送调用。该跟踪没有覆盖 `sendmmsg`、`io_uring` 等全部可能方式，也没有保存全部进程跟踪文件，不能证明没有任何进程发送过任何字节或断言根因。另一轮采用 `connect,getsockopt,poll,ppoll,epoll_wait,accept,accept4` 跟踪，留下有目标端口的进程原始文件，未包含所有进程文件。不可把仅捕获的调用范围推广为完整系统调用审计。

两轮未满足页面焦点条件，包外 sender 未启动；无 Fcitx 输入、回退、取消或切焦结果，不能归因产品。客机 SSH 在请求正常 poweroff 时 banner 超时，`shutdown.log` 保留失败；定向 docker stop 后容器 ExitCode 0、OOMKilled false 并删除，未确认客机内正常关机。无截图。

`browser-net-traced.py.txt`、`browser-write-traced.py.txt` 分别为两轮实际测试 fixture，运行方式及隔离要求见前一诊断。带 strace、无沙箱和修改临时 Fcitx 服务的探针只允许一次性隔离客机使用，不可用于真实桌面。`probe.log` SHA-256 `90ba0d2c870ea4a4c182ead0729910b51b9fc4c495039336d8add23875bc82fa`；`write-probe.log` `c2bb22df07624ed1567748120db6cbf0110fdaeb6d91f8ed9793e0cdd5b729ca`；`connect-3343.log` `ffe03a7803dc6bd0b777e7667b66a94026c406bcf1be3624b52b31b4c7aeb82d`；`write-3782.log` `d431f89f71070b66f4d758f777ef50cc11489281c1e7dde3358c6ad4a7737716`。
