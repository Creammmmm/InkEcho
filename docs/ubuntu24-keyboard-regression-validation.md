# Ubuntu 24.04 分段输入回归与未复现问题

本记录对应用户报告的 v0.8.0「识别结束卡顿后整段出现」和「Codex-cli 重复前两个字符」。当前检查仍在进行；以下通过结果不能写成用户字符重复故障已修复，也不能代替新 AppImage 的双系统验收。

## 源码与范围

v0.8.0 产品提交 `3bf0c67c2c5e47ee94166cf44ea5e855c3b2e521`、本轮起点 `967cd1d1bb92e60a866923937358bd348d50147f`（0.8.2）以及本轮检查时的 `src/inkecho/platform/keyboard.py`，SHA-256 均为：

`8c81ec8ba2e6519016c94ae687ca48647fc2d89417cea89ad8a554c513b47690`

因此，本记录中的生产键盘通过结果是**旧键盘实现的场景排除**，不是一个尚未实现的键盘修复。新启动、取消或润色规则另有各自的验证记录。以下实际场景是 Ubuntu 24.04.5、GNOME Shell 46.0、内核 6.8.0-142、专用 KVM 的 Xorg 会话；不表示用户已从默认 Wayland 切到 Xorg。

不使用剪贴板或系统输入法作为传输，不修改产品按键节奏、映射或恢复函数，不自动重放任何不确定输入。目标保留桌面真实输入环境（GTK_IM_MODULE 未设置、QT_IM_MODULE=ibus、XMODIFIERS=@im=ibus）；传输本身是生产 `_XTestDriver`。

## Session 与分段映射检查

新增 `tests/test_xorg_pair_session.py` 经过真实 `Session._stream_polish` → `StreamingOutput` → `KeyboardInput.output_session` → `_XTestDriver`。仅替换 X 硬件调用，每次按下时解码当时实际映射行，而不是只核对按键码计数。

覆盖混合 Unicode 长短分段、逐字分段、跨分段重复「中文」，以及等待下一片段期间取消、过期、替换、关闭后的迟到内容与资源清理。三种完整正文均精确；四种失效场景没有迟到按键。聚焦键盘、pair 与 Session 检查共 81 项通过；在启动路径变更后独立重跑新增 7 项亦通过，Ruff 通过。这是合成 X 硬件测试，不是实际终端证据。

## 实际 Chrome 21 字分段

固定公开样本为「中文输入验证 café Ω 字符逐个出现。」，8 个不等长片段，片段生产间隔 140 ms。真实 `StreamingOutput` 持有 `output_session`，调用冻结的生产工厂。独立本地 HTTP 页面观察实际 DOM `input` 后的正文，不通过脚本赋值或粘贴制造输入。

Google Chrome 154.0.8037.97 的真实 textarea 记录了 1 至 21 的全部前缀，最终正文精确，映射恢复，按下与释放平衡，未复现前两字重复或末尾整段出现。原始证据：

`build/ubuntu24-input-pipeline/raw/chrome-r2/result.json`

该轮原执行 `1224` 返回 1：正常关窗口后私有 Chrome 后台进程仍在，原报告保留 `browser_still_running=true`。随后对固定 owned PID 2940 核对 uid、starttime、exe 和独占 profile，按主 Agent 批准发送一次 SIGTERM，记录进程消失或僵尸状态；没有 SIGKILL，不能把后续清理改写为原执行自然成功。普通网页通过不能代表 Electron 集成终端。

## 实际 Codex / VTE 短句

真实 Codex v0.160.0 二进制 SHA-256 为 `12eb3e81114588aca3b7998f4f19e8997b056aca08e57a7ca7c8a3ec8c652aad`，运行于独立 GTK/VTE 窗口，私有 ext4 HOME、配置与空 cwd；独立网络命名空间只有关闭的 loopback，使用固定假密钥和不可用的本地端点。没有提交正文或访问云端。

本轮短句保留历史 `--no-alt-screen`，不能作为默认 alternate screen 的证明。主 Agent 检查真实空白编辑框后才批准发送相同 21 字分段样本：

