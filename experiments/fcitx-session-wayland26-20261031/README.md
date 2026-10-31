# Ubuntu 26 Wayland Fcitx Session 验证（2026-10-31）

一次性隔离 Ubuntu 26.04.1 GNOME Wayland 客机运行当前源码的真实 `Session`、自动输出路由和 Fcitx 桥，目标为本实验创建的本地 Chrome textarea。录音及识别、润色服务由夹具替身产生合成内容，没有使用实体麦克风、云服务、用户密钥或真实网页。源代码来自主分支 `a69ef0a`：客机与主机的源码文件 SHA-256 清单逐项相同，见 `guest-manifest.txt` 和 `host-manifest.txt`（清单文件 SHA-256 均为 `416551420d3ee23f5b630088b8d95dec7864cb097e24c6c27a7582b7120a9ef2`）。运行时来自旧 AppImage `ca322f19c6306546698621f4d2301a6a6b03eeb06c6c6be6e9f3d1506f6a5234`，仅借用其 Python 和依赖，**不是该 AppImage 的产品验收**。

| 模式与场景 | 页面结果 | Session 状态 | 从启动到延迟观察结束 |
| --- | --- | --- | --- |
| 自动，焦点不变，200 字 | A 收到 200 字，逐字精确 | succeeded | 9.874 秒 |
| 自动，首字后 A 切到 B，200 字 | A 收到 1 字，B 收到 199 字，合并逐字精确 | succeeded | 9.868 秒 |
| 手选 Fcitx，首字后切焦，200 字 | A 收到 1 字，B 收到 199 字，合并逐字精确 | succeeded | 9.852 秒 |
| 手选 Fcitx，首字发出时程序取消 | A 仅收到首字；额外等待 1.3 秒后未观察到后续文字 | cancelled | 1.382 秒 |

每次 dispatch 的 `route_after` 是 `fcitx`，详细字符、事件、时间、路由和结果见 `results.json`，脚本退出 0 见 `exit.json`。Chrome 使用 Wayland、测试专用本地页面与独立配置；脚本记录 compositor、toplevel 和键盘进入事件。切焦由页面首个 input 事件触发，只覆盖该受控时机；取消由程序回调触发，并非物理 ESC。成功样本各一次，不能证明所有焦点竞态或目标应用；桥接尝试及等待也不是目标确认，已经在途的请求不能撤回。

复现必须使用独立、可丢弃的匹配客机与只读父盘，预装测试 Chrome 和 Fcitx 插件，备份 guest 的 Fcitx profile，添加测试专用自动启动并重新登录；不要对用户桌面运行。将当前 `src`、`dbus-next`、`websockets` 和本目录的两个脚本放在 guest 私有 `~/inkecho-session-validation`，将合格插件放在该目录 `candidate`，以 `runner.py` 所指定的旧 AppImage 挂载提供运行时后运行该 runner。`session-browser.py` 创建测试页面、逐例重置焦点、运行 `session_product.py` 的真实 Session 并保存事件。此实验使用既有客机准备和恢复夹具，不能仅凭三个脚本从空白系统直接复现；测试完成须恢复原 profile、移除测试自启动与插件、重登并检查。`cleanup.log` 记录本轮恢复。

未覆盖 Ubuntu 24、本地真实录音与云识别、硬件按键、物理跨窗口切焦、IBus、正式包或长于 200 字的内容。该测试不能替代完整发布门。

清理后观察原 `ibus-daemon` 恢复。客机正常关机，QEMU 和容器退出 0、无 OOM；独立写层归档 SHA-256 为 `01174519e5364b73d99d55c27d22b9647e66d2e34ba16d4d5274f19f16834725`，完整解压流已校验。测试容器已移除。

关机与写层校验的原始、去敏 JSON 回执分别见 `qemu-exit.json` 和 `ram-overlay-archive.json`。容器退出码和 OOM 状态来自执行时的检查，未单独保存原始回执。
