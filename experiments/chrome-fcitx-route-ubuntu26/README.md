# Ubuntu 26 Chrome 输入法路径对照

同候选包 SHA-256 `f6ceb6311069f85b180bafd446f546247b5e592735ba26035455a571c5eb5164`，Ubuntu 26.04.1、GNOME Wayland、Chrome 154.0.8037.97、Fcitx 5.1.19、GTK3 Fcitx 前端 5.1.6。与 `candidate-f6ce-apps-ubuntu26` 使用相同临时 Fcitx 和测试网页，区别在于 Chrome 使用 `--ozone-platform=x11 --gtk-version=3` 而不是 `--ozone-platform=wayland --enable-wayland-ime`；沿用本地空白资料与 `--no-sandbox` 的断网隔离副本。输出测试为候选 AppImage 解包内 Session 和真实路由，转写使用固定替身；不是实际录音及云识别。虚拟磁盘只读挂载、QEMU `-snapshot`，未改动原镜像与原用户输入法配置。

XWayland + GTK3 中，自动路由选择 Fcitx，正常样本精确收到 200 字，记录 200 次状态 1；取消样本收到 18 字的正确前缀，状态 cancelled。受控切焦样本在首字到达后暂停发送、第二浏览器窗口焦点确认后恢复：观察到首窗 9 字、次窗 189 字、总长度 198，内容是 200 字的前缀，但发送端记录 200 次状态 1 及 succeeded。该样本未达到精确接收门。页面逐次通过并发 HTTP 请求上报文本框状态，可能存在上报顺序落后于最终 DOM 的夹具问题，未做最终 DOM 独立核验；也不能排除传输丢字，因此不得据此宣布原因或通过。取消与切焦均是受控单次合成测试，不代表所有应用和焦点竞态。

原生 Wayland 前轮三样本均由 Fcitx 报 no_target 后安全转键盘；本轮 XWayland 形成直接 Fcitx 正对照。Fcitx 的[官方 Wayland 说明](https://fcitx-im.org/wiki/Using_Fcitx_5_on_Wayland/en)列出 Chromium 可走 Wayland text-input 协议，或通过 `--gtk-version=4` 使用 GTK 输入法模块。这个对照与不同连接路径一致，但目前未实际追踪 Chrome 协议调用，不能断言前轮 no_target 的唯一根因。快照只安装 `fcitx5-frontend-gtk3`，无 GTK4 Fcitx 前端包或缓存；本轮断网，故未验证 GTK4 直接路径。

`browser-xwayland.log` SHA-256 `aca8c68867152267b19d330b9511edb7dad9b63ff264c203636b22e688ca03d8`；`browser.py.txt` SHA-256 `2ffff7b96f25b0bf9ba73c25fa60b1b2e1cf2155e805d2cacd3a35c7d0a58dd6`，`browser-run.sh.txt` SHA-256 `45e7a629c676d24419591df94bcec017d52f1f7502a7ac5968c5aba6c891b9a8`。用同目录 `candidate-f6ce-apps-ubuntu26` 的 sender 与候选包，在隔离客机按其说明复制脚本并执行 `bash probes/browser-run.sh <SHA> wayland`。后面的 `wayland` 指桌面会话，Chrome 参数独立为 X11。

准备带定期最终 DOM 快照的复测时，客机 SSH banner 与 QMP 均超时，未执行复测。对仅含临时快照的测试容器执行 `docker stop`，QEMU 退出码 0、OOMKilled false；未获得客机内部正常关机确认，不能写为正常关机。临时容器已删除，原始镜像未写入。原始日志只含自建固定文本及测试路径，无真实密钥或个人正文。此结果不覆盖 Ubuntu 24.04、正常桌面 Chrome 安装、真正的麦克风及云端 API，不构成发布验收。