- 生产发送与清理执行 `18368` 自然返回 0；21 字精确，按键平衡、映射恢复，发送总时长 1.357627 s。
- 实际 TUI 增长前缀为 `1,2,3,4,5,6,8,9,10,11,13,15,16,17,18,19,20,21`，首字至全文 1.227055 s。存在少量终端合帧，不能说每个字均有独立绘制帧。
- 主 Agent 实看 `capture-final.png` 核对全文。随后只向自有 PTY 发送正常 Ctrl-C，原 owner 执行 `72489` 自然返回 0。

证据：`build/ubuntu24-input-pipeline/raw/codex-r1`。`capture-startup.png` 是绘制前黑帧，不能当 ready；有效 ready 是后续 `capture-ready.png` 与其时间元数据。

## 实际 Codex / VTE 默认 alternate screen、245 字密集流

新的独立目标去掉 `--no-alt-screen`。固定 245 字公开样本，无换行、CR、ESC 或其他控制字符，包含中文、标点、ASCII 与重复词。每 3 字生产一个片段、间隔 20 ms，使队列持续有数据；产品每字按键节奏保持不变。主 Agent 实看 ready 后批准发送。

- 发送执行 `33760` 自然返回 0；245 个按下与释放平衡，映射恢复，发送总时长 11.664919 s。
- 旧 VTE 观察器仅做连续 `SAMPLE in text` 检查，终端软换行及两空格绘制缩进使原前缀门停在 57 字。原 `sample_complete=false`、`result.passed=false` 与原包装器 `78311` 返回 1 均保留，不能称原门通过。
- 经主 Agent 批准，在不修改 raw 的条件下，按精确「› 」正文标记及后续两空格渲染缩进提取；不 strip 正文空格、不跳过错误字。最终 245 字精确，227 次增长前缀，0 错误字帧、0 无法解码帧。最长无增长间隔 131.347 ms，中位 54.858 ms，首字至全文 11.511483 s。
- `capture-trigger-prefix-01.png` 是实际像素中间帧：捕获时仅绘出「中文输」，距全文完成仍约 11 秒。`capture-final.png` 显示最终多行正文。该证据并非仅 TextBuffer 的 changed 事件。
- 正常 Ctrl-C 退出后，CLI exit 0、GTK owner exit 0，无强杀；原完整前缀门失败仍然独立保留。

证据：`build/ubuntu24-input-pipeline/raw/codex-long-r1`。只读分析为 `formatted-editor-analysis.json`，输入绑定 `state-before-close.json`，SHA-256 `abec4e61c855f0b958b65f141fbd89fb589c0acd8f6e58e66b3ef779f06979f9`。这不替代未来包验收所需的完整接收端观察器。

## GTK 3 长段实际绘制对照

主 Agent 审核两个全新 owned 空白目标后，使用相同旧键盘源码、245字/20ms生产片段，分别运行 GTK3 TextView 与 Entry。两轮各收到245个精确增长前缀、245字最终正文，按下/释放平衡、映射恢复、接收器错误为空；发送分别11.543s和11.561s，正常关闭目标，无信号。

独立系统 Python/Pillow/XCB 进程抓取实际像素，未依赖被测 GTK 主循环的 draw/timer。TextView 的中间实际帧在 buffer5/47/168字附近呈现不同长度；Entry 的整屏中间实际帧在 buffer6/14/31/48/168字附近逐步增长并横向滚动。主 Agent 实看关键帧后接受“未复现最后整段出现”的场景排除。早期像素可落后 buffer 几个字；采样稀疏且 TextView 首轮 crop 曾漏左侧部分，不能宣称每字独立绘制或零绘制延迟。

原始证据为 `build/ubuntu24-input-pipeline/raw/gtk-textview-r1` 与 `gtk-entry-r1`，包含独立 frames.json/PNG、source sender 的原始等待结果和 owner 正常退出。TextView 原 emission92026 / owner72814、Entry emission56812 / owner23248均自然0。buffer-only统计单独标注，不用 changed事件间隔代替绘制延迟。这些是 GTK3 owned widget 的旧实现对照，不代表真实 GTK4应用或完整语音 Session 已修复。

## GTK 4 长段实际绘制对照

