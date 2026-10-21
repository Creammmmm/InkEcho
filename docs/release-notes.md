# InkEcho v0.8.0 — 持久图标与 Ubuntu 输入体验优化

本版修复直接运行 AppImage 时 Dock 可能显示灰齿轮的问题：桌面入口使用持久 XDG 目录内的品牌 PNG 绝对路径，避免依赖主题名称查找；图标先写入、入口随后发布，不引用 AppImage 临时挂载路径，也不增加启动时缓存刷新等待。0.7.0 因实际图标验收失败而未发布，历史记录保留。

- Xorg 相邻空键码行合并更新，改善 Files 首字后停顿再出现全文的问题，保留逐字发送、取消与映射恢复。
- 改善真实文本编辑器、Files、Codex CLI 与 Claude Code 的混合字符输入；不使用剪贴板或系统输入法。
- 阻塞 TLS 初始化移到后台，尽早收音；首次有效采样到达后才显示聆听动画。
- 桌面入口与程序使用一致的 InkEcho 身份，管理图标保持持久，保护外来文件与自定义资源。

Linux x86_64 的 Ubuntu 24.04 / GNOME 46 **要求 Xorg 会话**，其原生 Wayland 仍未支持。Ubuntu 26.04 / GNOME 50 保持既有原生 Wayland 与 XWayland 范围；原生 Wayland 仅支持既有 BMP 范围，非 BMP 字符明确拒绝，不宣称全 Unicode 支持。终端可能合并多字符重绘，不保证每帧只显示一个字。

26.04 既有受控 Chrome 测试偶发输入框失焦至 BODY，根因未定位；本版不宣称已修复或双系统体验完全一致。输出跟随发送当时光标，焦点变化本身不取消；主动取消、任务过期或替代后停止未发送文字。物理麦克风开头、真实供应商准确率与真实录音 → 云 ASR → 目标应用端到端本轮未验；合成标记和本地协议门不替代这些结果。

本版须从精确 0.8.0 源码构建，以同一 SHA-256 完成双系统实际包及 host FUSE 验收；24.04 Dock 须在该 Shell 首个 InkEcho 窗口及后续私有同 APP_ID 窗口之后分别复验。最终范围和状态见 [0.8.0 发布验证](release-0.8.0-validation.md)，不沿用旧包通过记录。

```sh
sha256sum -c InkEcho-0.8.0-x86_64.AppImage.sha256
chmod +x InkEcho-0.8.0-x86_64.AppImage
./InkEcho-0.8.0-x86_64.AppImage
```

旧实例请先正常退出，避免只唤起旧版。以下历史候选与发布记录保留原文。

---

# InkEcho v0.7.0（未发布候选）— Ubuntu 24.04 输入与录音启动修复

该候选在 Ubuntu 24.04 的实际 Dock 图标验收中失败，**没有发布**。后续源码 0.7.1 将 desktop Icon 改为持久 XDG 图标绝对路径；修复须随新的发布版本重新构建与双系统实测，不能返写该候选通过。

该候选面向 Linux x86_64，重点改善 Ubuntu 24.04 / GNOME 46 的 Xorg 使用体验：

- 修复 Files 等真实 GTK 输入框的首字后停顿、最后全文出现问题。Xorg 只借用相邻的两条空键码行，一次合并更新，逐字符发送并保留取消、冲突检测与映射恢复。
- 修复 AppImage 桌面身份与图标显示；设置窗口和程序使用一致的 InkEcho 标识。
- 对真实文本编辑器、Files、Codex CLI 与 Claude Code 的完整 Unicode 输入和渐进呈现进行验收；不使用剪贴板或系统输入法回退。
- 将阻塞的 TLS 初始化移到后台，尽早启动收音；只有收到真实采样后才显示聆听动画，避免动画先出现而尚未收音的误导。

Ubuntu 24.04 要求使用 **Xorg 会话**；GNOME 46 原生 Wayland 缺少所需映射接口，仍未支持。Ubuntu 26.04 / GNOME 50 保留原生 Wayland 与 XWayland 的既有限制。输出跟随发送当时的光标；切换焦点本身不取消任务。

