# 包含页面任务清理修复的 AppImage 候选

2026-10-28 从隔离冻结源码构建未发布候选
`InkEcho-0.10.2-x86_64.AppImage`，SHA-256
`f6378650f230215a0ff0a7196a80ddc48e9429e2546b55afe40105d8a5889d05`。
该文件名和版本来自未提交的源码，**不是正式 0.10.2 包**，未更新稳定
入口。构建后 633 项源码哈希均复核通过，清单及其 SHA-256
`5013987007df064faf024e789363bcd127e2a0c62536e0328fd2c4b7aa096d90`
保存在 `experiments/fcitx-runtime-version/candidate-r2-evidence/`。完整
源码副本和包在被忽略的 `build/runtime-candidate-r2/`，清单不保存文件
内容，临时目录可能被清理。

从实际包提取的 `ui/widgets.py` SHA-256 为
`ff7bbaf57cd447d6589bad2bc2aea1890fa03ce0d66ec40804459654c3a74559`，
与冻结源码逐字相同并包含 `Page.run` 任务清理修复。Fcitx 插件 SHA-256
`532ef632385bfe9ae3b76312b74874a7cc562c58435bb07f430e704179ebd139`，
与此前双系统独立实验候选相同。

Ubuntu 26.04 GNOME Wayland 隔离客机核对包和载荷哈希，通过包内安装器
在临时用户数据目录安装插件；包内配置默认自动选择、映射等待 40ms、
反馈超时下限 40ms。在自建 XWayland GTK 控件，包内生产路由自动、显式
Fcitx 分别输入甲乙，取消后无额外字符；准备任务后更换 Fcitx 进程，
旧连接返回 `fcitx_delivery_unknown`，没有重放。键盘是拒绝调用的测试
替身，非真实键盘。包内 Python 执行页面任务立即取消的确定性探针，
没有出现未等待协程警告。候选实际以 xcb 和原生 Wayland 两种 Qt 平台
启动，各生成 5 张截图并正常退出；原生 Wayland 设置页经人工查看。

实际包的 route、xcb 和 Wayland 完整原始日志、设置页截图、测试脚本与
源码清单保存在上述 `candidate-r2-evidence/`；全部截图和日志另存于
临时 `build/runtime-candidate-r2/ubuntu26-evidence.tar`。探针在客机
运行成功、输出 `package-immediate-cancel-no-warning`，其完整输出仅见
执行记录，未单独写入日志。xcb 和 Wayland 均报告缺少部分 VA 加速库；
Wayland 输出 Qt textinput disableSurface 诊断，但窗口正常退出。客机
临时配置及文件已清除，Fcitx owner 和进程消失，环境恢复、正常关机，
容器退出 0。

Ubuntu 24.04 GNOME Xorg 客机核对了**同一包** SHA-256、相同 Fcitx 和
`widgets.py` 哈希。包内安装器成功安装插件，默认自动及两个 40ms 设置
一致；自建 GTK 控件中自动和显式 Fcitx 输入甲乙，取消后无新增字符，
准备后更换服务返回 `fcitx_delivery_unknown` 且未重放。包内 Python 的
立即取消探针无未等待协程警告；AppImage 以 xcb 启动并生成五页截图，
设置页经人工查看。客机 Fcitx owner 和进程退出，环境恢复为 IBus，
临时目录清除，正常关机，容器退出 0。完整应用、路由和取消探针日志及
设置截图保存在 `candidate-r2-evidence/`，全部截图与日志另存临时
`build/runtime-candidate-r2/ubuntu24-evidence.tar`（SHA-256
`19c40651f54e681effa916ed8842973fcc32196a7f7b35646cf1b0f65449a962`）。

## Ubuntu 26 原生 Wayland Fcitx 输出补测

同一包 SHA 在 26 活跃的本地 GNOME Wayland 会话再次校验；包内安装器在
独立用户数据目录部署实际桥。自有原生 GTK TextView 使用 Wayland 后端和
Fcitx，包内 Session 使用固定合成转写文本，模拟录音和云端结果，没有
真实麦克风或网络请求。自动和显式两种模式各执行两项实验：