同一 Ubuntu 24 Xorg 会话使用系统 GTK 4.14.5 的 TextView 和 Entry，各自默认 GLRenderer、原桌面 IM 环境。245字密集生产片段分别发送11.328s、11.368s；实际正文精确、映射恢复、按下/释放平衡、接收错误为空，owner与sender正常退出。独立 root-screen 中间像素逐步增长，主 Agent 实看关键帧后接受旧实现未复现整段末尾绘制；Entry首个中间帧已见5字。buffer读取晚于像素截取，不可据此计算精确绘制延迟，也不能说零滞后。

原始证据 `build/ubuntu24-input-pipeline/raw/gtk4-textview-r1`、`gtk4-entry-r1`，四种GTK目标汇总在 `build/ubuntu24-input-pipeline/gtk-paint-diagnosis-r1.md`。这些仍为独立widget源码对照，不能替代完整语音链路或包验收。

## Electron / Code：进行中

VTE 与普通 Chrome 都不代表 Electron / xterm 集成终端。只读检查本机 Code 1.140.0 软件发现 `terminal.integrated.enableKittyKeyboardProtocol` 默认开启；这是一项需要实测的协议差异，尚未证明为根因。

现有公开 `/usr/share/code` 软件以完整清单复制至 guest 全新私有 ext4 目录，2596 个普通文件逐一 SHA 校验通过。清单 SHA-256 为 `9994c726c0b624b74a177c87fd8fd6784be1dd6f68e975a0ab73d34440b3e433`；未复制用户 profile、配置或密钥。测试工具使用本地 CDP pipe 的只读被动事件观察、透明 PTY 原样字节转发和实际画面；不插字，不禁用 sandbox。

首次正常 sandbox 启动因私有复制的 SUID helper 非 root / 4755 而拒绝（owned Code exit -5），没有创建窗口或发键。第二轮已 pin 的现有官方 helper 通过非空 CHROME_DEVEL_SANDBOX 指定，此 Code 构建仍查私有默认 helper 并拒绝；两轮失败均保留，未降低 sandbox。

经主 Agent 审核，第三轮只在 fixture 独占 mount namespace 中把已安装的 root-owned 官方 helper 只读 bind 到私有默认 helper 路径，先设 rprivate、验证 source/target SHA，再降 uid/gid1000启动。该轮越过 SUID 拒绝，但诊断 CDP pipe 出现 BrokenPipe。随后在带 process_log 的假浏览器回归中确认**测试 helper 的 FD3 CLOEXEC 自 dup 缺陷**：不能把第三轮工具错误写成 Electron 不支持 pipe，也不能当作产品输入失败。

第三轮 controller 退出时报告 Code 仍在，之后 PID5172 在拟发送清理信号前已消失，实际没有发送任何信号。原重复日志大小669,233,732字节，SHA-256 `f77e6e95c856e8853f3bb28adcb422fb209eb24754027bdc630e7ee92f6fe680`。隔离外私有 helper 仍 uid1000 / 0755 / 原 SHA，已安装 helper 仍 root /4755 / 原 SHA；没有留下全局 mount、系统文件或安全策略变更。

修正诊断 helper 后，真实 Code CDP 成功连接，实际 userAgent 为 Code1.140.0 / Electron43.7.3 / Chrome150.0.7871.250。该新私有 profile 随后触发空白新 Default keyring 模态，阻塞了观察；没有填写密码、创建 keyring 或输入正文。此为外部测试宿主的 SecretService 请求，不是 InkEcho 产品使用密钥环。正在正常取消此模态并准备只对 test-owned Code 使用 basic password store 和 in-memory secret storage 的新轮次。原 timeout、清理与单次SIGTERM均保留，不改写自然成功。该模态经两次正常 Cancel 后随已有单次 SIGTERM 的 owned Code 一并退出；没有追加信号。

第七轮使用新的私有 profile、真实 sandbox、loDOWN，仅对测试宿主加入 `--password-store=basic` 和 `--use-inmemory-secretstorage`，真实 Codex 默认 alternate screen 就绪。透明 relay 保留并记录实际 Code 的 `TERM=xterm-256color`、`COLORTERM=truecolor`、`TERM_PROGRAM=vscode`、`TERM_PROGRAM_VERSION=1.140.0`，xterm 返回 Kitty flags7；没有因环境清理关闭增强协议。主 Agent 目视空白 ready 后批准同245字密集分段。