终端应用可能把多个字符合在一帧重绘：验收分别记录完整渐进输出与严格每帧单字，不承诺所有 CLI 每字独立显示。26.04 的受控测试曾出现输入框由 TEXTAREA 失焦至 BODY，后续正常与取消对照通过，但该偶发风险的根因尚未定位，**本版不宣称已修复该风险或两个系统体验完全一致**。

物理麦克风开头、真实云端识别准确率及真实录音 → 云 ASR → 目标应用端到端流程本轮未验证；合成音频和本地协议验证不替代这些结果。本版必须从精确 0.7.0 源码重新构建，以同一 SHA-256 在两系统完成实际包验收及私有 FUSE 启动后才发布；此前 0.6.8 的验证只作方法参考。最终状态见 [0.7.0 发布验证](release-0.7.0-validation.md)。

下载后校验并运行：

```sh
sha256sum -c InkEcho-0.7.0-x86_64.AppImage.sha256
chmod +x InkEcho-0.7.0-x86_64.AppImage
./InkEcho-0.7.0-x86_64.AppImage
```

旧实例请先正常退出，避免单实例通信只唤起旧版。

以下历史记录保留原文。

---

# InkEcho v0.5.0 — 统一工作台与不抢焦的语音预览

本版将设置整合为「概览、模型配置、风格、设置、帮助」五页，并修复原生Wayland
显示Siri灵感悬浮预览时抢走输入焦点的问题。主设置保持原生Wayland，只有悬浮显示
使用独立XWayland ToolTip宿主；草稿仅经RAM通道显示，不提前发送到目标应用。
宿主异常会显示安全提示，不回退到抢焦窗口、剪贴板或系统输入法。

- 概览提供字符数、录音时长、次数、最近七日图、语音与润色配置选择；
  删除开始录音卡片，默认通过快捷键开始 / 停止，准备中和任务中保留取消入口。
- 语音与润色合并到模型配置页；首次不预建平台或名称，需自行填写并保存。
  已有配置保留，协议按平台能力过滤，超时集中到设置，关闭润色后相关选项灰显。
- 提供聊天、编程智能体、正式邮件、忠实整理等模板，允许复制并自定义。
  支持的Qwen实时协议在悬浮内显示可替换草稿，取消、替代或结束清空；
  普通HTTP和没有partial能力的协议不伪装为实时识别。
- 统一InkEcho图标、桌面身份和单实例设置窗口；关闭到托盘，无托盘时保留可恢复
  的最小化入口。帮助提供版本信息与手动更新检查，不自动安装。
- 显式余额刷新仅对已适配的官方接口读取；未知余额不估造，提供已知官方控制台。
  凭据继续明文保存在专用credentials.json，不使用系统密钥环。

输出仍跟随输出当时的光标，不捕获录音开始时的目标；焦点变化本身不取消任务。
主动取消、过期或被替代后停止未发送文字，已发按键不能撤回或自动重放。
原生Wayland保持既有BMP支持边界，不支持的非BMP字符明确拒绝。

发布范围为Linux x86_64：Ubuntu24.04 / GNOME46的实测Xorg路径，以及Ubuntu26.04 /
GNOME50的原生Wayland与XWayland限定自有目标。GNOME46原生Wayland仍不支持；
不新增Windows/macOS支持。本地TLS/WSS/SSE与合成音频不等于真实云账户、余额、
麦克风、物理快捷键、语音准确率或任意应用认证。

0.5.0须由精确发布源码重新构建，以同一SHA完成两Ubuntu实际包、Siri无抢焦、
正常 / 取消输入与资源恢复验收，并验证私有FUSE启动后才发布；
不使用已验0.4.4改名或沿用旧包hash验收。源码先合入main，正式tag绑定精确0.5.0
发布提交；后继报告提交按规则使用0.5.1。实际发布状态以GitHub为准。

下载AppImage与同名校验文件后：

