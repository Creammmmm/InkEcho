# InkEcho 0.7.0 发布验证记录

状态：**候选实际 Dock 图标验收失败，0.7.0 不发布**。已有包与失败记录保留，后续修复不可改写该冻结包的结果。

## 精确来源与产物

- 准备分支：`codex/release-0.7.0`；父 main：`0dd7a3b` / 0.6.9。
- 发布源码提交：`be656ba639c4c7c4235fab686fd34c724a89d38a`；冻结包版本：0.7.0。
- 新 AppImage：`InkEcho-0.7.0-x86_64.AppImage`；SHA-256：`7159635e1d305b62e22ade9b334a72f6da225454b9e1e1cf2dfd8b070e33b7fe`。
- inventory SHA-256：`9234121896610fa44a46a887ab72613f6e06435045b9ee1c4461efcf7d35d7d2`；冻结清单 SHA-256：`8bc951af80ecb4a0ac22694d198e1e60c71f201abd356ca0442dc976d1c68e4a`。
- 0.6.8 旧包及其通过结果不属于本版验收。

## 同 SHA 实际包验收（Dock 失败，不能发布）

| 门 | Ubuntu 24.04.5 / GNOME 46 / Xorg | Ubuntu 26.04.1 / GNOME 50 / 原生 Wayland + XWayland |
|---|---|---|
| 实际 AppRun、配置页面与私有配置 | 通过 | 通过（实际 FUSE / 页面） |
| 本地协议 / 实时 / 手动 VAD | 通过 | 通过 |
| Recorder 首采样、开头标记与动画时序 | 合成标记通过 | 合成标记通过 |
| 实际 Dock 图标及资源恢复 | 失败：实际侧栏灰齿轮；资源已恢复 | 不新增该应用支持声明，见受控目标门 |
| 正常 / 取消 / 当前光标与映射恢复 | 通过 | 受控 native / XWayland 通过 |
| Files / Text Editor 渐进 Unicode | 通过 | 不新增该应用支持声明，见受控目标门 |
| Codex / Claude 真实离线 TUI | 本候选因 Dock 失败暂缓，未执行 | 不新增该应用支持声明，见受控目标门 |
| 包运行 / 私有真实 FUSE 启动 | 提取运行通过，不声明 guest FUSE | host 私有真实 FUSE 通过 |

每项补充原执行自然终态、包内来源、实际结果文件路径、画面 / 接收证据及清理结果。不把生产发送时间当作应用绘制时间，不以最终全文替代渐进证明；CLI 严格逐字重绘与完整渐进分别记录。包装器缺失的结果文件不得虚构。

## 明确限制与风险

- Ubuntu 24.04 本版输入支持范围须以实际 Xorg 结果为准；GNOME 46 原生 Wayland 未支持，不使用剪贴板或系统输入法回退。
- 26.04 既有受控 Chrome 输入框偶发 field blur 的根因未定位；保留失败与后续对照，不宣称本版已修复，不强制重新聚焦或降低 guard 门限。
- 真实录音 → 云 ASR → 目标应用端到端、物理麦克风开头与真实供应商识别准确率：未验。生成标记不能替代。
- CLI 合帧不等于按键批量提交，也不构成每帧单字符承诺。

## 发布与稳定入口（待执行）

待双系统同 SHA、host 实际 FUSE、原始证据和限制审阅通过后，记录 main 祖先关系、精确 tag、GitHub 草稿资产及远端下载校验，再记录正式发布地址。发布仅针对 GitHub，本机稳定入口保持旧版，不执行替换。当前未执行发布操作。后继报告提交按规范为 0.7.1，不重建或改标已验 0.7.0 包。

## 实际失败与单变量诊断

Ubuntu 24.04.5 / GNOME 46 / Xorg 实际包启动的 `build/ubuntu24-perf-vm/output/ubuntu24-release-dock-0.7.0-r1/dock.png` 经主 Agent 审图确认 Dock 显示灰齿轮，托盘品牌正常。`identity-observer.json` 的 Gio desktop、StartupWMClass 和主题图标文件均正确，Shell introspection 返回拒绝 9，不能把 Gio 解析成功当作 Shell 实际渲染通过。该次程序自然退出与资源恢复不表示图标验收通过。该 Shell 在 Dock 测试前已运行 entry / protocol / audio 的私有同 APP_ID 窗口，不是首次 InkEcho 窗口的冷注册对照；先行窗口缓存可能相关，尚未定位唯一根因。

随后独立 A/B 诊断只在运行后的自有 managed desktop 中，将 `Icon` 从主题名称改为持久 XDG 的 256px PNG 绝对路径，并原子重写 desktop；没有刷新图标缓存或重启 Shell。`build/ubuntu24-perf-vm/output/ubuntu24-release-dock-0.7.0-absolute-r1/dock.png` 实际品牌恢复；原执行 54205 的自然终态及资源恢复另见同目录 `terminal.json`。这同时包含 desktop 重写通知，**不能独断 Shell 缓存内部根因，也不代表原 0.7.0 产品已修复**。

