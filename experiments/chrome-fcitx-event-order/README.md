# Chrome Fcitx 首次切焦样本的事件乱序分析

分析对象是 `experiments/chrome-fcitx-route-ubuntu26/browser-xwayland.log`（SHA-256 `aca8c68867152267b19d330b9511edb7dad9b63ff264c203636b22e688ca03d8`）。脚本 `probe.py.txt`（SHA-256 `6f19bb5dbca1b8ac0676ece9c114a7498405df373c20d09acfbba1cdb98aff65`）解析原始日志并进行独立线程模拟，输出保存在 `probe.log`（SHA-256 `9dba8bdd64e63a9ab8a71b30ae606f95c2e0eb7ca2c63d474e4dbe02c3967137`）。原始日志中第二窗口共有 191 次 input 事件，末五次所报告的文本长度依次是 187、188、190、191、189；第一窗口报告 9 字。原测试服务使用 `ThreadingHTTPServer` 并按请求抵达顺序无条件覆盖最后状态，故最后的 189 覆盖之前的 191，产生 9+189=198 的报告。模拟实验强制旧事件后到，复现 191 被 189 覆盖。沙箱禁止网络套接字，该实验仅复现原服务器处理器对共享状态的赋值，不是实际 HTTP 传输复测。

第二窗口曾上报 191 字，与第一窗口 9 字合计为 200 字的长度；但原事件日志只保存长度，不能据此证明两个窗口文字内容逐字正确，也不能断言 Fcitx 对任意窗口都不会丢字。独立 DOM 验证的后续三次受控复测见 `experiments/chrome-fcitx-focus-dom-ubuntu26/README.md`。Native addon 的状态 1 表示对选中的输入上下文调用了 `commitString`，不是应用已处理或显示的回执；不得用状态 1 断言最终消费，也不能为不确定的输入自动重放。

新建 `browser-sequenced.py.txt`（SHA-256 `d269b8da742796dffaaf93f4a075f30c8931819811c71259ee42f3d131ef8ed1`），在后续 DOM 复测脚本基础上为每个页面的状态事件添加单调递增序号，服务端在锁内仅接受较新序号，并仍独立读取目标 DOM。脚本已通过 Python 语法编译，但未在图形环境运行；此序号假定测试页面不重新加载。线程模拟验证延迟旧事件被拒绝，不覆盖浏览器、网络、焦点和目标应用行为。限于任意目标应用缺少通用消费回执，延时或事件序号都不能保证真实应用完成处理；不能据此声称解决应用侧可能丢字。

复现：从仓库根目录执行 `python3 experiments/chrome-fcitx-event-order/probe.py.txt`；脚本当前引用本机仓库的绝对路径，可按实际位置调整。实验只处理自建测试记录和合成文字，不使用用户数据。
