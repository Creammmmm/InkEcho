# InkEcho 0.9.0 双系统实际包验收

## 结论与适用范围

同一版本、同一 SHA-256 的候选 AppImage 已在真实 Ubuntu 24.04.5 / GNOME 46 / Xorg 与 Ubuntu 26.04 / GNOME / Wayland 会话完成以下实际包验证，Root 分别检查了关键页面、逐字输入与 Dock 图像。文本编辑器和 Files 的结论来自明确记录的人工独立验收，原严格自动门仍为 false；不将其改写成自动 AT-SPI 完整链路通过。此文档本身不表示已经上传 GitHub 或替换稳定入口。

音频使用独占、唯一命名的虚拟设备及本地 TLS ASR/SSE 服务；键盘门使用真实选包输入后端与新建的 owned 接收窗口。未读取真实凭据、未调用真实云服务、未访问物理麦克风、未使用剪贴板或系统输入法。未将 Ubuntu24 原生 Wayland 写成已支持。

## 构建、来源与审计

清洁 main 源码为 `2330dffcfb1df6e88fa8720848ef700637b005c0`，三处版本均为 0.9.0。完整本地工作流结果为 **1918 passed、2 skipped，51.51s**。随后仅构建一次，原构建进程 5518 自然退出 0；后续全部测试工具修订均未重建或修改该包。

| 对象 | SHA-256 |
|---|---|
| `InkEcho-0.9.0-x86_64.AppImage`，104294904 bytes | `be8b77df3e62f9d436083884c98e52a70535c60cadc8cb6ec52a1ebb6e4d85d5` |
| `.AppImage.sha256` 侧车文件自身 | `23fb6699513bfe39bcbf0bf5dc6d24eb4c3fca675cafe5f4f32691a941d52866` |
| 包内 `inventory.json` | `df5600abb169674a226e7e31b469b62815812d2b5e0b077ec588884dde6ff17e` |
| 原始完整测试工具闭包 c556 | `c556703a2e4a85c568447bfcb519f1ef96c6b24bdbfe6c9f22a253f6c80267aa` |

两系统均从该同一 AppImage 自解压至新的私有目录，所选解释器、应用模块及其 origins 来自新包，不使用旧 0.8 runtime 或源码 overlay。每门先校验完整工具闭包、AppImage 摘要、inventory 的 3673 个文件和 1048 个链接，以及全部 64 个应用源码文件的集合和内容。Code9 闭包为 `34d9ee6589701023e524a32ad673b461950e37cac7f9529f2df2af474b7c0147`，apps4 闭包为 `2b8204be7df6756be88cfdc4ed64b3972710938270fb7416881c6ec0ee6bccfb`；Ubuntu24/26 分别使用已冻结的原生 Pulse16.1/17 外部工具，避免跨 glibc 复制工具造成假故障。

## Ubuntu 24.04.5：Xorg 实际结果

| 验证门 | 实际结果与边界 | 原始证据（相对 `build/release-0.9.0/`） |
|---|---|---|
| 五页设置与生命周期 | Root 实看全部 1120×731 页面；AppImage 主进程自然0；IPC show/quit、cold toggle/cancel/quit、配置不变、损坏私有配置退出1且原 bytes 保留 | `raw/ubuntu24-entry-r2/` |
| Code / Codex CLI 正常完整链路 | 真实 Recorder→本地 WSS final→HTTPS SSE→真实选包 X11 factory→Code1.140/Electron43.7/Chromium150 中真实 Codex CLI。9个 trusted DOM 字符及前缀正确，完整 PTY UTF-8 精确、无 NUL；Root 亲看“本地”→“本地完整链”→完整9字。截图前后计数2/2、5/6、8/9，第三张不算严格partial | `raw/ubuntu24-code-normal-r1/` |
| Code / Session.cancel | fresh 接收端，真实 first_sent 后同步 Session.cancel；58次独立采样、持续1.28232079s，仅可信单字“本”，DOM/PTY一致且无尾字；Root 实看最终图 | `raw/ubuntu24-code-cancel-r1/` |
| 文本编辑器 | 原自动严格门 false。Root 独立检查21组逐字通知、partial6字→caféΩ实际渐进与最终21字准确readback；每组两个通知、offset0..20/len1/data精确，无删除/反向。未记录 source identity，不能猜测重复通知一定来自同一 callback | `raw/ubuntu24-actual-editor-r2/`，`independent-notification-adjudication.json` |
| Files / Nautilus 搜索框 | Root 实看6→14→完整21字的真实渐进与最终图。21组按键平衡、map恢复、owned文件仍0字节，无Enter、未重命名。实际5帧，第6预设阈值因sender已结束未采。`automated_pass=false`、`passed=false`、`manual_pixels`、`AT-SPI fullchain not certified` 均保持原值 | `raw/ubuntu24-actual-files-r4/` |
| Xorg Escape | 选包全审计后：活动任务取消、普通a、空闲Escape、焦点不变、释放grab均true；owned Qt11824自然0。选包escape模块摘要 `c111ee8666ee0c1a76b6383bd6c4f0ea4af5bec72a95b06e84571aa1740b7cc1` | `raw/ubuntu24-xorg-escape-r1/` |
| 直接 AppImage Dock | Root 实看真实窗口、左Dock专属笔图标及单个运行点、顶部托盘图标，没有Python分裂图标；原1922/SSH91817/runtime自然0 | `ubuntu24-dock-r1/`；实际屏幕 `build/ubuntu24-perf-vm/output/ubuntu24-release-dock-0.9.0-r1/dock.png` |
| 空结果与真实错误 | 8场景全部接受；empty/whitespace/ASR-empty/no-PCM无problem，认证/网络/响应/超时保持准确可见错误 | `raw/ubuntu24-nongui-r1/quiet-r1/` |
| 协议与VAD | 本地ASR/SSE正常文本精确、首次输出早于润色完成、取消无尾字；VAD正常final一次、取消零输出、资源清理。零真云/零真实凭据 | `raw/ubuntu24-nongui-r1/{protocol-r1,vad-r1}/` |
| 真实Recorder与动画 | 虚拟源3次首帧14.575/15.165/15.840ms，各1600 marker；动画初始inactive，首有效624 bytes后才启动，捕获信号各1次；虚拟模块清理、默认音频不变 | `raw/ubuntu24-nongui-r1/audio-r1/` |

