# 26.04 Wayland 延迟授权探针

2026-10-29，在隔离 Ubuntu 26.04 GNOME Wayland 客机的自建 GTK 文本框上，使用 r4 候选 AppImage 解包运行，**不等于最终 AppImage 验收**。基包 SHA-256 `852a9e53efd66c7a19806e2473726d1ae5cdae5306804992fbf7d925eb583a48`。覆盖的工作区 `app.py` 与 `platform/output_router.py` SHA-256 分别为 `69cad54fee6b70bef05a5110289133aa819a33ebb4f0ba35d10f1d784fbf8600`、`e3f8e993566d996eabc43345f94956af821dec0ae071a8d632bbd62c36ff61e0`；其内容未随本记录归档，复现前必须核对源码哈希。输入为固定合成文字，无云端请求、真实凭据或用户桌面。

首轮没有指定 GTK 版本，客机默认导入 GTK 4；探针使用 GTK 3 的 `Window.add`，三种场景均在授权前因 `AttributeError` 退出。`gtk4-attempt-stdout.log` 是该次 stdout 原文，SHA-256 `21439ecf55a02003973cc6be4c18fcda260a2fc9b34aada5ad0613b21a09429a`；该轮 traceback 只出现在运行工具的 stderr，未被捕获成原始文件，此处不伪造原始 traceback 或声称保留。此失败与产品授权无关。

修正探针指定 GTK 3 后，`gtk3-retry.log`（SHA-256 `c652797e2068629ce2e40252d79383e8e8e61d400d5a1823f2c725926357ba79`）记录：

- cancel：授权函数约 29ms 返回，测试在调用开始 50ms 后将 can_continue 改为 false；目标收到“甲”，接着返回 input_cancelled。取消发生在授权返回之后，不是授权中取消；已发送文字不能撤回。
- timeout：给定 100ms 整个输出任务期限，授权约 2ms 返回；目标未收到文字，结果 input_cancelled。它没有覆盖授权等待中 deadline 到期，也不能凭结果断言已在授权阶段超时。
- normal：授权约 5ms 返回，目标收到“甲乙”。三次结束时目标都报告 active 和 focused，但该状态无法证明在授权过程的所有时间点没有焦点改变。

探针没有持续观察系统 UI，无法证明首次 RemoteDesktop 授权弹窗是否出现、是否可由用户处理或在弹窗期间取消/超时；更未覆盖弹窗内切换焦点。不能把快速成功当作真实首次授权弹窗的验证。本次只检查退出后无独立 `inkecho.platform.wayland_worker` 进程，不能证明所有远端授权资源均被释放。

原始重试探针以 `.py.txt` 保存，仅变更文件名，SHA-256：`sender.py.txt` 为 `170df88b25e625632e6105bbb308ba46e192f79117f4a173162962e0ad9ff744`，`target.py.txt` 为 `39ed956f29a19c674f9bf59602e7dec7fe35f85ee8d7dce722c058a2195cf6ef`。在隔离客机复现时，把它们复制到 `/tmp/inkecho-auth-experiment/` 并去掉 `.txt`，校验并解包基包、覆盖两份指定源码，在真实 Wayland/GNOME 会话导出相应 DISPLAY、WAYLAND_DISPLAY、XDG_RUNTIME_DIR 和 DBUS_SESSION_BUS_ADDRESS，依次执行 `timeout 25 /usr/bin/python3 target.py cancel`、`timeout 25 /usr/bin/python3 target.py timeout`、`timeout 25 /usr/bin/python3 target.py normal`。重建步骤未另行实测。

隔离客机临时目录已删除，客机容器正常退出（exit 0）。Ubuntu 24.04、首次弹窗、其他应用和最终双系统包验收均未包含在本轮范围。