**该轮实际失败，不能写成通过：**生产 sender 自然0、245press/release平衡、映射恢复，发送11.491993s，但实际 partial/final 中 Codex 正文仍空。被动 DOM 捕获245个 trusted/focused keydown，全部 `key=\u0000`、`keyCode=0`，没有 `input`；透明 PTY 原样收到245个 `00` 和245个释放序列 `CSI 0;1:3u`。这把故障缩小到 Electron43 的真实键译码至终端输入层，发生于 Codex正文处理之前；不是单纯按键已发送即可认定成功。未自动重放。

证据 `build/ubuntu24-input-pipeline/raw/code-r7` 包含 `ready.png`、`partial.png`、`final.png`、`dom-events.json`、`bytes.jsonl`、`identity.json`、`send.json`、`diagnosis.json`。这并非用户“首2字重复”的完全同形复现，缓存或键图通知差异仍待有界差分探针确认；**Electron 的映射输入兼容性已见实故障，尚未修复**。

## 映射通知的有界定位与候选修复

在实际失败的同一 Code 目标上，独立物理 `a` 正常成为 DOM `key=a` / `code=KeyA` 并显示，原生产单字「中」仍为 NUL。无发键探针只借183/184空行，core/master3/XTEST5的XKB快照都正确增加中/文，恢复后三个完整快照 SHA 全部回到 `0744a11b74a6cfd8112e4f48f0f379d23cd910e2c3e49bc9f68608463762b4e8`，所有core行恢复；服务器映射正确，不能归因为不同设备图不一致。

本探针收到真实 Xkb MapNotify 与 core MappingNotify：映射 first183/count2/requestKeyboard，恢复分别183/184 count1。这只能证明该探针连接收到，不能证明 Code 收到或处理。精确 Chromium150 的 Connection 代码在 core MappingNotify / Xkb NewKeyboardNotify 才重建本地XKB缓存；目标缓存重建使用 GetMap 的同步回复。Chromium154对应代码相同，不能称150独有回归。

经审的单字符差分只向准确owned窗口发送真实当前图的 core MappingNotify 后再按一次新「中」，DOM和PTY立即正确，实际图从a变a中；通知目标改成 InputFocus=1 后另一次新中同样正确，图为a中中。没有重放原失败245字、没有脚本插字或改变按键等待，归还映射后也通知原图。这证明本场景的客户端图缓存失效提示能修复实际键译码，不代表通知确认了显示完成。

候选在 `_XTestDriver` 每次借用行press前通知当前 InputFocus；不保存/绑定录音窗口，release不依赖通知；恢复空行后best-effort提示当前focus，通知失败不妨碍归还映射。没有改全局layout、非空物理键或按键节奏。focused84项检查与Ruff通过，候选尚未提交。

冻结候选 manifest `c683f6e1a09b43924852fb98b228e8476a4e4b2149bf8b6ef2b1e4711124c3dc`、keyboard SHA `79a38eab36fea9b16165e21a8b371629503002aa77b74b4b92babb799297fb9e`。

- 同一旧Code目标独立新17字「映射刷新验证：中文 café Ω。」：sender自然0，0.911790s，17个实际trusted DOM key全精确，图中追加正文精确；映射恢复、按键平衡。该目标正常Browser.close后Codeexit0，但原wrapper等待超600秒返回1，原timeout记录保留。
- 新私有Code目标PID6912/start674971、根审空白ready后发送245字/3字20ms流：11.522883s，245个实际DOM key精确全文，最大相邻事件间隔59.6ms。透明PTY完整消费245个精确UTF8正文press和245个Kitty释放帧，无未知尾字节；4个大写E释放按xterm编码为小写e，明确记录。原owner等待77073自然0、Codeexit0，无信号。
- 长段手动截图到达太晚，partialone/partialtwo实际都是全文，不能冒充逐步绘制证据。已审的只读阈值截图观察器将供后续source focus/cancel或实际包验补齐。候选GTK绘制与完整Session回归仍在进行。

后续候选GTK4 TextView回归出现真实单字错误：245字总长相同，第24字「我」成为「测」，实际像素同样错误；sender按键平衡、映射恢复、焦点guard无错，原wrapper73515自然1，不能因Code通过而忽略。原错字接收器和截图保留在 `raw/gtk4-candidate-textview-r1`，正常关闭owner75049自然0。每键全键图通知可能放大目标图重建/异步解码压力，目前只是待验证解释；79a38e候选不能发布。正在准备只对实际借行通知、按图revision与当前window去重的新候选，保持原按键等待，不以加sleep掩盖问题。