Code正常门首捕 **25.854ms**、marker **1601**，首次实际发送比完整SSE早 **289.8ms**。正常/取消的 sender、Code和原owner均自然0，按键平衡、map和默认音频恢复；CLI relay因Code正常关闭PTY记为 **-1**，不能称CLI自然0。Editor原owner11534/dispatch11596自然0；Files原owner12214/sender12352自然0，独立quit helper **255** 如实保留，不将wrapper完成0当自动文字门通过。

Dock独立恢复审计确认恰好9个公开desktop/icon路径全部恢复。SSH观察路径与实际Shell data home `/home/inkecho/.local/share` 精确一致；before/after的exists/hash/mode完全相同（本次9路径初始均不存在），无未恢复路径、无临时restore残留。before/after JSON摘要均为 `12258a2b371ef753eeb2aa9af58b146d10479f74a5668c7c8e3f9ca4b91594f6`。只读观察脚本摘要 `fa966f9f4097d3dbc4263bcbad1966aa7138422860d714a78e9fd7e80b8d30dc`；`independent-restore-audit.json` 与原 terminal 分开保存。

## Ubuntu 26.04：Wayland 实际结果

| 验证门 | 实际结果与边界 | 原始证据（相对 `build/release-0.9.0/`） |
|---|---|---|
| FUSE直接运行与五页生命周期 | actual FUSE mounted runtime全内容审计；Root 实看5张2240×1700图；原owner自然0、show/quit、cold controls0、配置不变、旧stable摘要未改 | `host-fuse-r2/` |
| 原生正常完整链路 | 真实Recorder→本地TLS ASR最终屏障→HTTPS SSE→真实选包nativefactory→原生Chrome。实际Wayland surface/xdg_toplevel、DISPLAY unset；Root 实看“本地”→完整9字，可信前缀1..9精确 | `host-native-normal-r2/` |
| 原生Session.cancel | fresh原生接收端，真实first_sent同步取消与epoch失效；独立receiver持续1.20289455s仅“本”，Root实看最终图，无尾字 | `host-native-cancel-r1/` |
| 原生全局Escape | 真实选包TaskEscape/PortalTaskEscape与owned原生Qt；Root审精确目标后emit，回调一次并同步失效。活动press被取消，keyup1仍可透传；断开后空闲press正常通过。原owner84138/receiver自然0、sender关闭、guard shutdown | `host-native-escape-r3/` |
| 空结果、协议、VAD | 同24对应边界，全部原owner自然0；空结果静默且真实错误反馈，本地协议正常/取消与VAD资源清理通过，无真云 | `host-quiet-r1/`、`host-protocol-r2/`、`host-vad-r1/` |
| Recorder与动画 | 3次首帧19.222/15.099/11.902ms，各1601 marker；动画首有效628 bytes后才启动。此Overlay按生产实现运行在XWayland，不能写原生Wayland Overlay。模块清理、默认音频不变 | `host-audio-r2/` |

