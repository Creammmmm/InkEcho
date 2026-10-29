# Chrome Fcitx 顺序编号事件复测

候选包 SHA-256 `f6ceb6311069f85b180bafd446f546247b5e592735ba26035455a571c5eb5164`；Ubuntu 26.04.1 GNOME Wayland，Chrome XWayland/GTK3，Fcitx 5，隔离 QEMU 客机 `-snapshot`、源盘和基础盘只读、容器无外网。Chrome 使用临时空资料和本地合成页面；AppImage 内 Session 使用固定合成转写，不涉及真实音频或云端服务。运行脚本见 `experiments/chrome-fcitx-focus-dom-ubuntu26/`，将其中 browser.py 换为 `experiments/chrome-fcitx-event-order/browser-sequenced.py.txt`（SHA-256 `d269b8da742796dffaaf93f4a075f30c8931819811c71259ee42f3d131ef8ed1`）。原始结果 `retest.log` 的 SHA-256 是 `4db77ed2f0fa5eb31ff3d987039ee716f050c5087fbe96942790c769202dbf44`。

三次均在观察到第一窗口输入事件后暂停发送进程，待第二窗口网页报告焦点后恢复；最终另经 Chrome DevTools 协议读取两个自建 DOM。第二和第三次分别为 7+193、12+188 字，拼接与固定 200 字逐字相同；发送端各有 200 次状态 1，最终 succeeded。第一次为 **11+0**，第二网页持续报告焦点且最终 DOM 有焦点但为空；发送端前 11 次状态 1 后收到 1721 次状态 3。状态 3 表明插件没有找到唯一焦点上下文、未调用 commitString，现有日志不能区分零个与多个上下文，也无法说明网页焦点与 Fcitx 焦点之间发生了什么。不得将第一次判为成功或归因于事件乱序。状态 1 不是应用最终消费回执。

第一次探针在等待约 20 秒后主动关闭 Session，发送端 outcome 为 None；这不证明产品最终超时行为，也说明脚本的退出码 0 不代表输入成功，必须检查 DOM 和 outcome。事件记录以每页单调序号拒绝晚到旧状态；本轮 DOM 独立读取是最终内容的判断依据，并非通用应用消费回执。本实验未覆盖自然无暂停切焦、真实麦克风、全部应用或双系统完整验收。

首次启动容器因 KVM 组权限不足失败，修正容器组权限后复测；运行结束后客机 SSH 握手超时，已停止并删除仅有临时写层的容器，退出码 0、OOMKilled false，未确认客机内部正常关机，原始镜像只读。独立程序副本来自本机 Chrome 安装文件，未复制用户浏览器资料。