- **受控焦点切换**：A 收到第一个字后暂停发送进程，切换到 B 并确认 B
  的焦点后恢复。两种模式各有 A 收到 1 字、B 收到 199 字，拼接与原
  200 字完全相同；这不证明未暂停进程时的自然快速切换行为。
- **取消**：A 收到第一个字后发送取消信号，两种模式均以 cancelled
  结束，A 最终保留两个已送达的前缀字符，B 为空。取消无法撤回已经在途
  的输入，不能据此声称信号瞬间没有其他字符送达。

自动模式两次 sender stderr 都含 `Authorization required, but no
authorization protocol specified`，显式模式没有；四项 Fcitx 检查均
通过，但该提示来源未证实，不能忽略或宣称所有授权路径正常。完整原始
输出与 Fcitx 日志在 `candidate-r2-evidence/native-wayland/` 的 `run.log`
及 `fcitx.log`；实测脚本同目录，源 `run26.sh`、`sender-measured.txt`、
`target-focus-measured.txt` SHA-256 分别为
`09974052569cf8807a42fb6b67a789c9f5286ff9ca9961dfb4f0be3b992b5cb9`、
`c57667db94206bd714010df3ce986221b168bd6cb049bc6464ec193585d72c13`、
`46fcd3e008b724b09f04c7799554de5bdce565bc557febabc8cdd200e9cacf4f`。
日志含的文字均是固定合成测试内容。结束后会话变量恢复、Fcitx owner
和进程退出、客机临时目录删除，正常关机，容器退出 0。

### 26 X 授权提示对照

在另一次隔离客机中使用相同 r2 包及同一个自动 Fcitx/取消场景：显式
移除 `XAUTHORITY` 时重新出现上述提示；从当前 GNOME 会话取得可读的
`XAUTHORITY` 后重跑，同一场景通过且 sender stderr 为空。另以包内 Python
单独建立 `_XTestDriver`：无授权文件时输出同一警告并得到
`display_unavailable`；有实际会话授权文件时打开和关闭 X 连接成功。
这支持 26 的警告由先前测试脚本传入 `DISPLAY` 却遗漏 `XAUTHORITY`，
使自动模式准备 X11 备用路径失败所致；这不证明所有真实用户会话都有
可用的 X 授权，也不证明键盘实际输出。先前的原始失败和限制仍保留。
完整对照日志和脚本在 `candidate-r2-evidence/ubuntu26-xauth/`，其中
无/有授权的任务日志 SHA-256 分别为
`68f23a952146d212b1a8a676bf5b4f6ab278213d4b299e9ed4870d189ce45f09`、
`17c975e4f1559e09663f19d28bee6a14e4b6d3d96c50cb2964a429d08a66bec0`。
实验后服务退出、环境恢复、临时目录删除，客机正常关机退出 0。

## Ubuntu 24 原生 Wayland Fcitx 输出补测

在隔离客机先将原 GDM 和账户配置分别备份到重启后保留的 `/var/tmp`，
启用 Wayland 并重启，确认本地活跃会话 `Type=wayland`。相同 r2 包通过
SHA 校验，使用与 26 完全相同的包内 Session、自建原生 GTK 控件和脚本：
自动和显式模式在受控切焦实验各有 A 收到 1 字、B 收到 199 字，拼接
与固定 200 字完全一致；两种模式在取消后 A 均保留 2 个已发送前缀字，
B 为空。发送进程在切焦时被暂停，B 焦点确认后才恢复；不是自然快速切焦。
固定合成转写和模拟录音不验证真实音频或云端。

自动模式两项 sender stderr 均出现 `Authorization required, but no
authorization protocol specified`，显式模式没有；总日志还包含
`xcb_connection_has_error() returned true`。四项 Fcitx 检查通过，
这些诊断来源未确认，不代表键盘后备和其他授权路径正常。完整原始日志
和 Fcitx 日志在 `candidate-r2-evidence/ubuntu24-native-wayland/`；run.log
SHA-256 为 `f2141db29b5f0ad789994c062fe656b5ef971c993054b51cde18a5e6fb7e98cf`。
使用的三个脚本与上节 Ubuntu 26 脚本哈希完全相同。

