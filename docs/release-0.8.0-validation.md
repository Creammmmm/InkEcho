# InkEcho 0.8.0 发布验证记录

状态：同一 SHA 的双系统实际包验收已完成，等待发布前源码 / 证据审阅与 GitHub 资产流程；尚未发布。0.7.0 图标失败候选保留且未发布。

## 精确来源与产物

- 分支 `codex/release-0.8.0`；父源码 `63cb0cd` / 0.7.1。
- 发布源码提交：`3bf0c67c2c5e47ee94166cf44ea5e855c3b2e521`；目标元数据 0.8.0。
- `InkEcho-0.8.0-x86_64.AppImage` SHA-256：`0adb112bd5e955935a3dbc844f44a8165b5ea10bca0f4535b030acc9cd8be74b`。
- inventory SHA-256：`a8b8659078a5fdba4da4c494f730ac963c8c46ca097fdcdafefc7bd2e5e675f7`；清单 SHA-256：`39b1ec78d8e4ed65cf96793e0ac37c606f3c6e1fe6aa101587d6b34a69f7abbd`。
- source workflow 原55549自然0：1865 passed / 2 skipped，49.18s；构建原98362自然0。校验sidecar自身SHA-256：`2854f200c3f8b2f3421a845f2d68f3356cf8851cce3155dc2ac324eea8f027fa`。

## 同 SHA 包门实际结果

| 门 | Ubuntu24.04.5 / GNOME46 / Xorg | Ubuntu26.04.1 / GNOME50 / native + XWayland |
|---|---|---|
| Dock 该 Shell 首个 InkEcho 窗口 | 通过，首窗口实际品牌 / running dot，未预装或刷缓存 | 不新增应用认证 |
| 实际入口 / 配置页面 | 通过 | host FUSE / 页面通过 |
| 本地协议 / 实时 / 手动 VAD | 通过 | 通过 |
| Recorder / 标记 / 动画时序 | 通过 | 通过 |
| Dock 在 entry/protocol/audio 后复验 | 通过，原失败顺序后仍实际品牌 | 不新增应用认证 |
| 当前光标正常 / 取消 / 映射恢复 | 通过 | 受控 native / XWayland 通过 |
| Files mixed / long / cancel 与 Editor | 通过 | 不新增应用认证 |
| Codex / Claude 真实私有离线 TUI | 通过 | 不新增应用认证 |
| 实际包运行 | 提取运行通过，不宣称 guest FUSE | 私有真实 FUSE 通过 |

以下记录各门原进程自然终态、实际来源、截图 / 接收证据、资源恢复和原始路径。图标须审实际侧栏画面，不能以 Gio 解析或进程0替代。发送耗时与画面跨度分开，CLI progressive-full 与 strict每字帧分开。不得用0.7.0或0.6.8结果填新包通过，也不虚构未落盘的包装器文件。

## 必须保留的限制

24输入范围为Xorg；GNOME46原生Wayland未支持。26原生Wayland既有BMP范围，非BMP明确拒绝。26既有偶发field blur尚无根因定位，新门通过也不等于风险已修。真实物理麦克风开头 / 供应商准确率 / 录音→云ASR→目标应用端到端未验；本地协议和合成标记不替代。CLI可能合帧，不承诺每帧单字。

## 发布（待执行）

同SHA双系统、host FUSE与实际图标QA已通过；尚待最终源码检查、main祖先关系确认、精确tag、GitHub草稿资产上传及远端下载校验，当前未发布。本机旧稳定入口保持不变，不额外替换。本次QA报告为0.8.1；实际远端发布终态将另以0.8.2报告记录，均不重建已验0.8.0包。

## 26.04 同包六门独立审查

证据根 `build/release-0.8.0/host-r1`，六门首次原执行均自然0：FUSE13962（root看page05版本0.8.0）、protocol9880、VAD6733、audio38095、normal41036、cancel7011。独立读取每项terminal确认同包SHA及0终态，实际门结果passed/statuspassed，全部preservation unchanged。

normal实际native10/XWayland13精确、共23次按下/释放；cancel实际10/4精确、共14次按下/释放。两者maps恢复、guard/cleanup/fixture错误空，接收进程自然0。实际JSON为mixed-{normal,cancel}/tool-result.json，原terminal俱在；工具SystemExit0未生成外层result，不能虚构。FUSE/音频用result.json，协议/VAD有tool-result与result。

音频三轮首帧13.359/22.277/21.713ms，各1601非零样本，动画前628B、默认音频设备未改/自有模块清理。物理mic仍未验；本版六门首次通过不消除旧26fieldblur风险。24结果见下节，未以单系统或旧包结果替代。