原生正常链路首捕 **7.747ms**，marker **1601**；首发1634.897ms，完整SSE1960.234ms，提前 **325.337ms**；9ACK、9press/9release。原生取消首捕8.449ms、marker1601、1ACK/1press/1release。二者无guard rejection、按键平衡、Mutter keymap/state与默认音频恢复，sender/browser/controller原始句柄自然wait0，cleanup_errors为空。精简字段及各原始JSON/PNG摘要见 `host-native-package-summary.json`。

## 外部测试工具修订来源

以下仅修测试工具，完整冻结源和AppImage始终不变。每个新闭包都明确以c556为parent并由Root校验完整文件摘要，旧manifest与失败证据未改。

| 独立工具闭包 | SHA-256 | 改动范围 |
|---|---|---|
| FUSE `fuse-stage-r2` | `5cdf1341577e9663951ccb9c72d96d0d69e55460a9c6f4848c55caebd2e786ea` | PNG有限写入完成等待；CRC/IEND/EOF、ownedPID仍活及同bytes；helper `0beb35fbf707dd5b2037d87be1b44ea38222680f37bd9200beb2eaa7ac219a83` |
| 24 entry `entry-stage-r2` | `ff5b06e89f66f2923abe2ac773cd2c48146abd6e4888c4328f59c553fc594af2` | 同类外部PNG等待probe `fc3da19f8229da4c260c01050387d371ed5e64ba53c1c1311f6b8eae261d0bb7`，显式加载gate `6dac5c43cf63bf48b081c884e313af7f2eaa940a6a5f5e0892aadca2220f2456` |
| native Escape `native-escape-stage-r2` | `e2dd0058e4a7fa4a7a7629d45fb8d0adca4d27a69263aed5d63b01abfddf1910` | 仅修PySide逻辑嵌入support模块来源审计；外部probe `c792666e2630c270ed2457a2790236bc1555372fc044eda2207524ff0533225a`，wrapper `ceab3a844a2566fe9dabcc93725c37375f07a6c23620d4e5d8f544ba6255ff59` |
| Dock `dock-stage-r1` | `ecbf21fe74b23ec8186fbe6c3f63189c84c67791f35ea84df744642808bd5674` | 4个外部helper迁移显式0.9/source/artifact/fullpackageaudit、新私有ext4与QMP实屏；原备份恢复语义保留 |

## 原始失败、清理异常与限制

- FUSE r1的控制器93886在有限PNG写入尚未完成时断言失败1；AppImage主进程自行0，后来有效的5图仅作视觉证据，原生命周期门不写pass。r2修工具等待后完整门通过。
- native normal r1的外层系统Python缺websockets，在sender/按键前失败。Root批准核PID/start/exe/profile/CDP browserPID后一次正常Browser.close；控制器残留非daemon HTTP线程，无正常外部shutdown入口，Root明确批准对UID1000/PID79115/start1368770再核身份后仅一次SIGTERM。原29632返回shell143（controller等效-15），**不是自然0或cleanup通过**。r2外层改为预检过的project-venv观察器依赖，产品解释器仍来自新包，随后真实门通过。
- host protocol r1被工具沙箱拒绝Wayland IPC，在协议前失败；同冻结脚本正常IPC r2通过。host audio r1传错fixture平台，在录音前xcb断言失败；其生产Overlay所需xcb r2通过。没有改产品或重建包。
- native Escape r1在建Qt/Portal前误拒真实PySide嵌入逻辑模块，外部probe仅接纳精确11对模块/逻辑名称及已pin四个native backing文件，9个负例拒绝。r2等待审核超时，无emit/按键，原owner自然1、receiver0；r3经Root原子身份审核后通过。
- Editor r1是**晚读回漏掉首个长度1前缀**，不能写最终全文缺字。r2有42个通知、21组同内容，未保存source identity，不推定重复callback根因。严格原flags仍false，Root独立验收与自动门分列。Files旧rename/a11y focus Text准备失败均保留；最终仅认证搜索框逐字像素，不认证rename或AT-SPI fullchain。
- Code及native正常门保留本地ASR fixture的 `ConnectionClosedError`；从异常类型和路径可定位来自ASR WebSocket，而非已成功完成的HTTPS润色。产品finish在最终session.finished后关闭连接，fixture继续async-for；未记录closecode/stack，不能称干净1000握手。取消额外 `ConnectionResetError` 的HTTPS drain/wait_closed阶段无法由共享type列表区分。错误类型与实际文本/ACK/map/default恢复分别记录，不掩去、不因此重放成功输入。
- 本次验证不量化真实云端语音准确率、物理麦克风冷启动、真实网络时延或未测桌面会话。虚拟源首帧毫秒结果不保证所有物理设备零丢字。原生Escape首次系统授权和活动keyup透传边界如实保留。输出遵循当时光标位置；主动取消/epoch失效后不继续发字，未确认输入不重放。

## 可复现步骤