```sh
sha256sum -c InkEcho-0.5.0-x86_64.AppImage.sha256
chmod +x InkEcho-0.5.0-x86_64.AppImage
./InkEcho-0.5.0-x86_64.AppImage
```

旧实例仍运行时，请正常退出后再启动新版，避免单实例IPC只唤起旧版本。

以下历史记录保留原文。

---

# InkEcho v0.4.0 — 配置目录明文凭据

所有供应商认证字段现在明文保存到所选配置目录的专用 `credentials.json`，
不再使用系统密钥环。普通 API Key 与 App ID/API Secret/Secret ID/Access Key 等组合
凭据都走同一本地存储；普通供应商参数仍只保留引用，不将秘密混入参数或日志。
文件使用 0600、目录 0700，原子写并拒绝符号链接。

- 移除 keyring、SecretStorage、jeepney 等 11 个专用依赖分发。
- 旧密钥环条目不会读取、迁移或删除；升级后需要在界面重新填写凭据。
  切换供应商不复用旧引用，`--config-dir` 同时隔离配置与凭据。
- 保留 18 项云 ASR 供应商/参考入口、四种润色协议及模型能力过滤，
  四槽原生输出、10ms 释放等待和整句 ASR 收尾重叠行为不变。
  不使用剪贴板或系统输入法；本地协议测试不代表真实云账户认证。

发布范围为 Linux x86_64：Ubuntu 24.04 Xorg 与 Ubuntu 26.04 GNOME 原生 Wayland/
XWayland 的限定实测路径。GNOME 46 原生 Wayland 仍不支持；不声称真实麦克风、
物理快捷键、任意应用、Windows/macOS 或本地模型已验证。

本版必须由精确 0.4.0 源码构建独立 AppImage，同一 SHA 在双系统完成实际凭据九门、
11 模块缺失、九页界面及正常/取消输入，并通过候选私有 FUSE 后才发布。
不能使用已验 0.3.2 包改名代替。旧 0.3.0 发布资产与旧凭据保持原样。

下载 AppImage 与同名 `.sha256` 后：

```sh
sha256sum -c InkEcho-0.4.0-x86_64.AppImage.sha256
chmod +x InkEcho-0.4.0-x86_64.AppImage
./InkEcho-0.4.0-x86_64.AppImage
```

正式 tag 指向精确 0.4.0 发布源码，后继验收报告提交按规则使用 0.4.1，
不改变冻结产物身份。源码须先合入主分支；实际发布状态以 GitHub 为准。
[凭据源码记录](plaintext-credentials-validation.md)与[0.3.2 历史包验收](plaintext-credentials-package-validation.md)
提供验证方法，本版产物仍须独立验收。

以下历史记录保留原文。

---

# InkEcho v0.3.0 — 云供应商与协议适配

本次版本整合18项云ASR供应商/参考入口与四种润色线协议，并改进语音模型选择。
供应商目录、协议实现和实际账户权限分开：本地TLS/WSS/SSE验证不代表真实云账户认证。
协议依据和独立实现边界见[适配记录](provider-adaptation-validation.md)。

- 语音：保留百炼Qwen HTTP/实时能力，新增显式multipart、音频JSON/chat及
  StepFun专属ASR、百炼Fun-ASR/Paraformer任务式实时、火山、讯飞和腾讯WebSocket适配。
  包含ElevenLabs、SiliconFlow、Groq、OpenAI、OpenRouter、ZenMux、MiMo、Orca、
  Zhipu、MiniMax等预设；未知自定义模型保留手填，但不声称已验证。
- 润色：Chat Completions、Responses、Anthropic Messages、Gemini原生协议，
  独立处理请求、流事件、终态与思考/工具内容，不将截断或部分输出重放为成功。
- 模型列表按当前供应商和转写协议过滤ASR候选，排除纯文本、TTS、图像和embedding；
  切换协议即时重过滤。无发现接口的内置列表不会伪称连接测试成功。
- 密钥存入系统密钥环，普通配置仅保存引用；多字段凭据有专用输入，不写普通配置或日志。
  切换供应商不会把旧密钥复用到新端点。
