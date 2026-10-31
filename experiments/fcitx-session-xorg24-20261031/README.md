# Ubuntu 24 Xorg Fcitx Session 验证（2026-10-31）

隔离 Ubuntu 24.04.5 GNOME Xorg 客机运行实际 `Session`、自动输出路由和 Fcitx 5.1.7，目标为 Chrome 本地自建 textarea。录音与识别、流式润色由合成替身产生；不访问实体麦克风、云服务、真实密钥或真实网页。同一冻结源码与 [Wayland 实验](../fcitx-session-wayland24-20261031/README.md) 一致；客机和主机的源码文件哈希清单相同，清单 SHA-256 为 `416551420d3ee23f5b630088b8d95dec7864cb097e24c6c27a7582b7120a9ef2`。旧 AppImage `ca322f19c6306546698621f4d2301a6a6b03eeb06c6c6be6e9f3d1506f6a5234` 只提供 Python 和依赖，不能视为包验收。

| 模式与场景 | 页面结果 | 状态 | 启动至观察结束 |
| --- | --- | --- | --- |
| 自动、焦点不变，200 字 | A 收到 200 字，逐字精确 | succeeded | 9.857 秒 |
| 自动、首字后切焦，200 字 | A 收到 1 字，B 收到 199 字，合并逐字精确 | succeeded | 9.869 秒 |
| 手选 Fcitx、首字后切焦，200 字 | A 收到 1 字，B 收到 199 字，合并逐字精确 | succeeded | 9.936 秒 |
| 手选 Fcitx、首字发出时程序取消 | A 仅收到首字；额外等待 1.3 秒未观察到后续文字 | cancelled | 1.388 秒 |

所有 dispatch 的 `route_after` 均为 `fcitx`；页面事件、逐字记录、状态与焦点见 `results.json`，退出状态见 `session-exit.json`。运行器确认 X11、GNOME 和 DISPLAY，Chrome 指定 X11 平台、独立配置和自建本地页面；未传入禁用浏览器沙箱的选项，但没有独立认证各 renderer 的沙箱状态。切焦由首个 input 事件触发，取消由程序回调触发；二者均不是物理设备测试。每种场景一个样本；尝试返回不是应用确认，在途请求不可撤回。

复现仅限独立、可丢弃的匹配客机和只读父盘：备份 guest Fcitx profile、部署产品插件、自启动 Fcitx 并重新登录；复制匹配的测试 Chrome 并在客机配置沙箱助手权限。将冻结源码、`dbus-next`、`websockets` 和本目录脚本放入私有目录，使用 `runner.py` 指定的 AppImage 运行。本实验依赖既有客机与测试安装夹具，不可直接在用户桌面运行；结束后恢复配置、移除测试插件并重登，见 `cleanup.log`。

未覆盖实体麦克风和按键、真实云识别、真实网站、任意时刻跨应用切焦、IBus 或正式 AppImage 发布验收。

客机已恢复原 X11 和 IBus 并正常关闭，QEMU 与容器退出 0、无 OOM，独立写层归档 SHA-256 `857b7ce540f5089f0d710cff9978e1accbaec412e464df74664be67f6fb42347`，完整解压流已校验，容器已移除。

关机与写层校验的原始、去敏 JSON 回执分别见 `qemu-exit.json` 和 `ram-overlay-archive.json`。容器退出码和 OOM 状态来自执行时的检查，未单独保存原始回执。