原始证据：`raw/xkb-map-r1`、`raw/code-r7`、`raw/code-candidate-long-r1`，均位于 `build/ubuntu24-input-pipeline`。用户“恒重复前两字”的完全同形缓存初始化场景尚未构造，不能把NUL失败写成精确复现；当前确证并修复候选的是实际Electron/xterm动态映射失效。

## r2：缩小通知范围与复用提示，实际回归

最终候选改为只提示实际借用的两行，按 `(map_revision, current_window)` 只保留单个最后提示键；新图或当前focus变化才再提示，同图同窗复用时不重复。这里的window只用于cache失效提示去重，不绑定录音目标；真正XTest仍按输出当时光标语义发送。恢复前保存借用范围、归还后best-effort提示该范围；失败不阻断release或归还。没有改变按键节奏、用户layout、非空行或增加等待。84项focused检查与Ruff通过。

冻结manifest `92e88de01d36fdea98756dd3442edc38641ad27de17782f84eb1b44704e8e7e4`，keyboard SHA `386d8349da0269766e3c1a9fa3c5deededce72f8b8909e040602b398a9c788dc`。

- 对新的GTK4.14.5 GLRenderer TextView，根审空ready后原245字密集流自然通过：11.261551s、246个快照全部是正确增长前缀、最终245字精确、maps恢复/按键平衡。原wrapper17743自然0、owner77580正常关闭自然0。`raw/gtk4-r2-textview/complete/frame01.png` 实际只有少量字符，frame08多行渐进；根 Agent 独立实看。没有把旧r1失败记录重写为通过。
- 根审两个新空目标后，6字transport取消与current-focus切换：前3字「焦点切」进入真实Code，第三release后正常切GTK4 Entry，后3字「换然后」进入GTK；第6字后 `can_continue=false`，继续观察1200ms，两receiver最终各3字无尾字。GTK最后changed7824.554、最后release7824.565，随后无新增快照。input_cancelled、6个press/release平衡、映射归还；这是transport条件取消，不是完整Session.cancel证明。
- 同一Code正常再次激活后追加独立新17字样本「映射刷新验证：中文 café Ω。」：0.899887s、DOM精确匹配既有3字加17字，实际图匹配；maps归还/按键平衡。没有清空或重放原不确定输入。两个receiver正常关闭，Code原74526、GTK原86666均自然0、无信号。

证据 `build/ubuntu24-input-pipeline/raw/focus-cancel-r2` 含两receiver截图、每个真实DOM事件、GTK快照与取消原始报告。GTK aftercancel截图为独立VM实际root-screen，因为此GTK4目标仅支持正常close控制，不支持GTK3旧工具的capture-request；没有据缺失文件推断成功。

此处完成的是r2源码级输入与焦点取消回归。新r2完整语音Session到真实Code的9字链路、实际包双系统同SHA验收另记，不能由源码结果替代。

## Wayland 与环境限制

静态核对：GNOME Wayland 工厂选择 Hybrid，输出要求 native 已授权；GNOME 46 缺少 SetKeymap / KeymapCapabilities 时，授权返回 `unsupported_compositor` 并 Stop / disconnect，不应绕到未授权的局部 XWayland 映射输出。已有缺接口测试覆盖此拒绝路径，但不能假定用户的实际会话或终端宿主。

本次 VM 正常开机后 9p 没有持久挂载，标准挂载返回 EINVAL，且 SSH 握手曾间歇超时。ControlMaster 后连接恢复；按批准改为新私有 ext4 输入 / 输出、SSH 传输和重新冻结 pins。上述是测试环境问题，非产品输入故障，未通过强杀或系统安全策略修改掩盖。

本记录仍是源码场景诊断，不是新 AppImage 或 Ubuntu 26.04 本轮包验收。用户首两字恒重复没有完全同形复现；实际Electron动态映射产生NUL已通过有界差分定位，并有r2源码修复回归。完整Session与同SHA包验收完成之前，不能将源码回归描述为发布验收通过。