- 保留四槽原生输出、10ms逐字释放等待、整句ASR最终结果与协议收尾重叠，
  以及已有流式润色/输出。输出跟随当前光标；取消、过期或被替代后停止未发送文字。
  不使用剪贴板或系统输入法。

发布范围为Linux x86_64。每个新AppImage必须以同一SHA-256在Ubuntu24.04 Xorg和
Ubuntu26.04 GNOME原生Wayland/XWayland分别完成实际包验收，才可发布。
GNOME46原生Wayland仍不支持。本地合成音频测试不证明真实麦克风、物理快捷键、
任意应用或真实云模型权限；不增加Windows/macOS或本地模型支持。
本版验收另行绑定0.3.0真实产物，不能使用旧0.2.10包或其结果代替。

下载发布附件AppImage及同名.sha256后，可校验并启动：

```sh
sha256sum -c InkEcho-0.3.0-x86_64.AppImage.sha256
chmod +x InkEcho-0.3.0-x86_64.AppImage
./InkEcho-0.3.0-x86_64.AppImage
```

正式tag对应精确0.3.0发布源码；后续验收报告提交依规则递增为0.3.1，
不改变已冻结0.3.0产物身份。发布前须确认该源码已合入主分支。

以下历史记录保留原文。

---

# InkEcho v0.2.0 — current-cursor Linux voice input

This formal release contains the verified four-slot native Wayland keyboard
output, a 10 ms per-character release wait, and whole-utterance final-ASR /
protocol-closure overlap with the existing streaming polishing/output pipeline.
Each key still has its own acknowledgement; prepared hints never emit text.
Explicit cancellation, expiry and replacement stop unsent output without replay.
Recording does not capture a target; output follows the current cursor.
No clipboard or system input method is used.

The preceding a18 package measured one native 100-character sample at about
3.31 seconds; its source 30/20/10 ms comparison and local TLS pipeline proof are
recorded in [a18 acceptance](a18-dual-ubuntu-validation.md). Those are historical
a18 measurements, not a substitute for the new 0.2.0 artifact's same-SHA dual-OS
acceptance. The 0.2.0 package report must record its own version, SHA and results
before publication.

Release scope is Linux x86_64: Ubuntu 24.04 Xorg and Ubuntu 26.04 GNOME native
Wayland/XWayland as actually validated. GNOME 46 native Wayland remains
unsupported. No Windows/macOS, arbitrary application, physical shortcut,
real microphone or authenticated cloud-recognition claim is added by local
synthetic-audio/TLS tests. Credentials remain in Secret Service; audio and
transcript history are not retained by default.

The release-source version is 0.2.0. Later report/development commits use
0.2.1 and subsequent patch versions under the per-commit version policy; they
are not additional release assets unless independently built and published.

## Historical 0.1.0a8 — remove the retired focus-tracking adapter


This cleanup removes the unused captured-target AT-SPI adapter from production
source and packaging. Historical probes/tests keep that algorithm under test-only
support; no production module imports it. Current-cursor keyboard behavior,
explicit cancellation and stale-task protection remain unchanged. Recording does
not bind a target, and moving focus does not cancel a task.

See [source removal audit](focus-tracking-removal-audit.md) and
[alpha8 package validation](focus-tracking-removal-release.md) for the actual
artifact checks and deployment status. The supported transport remains X11 /
XWayland; this cleanup does not add native Wayland target or arbitrary application
support. Earlier acceptance results retain their measured versions below.

## Historical 0.1.0a7 — input at the current cursor

Recording no longer captures or requires an editable target. Windows and caret
may change during recording, transcription and polishing without cancelling the
task. The production keyboard backend resolves the X11/XWayland focus during
output, so later characters may follow a window switch. Explicit cancellation
and expired tasks still stop unsent text; already sent keys cannot be retracted.
No clipboard or system input method is used.