测试后 Fcitx owner 和进程退出，输入环境恢复 IBus；以 `cp -p` 恢复 GDM
和账户原始文件并逐项 `cmp`，删除备份及测试目录，客机正常关机、容器
退出 0。备份 GDM 和账户文件的 SHA-256 分别为
`f025b366cbe743a9eee8535ea6b58d33965228c7c017c9d5f4a4b3bfacf9bc1d`、
`1234cf5c6acdbf6033569702b3cb5bdca557798fe88dc9f7af3df7b5492ae339`。

### 24 X 授权提示对照

在另一轮同一包和同一 GNOME Wayland 隔离客机中，与 26 一样对照自动
Fcitx/取消场景：显式移除 `XAUTHORITY` 出现先前相同提示；从当前图形
会话的用户管理器取得可读授权文件后重复，测试通过且 sender stderr
为空。包内 `_XTestDriver` 单独调用在无授权时重现相同警告并报
`display_unavailable`，使用会话授权文件时正常打开和关闭连接。
这支持先前 24 的警告同样源自测试进程遗漏 X 授权文件；单次 Fcitx
调用成功不能证明用户实际键盘回退、其他授权错误或所有环境都正常。
无/有授权任务日志 SHA-256 分别为
`5d121803df84387b351ceac42e19b43e660746349b510772be1de150d65b89d2`、
`87aec6166dac1aa98b4f51392a4256d67310ec04fbef1ad31e2f132c89899b0e`；
完整输出和对照脚本保存在 `candidate-r2-evidence/ubuntu24-xauth/`。
现有 X11 不可用回退单元测试单独通过。该轮客机由并行实验移交，测试后
Fcitx owner 和进程退出、输入环境恢复 IBus，移交的 GDM 和账户持久备份
已 `cp -p` 恢复并逐项 `cmp`，备份及临时目录删除，正常关机退出 0。

后续从 SSH 驱动原生 Wayland 图形测试时，应先在隔离客机设置
`XDG_RUNTIME_DIR`、`DBUS_SESSION_BUS_ADDRESS`，从 `systemctl --user
show-environment` 获取当前 `XAUTHORITY` 并验证可读，再将其传给测试
进程；不要将授权文件内容复制或写入日志。之前缺少该变量的原始记录仍
保留，不应将补测结果追溯为之前测试时键盘后备可用。

上述记录完成时尚未验证真实键盘回退和 FUSE；后续 Ubuntu 26 补测见下。
真实语音识别及发送过程中的服务变化仍未完成完整包验收；稳定入口更新
和发布均未完成。

## Ubuntu 26 FUSE 和真实键盘回退补测

同一 r2 AppImage SHA-256 为 `f6378650f230215a0ff0a7196a80ddc48e9429e2546b55afe40105d8a5889d05`。
在隔离 GNOME Wayland 桌面取消提取运行环境变量后直接启动该文件，
进程 mountinfo 显示 `/tmp/.mount_InkEchDkoaKl` 由 `fuse.InkEcho.AppImage`
只读挂载，应用显示并正常退出。原始挂载信息、启动日志、截图和脚本
保存在 `candidate-r2-evidence/ubuntu26-fuse-keyboard/inkecho-fuse-test/`。
这只证明本次客机具备 FUSE，不能推断所有安装环境均具备。

同一包的 Python 路由在私有 Fcitx 服务和两个自建原生 GTK Wayland
控件上使用固定合成文字：自动模式最初选择 Fcitx，真实桥返回
`no_target`、已接受 0 字且结果不确定标志为 false，随后回退真实键盘。
10 字完整到达；取消测试输出 6 字前缀并报告 `input_cancelled`；
自然切焦测试 A 收到 8 字、B 收到余下 52 字，拼接与原文一致。
这是特定控件和单次受控测试，不证明所有应用或真实语音表现。
首次启动因桌面锁屏未获得焦点而失败；解锁后首轮通过。增强探针首次
运行因上一轮 B 结果文件残留导致断言失败，清除结果后上述三项通过；
原始失败及成功日志均保留，不将探针错误归因于产品。