## 24.04 全部门与真实应用结果

最终索引 `build/release-0.8.0/ubuntu24-progress.json` 绑定上述同包 SHA / 清单。提取43386、入口62736、协议25789、VAD72066、音频19267原执行均自然0；原始结果在 `build/ubuntu24-perf-vm/output/inkecho-candidate-0.8.0-r1/gates` 对应门的result/tool-result/terminal。采音首帧15.713/19.235/14.783ms，各1601非零样本、动画前624B；自有模块清理、默认设备未改，仍不是物理mic验收。

### 两种顺序的实际 Dock

冷基线 `build/ubuntu24-perf-vm/output/release-0.8.0-cold-ready-r1/state.json` 确认该Shell没有先行InkEcho窗口且9管理资源缺失。首窗口Dock原90328自然0；entry/protocol/VAD/audio私有同APP_ID窗口之后的复验原77533自然0。root分别审阅 `ubuntu24-release-dock-0.8.0-{cold,after-ui}-r1/dock.png`，均显示品牌图标、running dot及一致托盘；GIO FileIcon解析到持久XDG PNG，其SHA匹配冻结资产。没有覆盖Icon、刷新cache、修改主题或重启Shell来取得通过，两次管理的9路径均精确恢复，应用自然0。

这是新0.8.0产品从注册前起跑及原失败顺序的实际结果；0.7.0灰齿轮失败与绝对Icon重写实验仍保留，不倒写其候选通过，也不独断Shell内部唯一缓存根因。

### 真实输入与当前光标

| 场景 | 原执行自然终态 | 实际结果 |
|---|---|---|
| Files mixed21 | 18401 = 0 | 帧图渐进；发送1092.355ms，文件名精确并恢复 |
| Files long36 | 51012 = 0 | 跨批渐进；发送1802.983ms，文件名精确并恢复 |
| Files cancel8 | 59114 = 0 | 发送469.990ms；8字后再观察700ms无尾部 |
| GNOME Text Editor21 | 49267 = 0 | 完整1..21 / delta1，首末跨度920.621ms，中位45.780 / 最大50.769ms |
| 当前光标正常 | 64951 = 0 | A8 / B27分别精确、单字增长 |
| 当前光标取消14 | 89066 = 0 | A8 / B6分别精确，input_cancelled、无尾部 |

这些输入均按键平衡、映射恢复、应用 / 两接收器自然0。root审实际Files mixed05/09、cancel12帧和Editor完整观察JSON；Files不可用的AT-SPI Text链不虚构，发送时间不当作画面跨度。原始路径在同output根的 `files-package-0.8.0-{mixed,long,cancel}-r1`、`editor-package-0.8.0-r1` 与 `ubuntu24-package-xorg-switch-0.8.0-r1`，详见索引。

### 两个真实 CLI

Codex0.160.0原owner90752与Claude2.1.258原owner10426均自然0，CLIexit0、观察器清洁、cleanup通过、各21按下/释放、映射恢复，最终21字精确且progressive-full=true。严格每帧单字仍false，最大前缀增长均2，不能声称每帧只增1字。

Codex前缀 `1,2,3,4,5,6,8,9,10,11,13,15,16,17,18,19,20,21`，首末呈现906.318ms、发送1042.473ms；Claude前缀 `1,2,3,4,5,7,8,9,10,12,14,15,16,17,18,19,20,21`，首末呈现890.331ms、发送1038.823ms。root已看两个真实ready与最终完整正文截图。

原始路径 `build/ubuntu24-perf-vm/output/cli-tui-0.8.0-r1/{codex-package-r1,claude-package-r1}`。只复制固定真实二进制，私有本地ext4 HOME / cwd、正常引导、不绕权限，隔离网络只有DOWN的lo、固定假key；未按Enter提交正文或请求云端。Claude原两次正常Ctrl+C只清空输入未退出，单独审阅的身份 / 焦点guard助手再发送两次正常Ctrl+C后原CLI自然0；额外正常关闭事实独立保留，非强杀。

### 结束与版本边界

全部验收后正常 `systemctl poweroff`，SSH0、VM容器Exited0、非OOM、无强杀，结束时刻 `2026-10-21T17:53:59.938303467Z`。本机旧稳定入口未替换；发布仅GitHub。该QA报告提交按普通规则将三处开发元数据递增至0.8.1，**不重建 / 不改标上述已验0.8.0包**，tag应绑定精确3bf0c67发布源码。GitHub发布地址、远端资产hash及正式终态待实际操作后补，不提前写已发布。