1. 在独立干净checkout选择构建源 `2330dffcfb1df6e88fa8720848ef700637b005c0`，安装项目依赖，执行与该源receipt一致的完整工作流：

   ```sh
   .venv/bin/python scripts/validation/workflow.py run \
     --module speech-pipeline --evidence docs/speech-pipeline-source-validation.md
   ```

   receipt所列子命令为 `.venv/bin/python -m ruff check .`、`.venv/bin/python -m ruff format --check .`、`.venv/bin/python -m pytest -q`。完整流程要求干净HEAD；后续QA文档提交应生成自己的receipt，不覆盖2330的构建事实。

2. 按[音频诊断与验证说明](ubuntu24-audio-pipeline-repair.md)准备独立真实桌面会话；选定摘要be8的AppImage、新自解压AppDir及冻结2330源码，先经[artifact_scope.py](../scripts/validation/artifact_scope.py)的 `selected_artifact` 与 `audit_package` 检查完整包/源。使用[原生完整链路runner](../scripts/validation/native_pipeline_runner.py)的显式参数，以下变量须指向同一轮新建私有目录而不是旧接收端：

   ```sh
   .venv/bin/python "$STAGE/native_pipeline_runner.py" \
     --stage "$STAGE" --manifest-sha256 c556703a2e4a85c568447bfcb519f1ef96c6b24bdbfe6c9f22a253f6c80267aa \
     --package-root "$APPDIR/packages" --frozen-source-root "$STAGE/frozen/src" \
     --python "$APPDIR/usr/bin/python3" --expected-version 0.9.0 \
     --artifact "$ARTIFACT" \
     --artifact-sha256 be8b77df3e62f9d436083884c98e52a70535c60cadc8cb6ec52a1ebb6e4d85d5 \
     --inventory-sha256 df5600abb169674a226e7e31b469b62815812d2b5e0b077ec588884dde6ff17e \
     --output "$FRESH_OUTPUT" --case normal --run-reviewed
   ```

   外层观察器需已预检websockets依赖，`--python`始终是同包解释器。准备阶段仅打开新的owned接收端；可信reviewer实看empty ready和原生surface/PID/start/focus后才写 `send-request`，不自动复用或激活用户窗口。取消场景另建fresh output/receiver并用 `--case cancel-after-first`。实际精确argv另存 `host-native-package-commands-r2.json` 与每轮terminal的sender_argv；九字/一字实际receiver前缀、至少1200ms取消观察和最终像素不能由合成sender替代。

3. Xorg取消使用[TaskEscape probe](../scripts/validation/task_escape_probe.py)，通过同包解释器运行并显式 `--package-root "$APPDIR/packages" --output "$FRESH_RESULT"`，先做完整artifact/source审计。原生取消使用[native Escape probe](../scripts/validation/native_escape_probe.py)的显式package-root、output/progress/owned-root/emit-file与desktop-entry参数；本次需要上表已审核外部审计修订，不能声称原tracked审计假拒版本通过。按真实接收端ready审核门运行，保留原始按键释放与生命周期证据。

## 复核入口

- 构建：`build-receipt.json`；原始完整stage与上述外部fixture stage的manifest。
- 本模块62份原success/fail/terminal摘要索引：`audio-entry-raw-receipt-pins.json`，自身SHA `c96a753ac9a2ee399e4908e83c0bcb9b05c8b78275ef285c1ed9371baac984e1`。
- 接收端完整人工/自动分离与原始目录：`ubuntu24-receiver-acceptance-summary.json`，SHA `1b8a561e5b3961d4e2640e6b536e8f0d5723d61dce217ad18764d0c03230b1cb`。
- native Escape完整原始证据摘要：`native-escape-acceptance-summary.md` 及 `host-native-escape-r3/acceptance-receipt.json`。
- Dock：`ubuntu24-dock-r1/{terminal.json,paths-before.json,paths-after.json,independent-restore-audit.json}` 与实际屏幕PNG。所有真实配置/密钥均未纳入证据。

复现时使用规范验证脚本的显式选包/source-root、owned接收端与新私有输出目录；完整闭包先审计，发字前核fresh ready，由可信reviewer查看。所有旧失败保留，不修改原rawflags，也不把后来QA文档提交的版本误认为该已验0.9.0 AppImage的构建来源。

## 专用验收环境关闭

全部owned窗口、sender、音频模块与9个Dock注册文件恢复完成后，通过SSH在专用guest内执行正常 `sudo -n systemctl poweroff`，命令退出0；未使用docker stop、强制关机或SIGKILL。容器随后自然 `exited`、exit code0，结束时间 `2026-10-22T18:35:12.697294358Z`。除上文明确保留的一次失败测试controller SIGTERM外，无其他强制终止。此后不再操作GUI。