复现脚本和日志位于 `candidate-r2-evidence/ubuntu26-fuse-keyboard/wayland-lifecycle/`。
`run.sh`、`probe-original.txt`、`cross-target.py` 与 `instrumented-clean-run.log` 的
SHA-256 依次为 `9936ccb32eca69ea9284cecbdd511b27b5ab24f412ef979b2a3df0a518b97af5`、
`f1f83810642c25e1579d7dd163857a4ebcadd47860a4e434a90121d92986faa5`、
`6899e61ebcd43cb4855f3514124ba18388c3f0804f5907972e30a0f559461bb3`、
`d2a16a0dee3565a4818a55383bbba6b5d7159485e45f88ab844b770b82d29633`。
`probe-original.txt` 为实际运行的原始字节；复现时需复制为 `probe.py`。
同目录 `probe.py` 是整理格式后的检查副本，SHA-256 为
`446908cc8a267545c62e1c790762d14caf636f808c96c4e52e5715cf1c778a34`，
未在客机重新运行，不能将其实测结果等同于原始版本。
结束后 Fcitx owner 为 false、未发现残留 AppImage 挂载，测试目录删除，
客机正常关机退出 0。此包是隔离候选，不代表之后变更过的源码已验收。

## Ubuntu 26 XFCE X11 补测

隔离客机只提供 XFCE X11 会话，切换后 `loginctl` 显示 `Type=x11`；
这不是 GNOME Xorg 验证。相同 r2 AppImage 的 SHA-256 与上述一致。
同包直接执行 `--help` 成功；另通过 `--appimage-mount` 确认进程的
mountinfo 显示类型 `fuse.InkEcho-0.10.2-x86_64.AppImage` 和只读挂载，
随后退出挂载。此处未以 FUSE 启动完整 GUI。

固定合成音频与转写、自建 GTK 文本控件上的真实生产 Session 检查中，
无 Fcitx 时自动选中真实 X11 键盘，完整输出 200 字；两次自然切焦
均为 A 1 字、B 199 字且拼接准确；取消后保留 1 字前缀。独立 Fcitx
服务运行时，自动和显式模式均通过暂停发送后的切焦（各 A 1 字、
B 199 字）和取消（各保留 2 字前缀），切焦期间发送进程暂停，因此
不能当作自然切焦。初次 Fcitx 切焦探针在同步等待焦点时阻塞自身
事件循环并超时，原始记录保留；改用异步窗口激活后通过。

使用包内真实 OutputRouter 和简单 GTK 输入控件，自动模式先选 Fcitx，
实际返回 `no_target`、已接受 0 字且无不确定结果，再回退真实 X11
键盘：10 字准确；取消保留 3 字前缀；自然切焦 A 2 字、B 58 字且
拼接准确。已发送文字不能撤回，不证明其他应用或真实语音表现。

原始日志、复现脚本保存在 `candidate-r2-evidence/ubuntu26-x11/`；
真实键盘、Fcitx 和回退成功日志的 SHA-256 分别为
`8ea1ad490cb13e710f1b0aeee5e2b5c4b3fc8c174efbcd09d984bba70234e708`、
`a20ed21527a6547a89505ca5e8b1643713ec9c84534556b4098704256d1c9f71`、
`fef5ef2558c864404129218890e4fac00453d7dec589150f61c4276afde874d9`。
复现需按脚本中的路径将 `.py.txt` 原文复制为对应 `.py`；键盘 Session
探针的控件原文在 `ubuntu24-xorg-keyboard/target-focus-r6.py.txt`，
发送端在该目录 `sender.py.txt`。结束后 Fcitx owner 为 false、未发现
残留挂载，测试目录删除；原 GDM 与账户配置恢复并逐项 cmp，虚拟机
正常关机退出 0。该补测不构成完整双系统包验收。