The final AppImage passed real microphone → verified local HTTPS → production
notification → owned GTK XWayland output and late-reply cancellation on a GNOME
Wayland host. Separate production checks covered switching windows mid-output,
partial cancellation, destroyed-window errors and an owned raw VTE terminal
without a shell. An owned Chrome XWayland diagnostic passed Unicode delivery.
These results do not establish arbitrary application support: native Wayland
GTK is unsupported by this backend, and the user's XWayland Codex input has not
been exercised. “Keys sent” reports dispatch, not acknowledgement by every app.

See [current-cursor acceptance](current-cursor-input-validation.md) for the final
artifact hash, exact commands, results, deployment status and limitations;
[keyboard transport evidence](keyboard-transport-validation.md) separates each
native target measurement. Build instructions are in [packaging](packaging.md).
Provider configuration, credentials and appearance are unchanged by this input
revision. Earlier release sections below retain their original input policy and
measurements; they do not describe alpha7's current behavior.

## Historical 0.1.0a6 — specific audio error feedback

This focused release preserves the recorder's specific, sanitized failure reason
through normal recording and microphone-test feedback. Missing devices,
unsupported formats, start failures, interruptions, empty input and recording
timeouts receive distinct explanations. Input routing, cancellation policy,
providers, dependencies and appearance are unchanged. Current package evidence
and the locked-native-session limitation are recorded in
[audio feedback validation](audio-feedback-validation.md).

## Earlier recording cancellation repair

This preview narrows accessibility-event handling to the captured target and
reports why a recording or pending result was cancelled. Unrelated application
lifecycle events must not cancel dictation, while real target focus changes,
caret changes and explicit cancellation continue to stop delivery. The exact
tested scope is recorded in [recording cancellation repair validation](listening-repair-release.md).

## Retained provider and appearance improvements

This preview aligns transcription requests with the configured model's supported
protocol and reports actionable Chinese configuration/service errors. Unsupported
realtime selections are rejected before recording or a capability request, rather
than sent through an incompatible ordinary HTTP chat endpoint. Dynamic discovery
still does not by itself establish a model's transcription capability.

The application uses the user's supplied logo artwork and a coordinated navy/white
palette for settings, tray and desktop integration. AppImage names now include the
exact package version: `InkEcho-0.1.0a6-x86_64.AppImage`. The stable legacy filename
is updated only after local acceptance; earlier versioned images are preserved.

The guarded AT-SPI input restrictions remain: target identity, editability, active
focus, cancellation and stale-result checks must all pass. Experimental Wayland
target checks do not imply universal browser/terminal compatibility. No clipboard
fallback is introduced. Keys remain in Secret Service; recordings and transcripts
are not retained by default.

The current checksum and package evidence are in the audio feedback report.
The earlier authenticated provider diagnostic is retained in
[provider repair release validation](provider-repair-release.md). Reproducible
build instructions are in [packaging](packaging.md).

## Historical alpha1 evidence

The following section records the original `0.1.0a1` release and its environment
on 2026-10-12. Its hashes, test counts and desktop state are historical and must
not be treated as acceptance of later releases.

This preview provides a complete settings application and the voice-input
pipeline: RAM-only microphone capture, configurable Qwen transcription,
optional DeepSeek/OpenAI-compatible polishing, cancellation, and guarded
AT-SPI delivery to supported editable targets. Cloud credentials are stored
in Secret Service; no transcript/audio history is saved. Desktop launcher
installation, path repair and explicitly enabled autostart are available.

The Python package version is `0.1.0a1`; the artifact filename uses
`InkEcho-0.1.0-alpha-x86_64.AppImage`. Source is MIT; bundled dependencies retain
their own licenses. Build/verification instructions are in [packaging](packaging.md).

## Scope and known limits

- Linux x86_64 preview. No Windows/macOS compatibility claim.
- Production injection is targeted AT-SPI EditableText delivery, with focus
  generation and task cancellation checks. Chromium and VTE targets that do
  not expose this interface are rejected. The earlier XTest feasibility probe
  is not a production global-key fallback. No clipboard fallback exists.
