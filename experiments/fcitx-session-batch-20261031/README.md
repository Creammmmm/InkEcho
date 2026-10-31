# Fcitx 批量输出：真实 Session 候选验证（2026-10-31）

此记录是隔离客机中的**候选源码验证**，不是当前版本 AppImage 的双系统包级验收。Ubuntu 24.04 GNOME Xorg 与 Ubuntu 26.04 GNOME 原生 Wayland 分别使用独立临时写层、无外部网络的客机，在自建 Chrome 文本框内接收合成文本；ASR、音频和润色均为测试数据。运行时来自旧版 0.10.0 AppImage（SHA-256 `ca322f19c6306546698621f4d2301a6a6b03eeb06c6c6be6e9f3d1506f6a5234`），被测应用 Python 源码来自冻结候选，并非该旧包内源码。Fcitx 原生插件 SHA-256 `f67c6b5f2cb7ecd7c915c8062efd3b70284c74b97ced4a597d942c4b39594e44`。

冻结的 94 个源码文件清单为 `source-manifest.json`，SHA-256 `130d742b6d92f17721efb88192ee6644ce19c0a3aa646855616c1b2f8486124b`。24 客机运行后单独生成的 `ubuntu24/guest-manifest.json` 与其逐字节一致；26 客机通过复制该冻结源码运行，但当时未单独取得客机清单，不能声称已对 26 客机内所有文件独立校验。关键文件 SHA-256：

- `platform/fcitx5.py`: `790300a2eaf14fffc0d66b327ab488fd7e694177088b9677edc9053b295897c4`
- `streaming_output.py`: `bdcf490e269a78e170d927f2c112b1f9cdd9f3e877a64c12ecf60ab310b30d63`
- `text_units.py`: `cd1885ea969ae825d5b7dcca013c0c2b8161dce1d0462c9363f87a7899241931`

## 结果

两个环境的七项 Session 场景均按夹具断言精确接收：自动及手选 Fcitx 的流式输出、同一网页两控件之间切换、跨片段 Unicode 与换行、发送第一字符后程序取消。`ubuntu24/summary.json`、`ubuntu26/summary.json` 按场景记录耗时、结果和实际提交批次长度。200 字场景 24 为 3.590–3.596 秒，26 为 3.554–3.576 秒；这些数字包含固定 1.3 秒的事后观察，且是整个夹具计时，并非纯输入耗时。自动路由观察到 1、2、3、4 字符批次；各具体场景的观察值以 JSON 为准，不能理解为每种场景均出现所有长度。

在真实拼音组合 `ni` 未提交期间，通过真实 Session 发起输出，两个系统都报告 `fcitx_composition_active`、原生发送尝试为 0，组合文本和页面事件不变；完成组合得到“你”后，另行通过输出路由得到“你甲乙丙”。组词期间的 Session 按设计返回失败，并非延迟自动补发；后续输出是独立的路由调用。

Fcitx 接口的应答不证明目标应用已处理或显示文字。批次也不保证内部逐字之间的焦点语义；无法确认投递时不得重放。本测试通过自有接收页面观察结果，但不能把该页面观察当成所有目标应用的通用接收确认。

## 首次失败与清理

24 的首次夹具启动在发送文字前失败：测试脚本寻找 `/opt/inkecho-local-chrome/chrome`，而隔离客机中 Chrome 位于 `/opt/inkecho-qa-chrome/chrome`，导致 `FileNotFoundError`。只修改测试夹具路径后在新目录执行 r2；首轮并非产品输入失败，也不能计为通过。原始首轮及 r2 记录保存在本工作区忽略目录 `build/fcitx-session-batch24/`；26 原始记录在 `build/fcitx-session-batch26/`。客机恢复了输入法配置，删除了测试插件和临时自动启动设置，并正常关闭。

## 操作与限制

目录下的脚本是当次去敏测试夹具，依赖隔离客机中预置的桌面、Fcitx、插件、Chrome、旧版 AppImage 运行时、FUSE 和对应测试用户目录，不能在普通主机直接运行。复现时应先隔离客户机及写层、安装相同插件和冻结源码，启动对应桌面与 Fcitx，再运行对应 `runner.py` 及 `runner-preedit.py` 并保存原始日志、接收结果和清理记录。26 拼音验证还使用 `qmp-key.py` 在自建窗口中发送测试键；24 使用 XTest。脚本不是发布验收工具，不应以实际用户桌面执行。

同页控件切换不证明跨窗口焦点切换；程序取消不证明物理 Esc 的链路。未覆盖物理麦克风、真实云端识别、全部目标应用与所有 Unicode 序列，也未覆盖 Ubuntu 24 原生 Wayland、其他输入法或完整 AppImage 验收。测试结果仅说明上述指定环境和样本。
