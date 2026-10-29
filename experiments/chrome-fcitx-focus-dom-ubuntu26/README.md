# Chrome XWayland/Fcitx 切焦复测：独立 DOM 快照

候选 AppImage SHA-256 `f6ceb6311069f85b180bafd446f546247b5e592735ba26035455a571c5eb5164`；Ubuntu 26.04.1 GNOME Wayland、Chrome 154.0.8037.97 以 XWayland + GTK3 运行、Fcitx 5.1.19、GTK3 前端 5.1.6。独立于 `chrome-fcitx-route-ubuntu26` 首次测试，使用新的 QEMU `-snapshot`，原系统盘、基础盘及 seed 只读挂载，容器无外网。Chrome 仅用临时空用户资料、本地合成页面、测试进程专用 `--no-sandbox`；不访问个人内容。候选包内 Session 使用固定转写结果，不涉及真实麦克风或云服务。

三次复测在观察到首个输入事件后暂停发送进程，待第二浏览器窗口及文本框获取焦点再恢复；每次发送端均报告 200 次 Fcitx `commit_status=1` 和 succeeded。发送结束等待一秒后，使用浏览器本地 DevTools 协议读取两个自建页面的 DOM `textarea.value`：三次分别为 **11+189、8+192、13+187** 字，拼接均精确等于固定 200 字样本。DOM 值与原 HTTP 事件观察值一致。该复测验证受控暂停与焦点确认的样本，不能证明无暂停时的切焦、取消、各应用或所有环境。

前次 `chrome-fcitx-route-ubuntu26` 报告 9+189 字、发送端 200 次成功；当时未取得独立 DOM 最终值，事件并发上报乱序与实际输入丢失都没有被排除。本轮三次通过不能确定该次原因，也不能将首轮结果改写为通过。

`retest.log` SHA-256 `6c74905f2b858e95ff8627d322f3eb764c686df0649396e4a1b0ea8969cbdca0`；`browser.py.txt` `8334484da17cd01aa3d68e80183fedff8b96de86e46043f2d2249d18384a18b0`；`browser-run.sh.txt` `8dbf7edbe18f23894c2604db85f4e6ea9b625a6a79b2f70fe10c47b504ca905c`；`sender.py.txt` `1154f7b8a478b7b788813b1ad47555d02034f1064b10331c7aa4d47c33c74324`。后缀保留实测脚本字节。复现时将候选包放入隔离客机 `/tmp/inkecho-r4-test/`，脚本去掉 `.txt` 放入 `probes/`，Chrome 副本放在 `/tmp/inkecho-browser/chrome/`，执行 `bash probes/browser-run.sh <SHA> wayland`。后者指桌面会话，Chrome 指定 X11。DevTools 仅绑定本机并读取限定的测试网页。

测试完毕后客机 SSH 握手和 QMP 均超时；对仅使用临时快照的容器执行 stop，QEMU 退出码 0、OOMKilled false，容器已删除，未得到客机内部正常关机确认。原始磁盘未写入。日志及脚本仅含自建合成文本、测试用户名和本地路径，无真实密钥或个人正文。此记录不构成完整发布验收。