- Native Wayland unrestricted input is not enabled. The current native desktop
  is locked; no attempt was made to unlock it for final acceptance. Isolated
  Xvfb tests must not be reported as GNOME Wayland acceptance.
- Model IDs must be selected/configured and a real key provided. Local HTTPS
  simulated-service tests verify the documented request/response pipeline;
  authenticated Qwen/DeepSeek transcription quality has not been measured.
- Cloud transcription sends the recording to the configured service; optional
  polishing sends its transcript. Local metadata-only statistics/logs do not
  turn this into offline speech recognition.
- Ubuntu24 offscreen container startup proves userspace startup only. A real
  desktop must provide display/graphics, audio, D-Bus, accessibility and a
  usable Secret Service. Container audio-service warnings are expected because
  no audio device or desktop bus is mounted.

## Package evidence

Initial full-app package testing on 2026-10-12 passed all nine Chinese settings
pages under isolated Xvfb, with development Python/library environment removed.
Bundled imports passed for Qt Core/GUI/Widgets/Network/Multimedia/Svg, qasync,
D-Bus, Secret Service, httpx, certifi, cryptography native bindings and Python SSL.
The package is approximately 102.6 MiB after removing unused Qt modules and adding
Noto Sans CJK, utility libraries and license notices. The earlier stage-zero
artifact remains separately preserved at approximately 242 MiB.

Ubuntu24 offline/non-root/read-only full application startup also passed after
the clean-image check identified missing Kerberos libraries (now bundled) and
PulseAudio client libraries (declared desktop baseline). The final frozen artifact was built twice byte-identically (same host,
`mksquashfs 4.7.5`, unchanged inputs), with 107,547,128 bytes and SHA-256:

```text
cb35d203024538a4ee3d55c6ccb8619059ce9f4bfda387fd1b92e2291eec11a4
```

The final artifact passed Ubuntu24 again: `screenshots: 9`, `platform: offscreen`,
`visible: true`, clean exit. Captures are in `build/ubuntu24-qa.c4zzrz` on the
validation host. The bundled font renders Chinese on that image, which does
not install Noto. Inventory verification matched 3,883 regular files, 1,048
symbolic links, 25 runtime distributions and 59 retained Qt attribution pages.

A packaged AppDir pipeline check before the final freeze also passed actual
microphone → locally verified HTTPS ASR/polish → AT-SPI GTK target: exact 28
Unicode code points, overlay focus preserved, cancel and away/back late replies
unchanged. Three RAM WAV captures measured 18,422 / 19,786 / 17,738 bytes; no audio
files or clipboard access. The local service returns fixed text, so this is
pipeline and safety evidence, not live-cloud recognition-quality evidence.
The final AppImage also passed the independent desktop lifecycle driver:
nine 1120×850 pages visually inspected, actual single-instance show/toggle/cancel/
quit commands, clean primary exit, and damaged-config exit with original bytes
preserved. Evidence: `build/ui-acceptance-appimage-final/result.json`.
Independent final-artifact review repeated lifecycle checks with development
`PYTHONPATH`, `PYTHONHOME` and `LD_LIBRARY_PATH` removed, then extracted the exact
image and matched 31 application source files plus all 3,883 inventory hashes.
The extracted image's own Python and packages passed the full microphone → verified
local HTTPS → production Session → AT-SPI GTK workflow on private Xvfb `:92`:
28 Unicode codepoints delivered, overlay focus preserved, cancelled and away/back
late replies unchanged, 3 tasks / 1 success / 2 cancellations, 5/7/12 reported
tokens and real WAV payloads 17,738 / 18,422 / 18,422 bytes. No audio files or
clipboard access. The only external library was xdotool's test-helper library;
application dependencies came from the image.

Final evidence: `build/ui-root-final-appimage/result.json` and
`build/voice-root-final-appimage.json`. All 211 automated tests passed, with one
explicit opt-in microphone test skipped by default; actual microphone capture was
covered separately by the full pipeline. Ruff and formatting checks passed.
See [local validation](local-validation.md) and the
[acceptance checklist](acceptance-checklist.md) for scope and reproduction.
