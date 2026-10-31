# Ubuntu 26 Xorg Fcitx Session 验证（2026-10-31）

隔离 Ubuntu 26.04.1 XFCE Xorg 客机运行实际 `Session`、输出路由和系统 Fcitx 5.1.19，目标为 Chrome 的自建离线 textarea。录音及识别、流式润色为合成替身，不使用实体麦克风、云服务、真实密钥或真实网页。源码与 [Ubuntu 26 Wayland 实验](../fcitx-session-wayland26-20261031/README.md) 为同一冻结版本；客机和主机源码文件清单逐项相同，清单 SHA-256 `416551420d3ee23f5b630088b8d95dec7864cb097e24c6c27a7582b7120a9ef2`。旧 AppImage `ca322f19c6306546698621f4d2301a6a6b03eeb06c6c6be6e9f3d1506f6a5234` 仅提供 Python 和依赖，不是包验收。

| 模式与场景 | 页面结果 | 状态 | 启动至观察结束 |
| --- | --- | --- | --- |
| 自动、焦点不变，200 字 | A 收到 200 字，逐字精确 | succeeded | 9.913 秒 |
| 自动、首字后切焦，200 字 | A 收到 1 字，B 收到 199 字，合并逐字精确 | succeeded | 9.905 秒 |
| 手选 Fcitx、首字后切焦，200 字 | A 收到 1 字，B 收到 199 字，合并逐字精确 | succeeded | 9.915 秒 |
| 手选 Fcitx、首字发出时程序取消 | A 仅收到首字；额外等待 1.3 秒未观察到后续文字 | cancelled | 1.389 秒 |

所有 dispatch 的 `route_after` 均为 `fcitx`；页面事件、逐字记录、状态与焦点见 `results.json`，进程退出状态见 `session-exit.json`。运行器确认 X11、XFCE 和 DISPLAY，Chrome 使用 X11、独立配置和自建本地页面。切焦在首个 input 事件触发，取消由程序回调触发；二者都不是物理设备测试。每种场景一个样本，尝试返回并非应用确认，发送中的请求不能撤回。

首轮 Chrome 因只读共享目录的沙箱助手权限不满足而拒绝启动，未发生正文投递；失败原始记录见 `session-suite-failed-sandbox.log` 和 `browser-failed-sandbox.log`。将浏览器复制到客机内部、配置 root 所有和 4755 权限后重试；未传入禁用浏览器沙箱的选项，未独立认证各 renderer 的沙箱状态。启动夹具时也曾因会话尚为 Wayland、随后因夹具路径错误而在启动浏览器前中止，修正会话及路径后才进行上述样本。

复现仅限独立、可丢弃的匹配客机和只读父盘：备份原账户和 Fcitx 配置，在客机部署插件、通过账户服务切换 XFCE Xorg、自启动 Fcitx、重新登录，并复制匹配的 Chrome 后设置助手权限。将冻结源码、`dbus-next`、`websockets` 和本目录脚本放入 guest 私有目录，用 `runner.py` 指定旧包运行。本测试依赖既有客机与测试安装夹具，不可直接在用户桌面运行；完成后恢复 profile、移除测试插件，并通过账户服务恢复 Wayland。`cleanup.log` 显示原 GNOME Wayland 与 IBus 已恢复，但重新登录后旧 XFCE 会话当时仍在关闭，不能据此声称已经完全消失。原账户备份文件在测试期间不再存在，故无法执行字节比较；恢复后观察到的账户字段与测试前读取的内容一致。

未覆盖实体麦克风和按键、真实云识别、真实网站、任意时刻跨应用切焦、IBus、GNOME Xorg 或正式 AppImage 发布验收。

客机正常关机，QEMU 和容器退出 0、无 OOM，独立写层归档 SHA-256 `76fd507d7c49bf88a9ad7114e1dfc39f48036a4b9ed05589d4334e87061b480a`，完整解压流已校验，容器已移除。

关机与写层校验的原始、去敏 JSON 回执分别见 `qemu-exit.json` 和 `ram-overlay-archive.json`。容器退出码和 OOM 状态来自执行时的检查，未单独保存原始回执。
