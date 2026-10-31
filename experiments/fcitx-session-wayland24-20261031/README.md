# Ubuntu 24 Wayland Fcitx Session 验证（2026-10-31）

一次性隔离 Ubuntu 24.04.5 GNOME Wayland 客机运行真实 `Session`、自动输出路由和系统 Fcitx 5.1.7，目标为自建离线 Chrome textarea。录音、识别和流式润色为合成替身，没有使用实体麦克风、云服务、用户密钥或真实网页。这与 [Ubuntu 26 同类测试](../fcitx-session-wayland26-20261031/README.md) 使用同一冻结源码：客机与主机源码文件 SHA-256 清单逐项相同，清单 SHA-256 为 `416551420d3ee23f5b630088b8d95dec7864cb097e24c6c27a7582b7120a9ef2`。旧 AppImage `ca322f19c6306546698621f4d2301a6a6b03eeb06c6c6be6e9f3d1506f6a5234` 仅提供 Python 和依赖，本次不是该包的验收。

| 模式与场景 | 页面结果 | Session 状态 | 从启动到延迟观察结束 |
| --- | --- | --- | --- |
| 自动，焦点不变，200 字 | A 收到 200 字，逐字精确 | succeeded | 9.895 秒 |
| 自动，首字后 A 切到 B，200 字 | A 收到 1 字，B 收到 199 字，合并逐字精确 | succeeded | 9.875 秒 |
| 手选 Fcitx，首字后切焦，200 字 | A 收到 1 字，B 收到 199 字，合并逐字精确 | succeeded | 9.742 秒 |
| 手选 Fcitx，首字发出时程序取消 | A 仅收到首字；额外等待 1.3 秒后未观察到后续文字 | cancelled | 1.345 秒 |

每次 dispatch 的 `route_after` 是 `fcitx`；完整事件、路由及页面内容见 `results.json`，脚本退出 0 见 `session-exit.json`。浏览器使用 Wayland 和独立配置；脚本记录 compositor、toplevel 和键盘进入事件。切焦由页面首个 input 事件触发，取消由程序回调触发，不是物理切窗或 ESC。成功样本各一次，不能证明所有焦点竞态、接收应用或未知投递状态；在途请求不能撤回。

首轮 Chrome 因只读挂载使沙箱助手缺少所需特权位而拒绝启动，未发生正文投递；错误保存在 `session-suite-failed-sandbox.log` 和 `browser-failed-sandbox.log`。随后将同一浏览器复制到客机内部并设置 root 所有及 4755 权限后重试；没有传入关闭浏览器沙箱的参数，但未独立核验每个 renderer 的沙箱状态。

复现仅限独立、可丢弃的匹配客机和只读父盘：备份 GDM、登录会话及 Fcitx profile，在客机选择 GNOME Wayland、安装测试插件、自启动 Fcitx 并重登；复制测试浏览器并正确配置其沙箱助手。将冻结源码、`dbus-next`、`websockets`、合格插件和本目录脚本放入 guest 私有 `~/inkecho-session24-validation`，运行 `runner.py`。这里依赖此前准备好的客机和测试安装夹具，不是空白系统即可执行的完整脚本；不得在用户桌面直接运行。结束后恢复 profile、插件、GDM 及原登录会话，`cleanup.log` 显示返回 X11 和原 IBus。

未覆盖真实录音及云识别、实体硬件、真实第三方网站、任意跨窗口切焦、IBus、正式包或超过 200 字的内容，不能替代完整发布验收。

客机正常关机，QEMU 与容器退出 0、无 OOM；独立写层归档 SHA-256 为 `dac1f22f71144ecccc6dba04bfa7358c8f552d783a5b3b387a8f4a8e0c2bf1ff`，完整解压流已校验，测试容器已移除。

关机与写层校验的原始、去敏 JSON 回执分别见 `qemu-exit.json` 和 `ram-overlay-archive.json`。容器退出码和 OOM 状态来自执行时的检查，未单独保存原始回执。