后续源码 0.7.1 的最小修复使用持久 XDG managed PNG 的绝对 Icon 路径，按 desktop-string 规则转义反斜杠并拒绝控制字符，不引用 AppImage 临时挂载资源；保留 icons-before-entry、外来资源保护及启动不等待缓存刷新。新增 GIO 实际解析、特殊路径、旧 managed 项迁移 / 幂等与保护回归。本候选停止发布；修复须随新的 release 准备版本重新构建，以新 SHA 完成双系统及注册前冷启动 Dock 验收。GitHub 未发布，本机稳定旧入口未改。

## 26.04 新包原始证据独立审查

证据根目录为 `build/release-0.7.0/host-r1`。本版 source workflow 原执行8265自然0，1856 passed、2 skipped、49.27s；构建17879自然0。这不替代实际包验收。

| 新包门 | 原执行自然终态 | 实际结果文件 / 事实 |
|---|---|---|
| 私有 FUSE / 实际页面 | 64028 = 0 | `fuse-entry/{result,terminal}.json`，passed / actual_fuse，原 owner 自然结束；root已看page02 |
| 本地协议 | 69295 = 0 | `protocol/tool-result.json` passed=true / version0.7.0；首字早于润色完成，取消无尾部，0云请求 |
| VAD | 38989 = 0 | `vad/tool-result.json` status=passed，仅生成音频与本地协议 |
| Recorder / 动画 | 45299 = 0 | `audio/result.json` passed；首帧16.743/20.461/19.087ms，非零样本1600/1600/1601，动画前628B |
| native→XWayland 正常 | 1311 = 0 | `mixed-normal/tool-result.json`；native10/X1113各精确，总23按下/释放，非35 |
| native→XWayland 第14字取消 | 28859 = 0 | `mixed-cancel/tool-result.json`；native10/X114各精确，总14按下/释放、input_cancelled，无尾部 |

两项混合门 factory_used=true，both maps restored、guard_rejections=0，cleanup/fixture/guard错误均空、两接收进程各自然0；使用原未增强事件门，本版首次六门通过不消除旧0.6.8 field-blur风险。混合工具正常SystemExit0使外层result.json未落盘，依据完整tool-result及原terminal，不伪造外层文件。协议与VAD保留tool-result和外层result，音频保留result。

所有host preservation记录均为旧稳定入口SHA `bf0d802cf07dc8f874d6c4b6033db4919f4e86a2b9f1d14ea86c2b6f98586ed9` 前后相同；未更新本机稳定入口。24.04 本轮结果如下；Dock 失败未被其他门通过覆盖，不使用旧0.6.8结果填通过。


## 24.04 本候选已完成的检查

来源索引 `build/release-0.7.0/ubuntu24-progress.json`。提取60625、入口24332、协议81871、VAD78233、音频59745原执行均自然0；实际原始结果为 `build/ubuntu24-perf-vm/output/inkecho-candidate-0.7.0-r1/gates` 对应门的result/tool-result/terminal。合成首帧16.465/19.210/19.650ms，各1601非零样本、动画前624B，不代表物理麦克风认证。

Files mixed20901、long69572、cancel33229均自然0，发送耗时1072.524/1768.187/464.013ms，21/36/取消8字文件名精确并恢复，映射恢复且按键平衡；取消再观察700ms无尾部。root审阅实际渐进帧。Editor50552自然0，严格1..21/delta1，首末跨度900.016ms、中位45.334/最大52.406ms。当前光标正常28838、取消13246自然0，精确当前目标接收、映射恢复。原始证据位于同一 output 根的 `files-package-0.7.0-{mixed,long,cancel}-r1`、`editor-package-0.7.0-r1`、`ubuntu24-package-xorg-switch-0.7.0-r1`。

Dock 控制器68184自然0、资源恢复，但图像门失败，不得以自然退出0冒充图标通过；AB控制器54205自然0仅为诊断。真实CLI新包门因发布阻塞暂缓，未执行；旧0.6.8 CLI结果不能补作本版通过。

### 后续 0.7.1 源码定向回归

`tests/test_integration.py` 为 25 passed / 0.43s，包含真实系统 GIO 对空格、反斜杠、引号、美元及百分号路径的解析；旧 managed 主题项迁移后再次启动不重写，控制字符在写资源前拒绝。Ruff lint / format 通过。随后 integration + startup + startup shortcut health 在本地 socket 可用环境共 40 passed / 1.92s，原进程自然返回 0、90s 外限未触发，未发送信号。结果在 `build/release-0.7.0/publication/focused-startup-escalated.{json,log}`。这只验证后续源码，不构成图标新包桌面通过。

首次受限 sandbox 的 startup 回归无法建立本地通信，4 failed / 6 passed 后事件循环未退出；主 Agent 授权后校验精确 host PID / start / argv / 父进程，仅发送一次 SIGINT，原进程返回 2 并保留 KeyboardInterrupt（200.51s），确认自有 fixture 无残留后才重跑。该受限失败不当作产品失败或自然通过，过程证据在同 publication 目录的 `restricted-startup-*.json`。
