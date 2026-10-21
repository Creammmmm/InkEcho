# InkEcho 0.8.0 发布验证记录

状态：准备中，尚未构建 / 实际包验收，不可发布。0.7.0 图标失败候选保留且未发布。

## 来源与产物（待填）

- 分支 `codex/release-0.8.0`；父源码 `63cb0cd` / 0.7.1。
- 发布源码提交：待提交；目标元数据 0.8.0。
- `InkEcho-0.8.0-x86_64.AppImage` SHA-256：待构建。
- inventory / 验证清单 SHA-256：待冻结。
- source workflow / 构建原执行终态：待执行。

## 同 SHA 包门（待验）

| 门 | Ubuntu24.04.5 / GNOME46 / Xorg | Ubuntu26.04.1 / GNOME50 / native + XWayland |
|---|---|---|
| Dock 该 Shell 首个 InkEcho 窗口 | 待验，禁止先预装新入口 / 刷缓存 | 不新增应用认证 |
| 实际入口 / 配置页面 | 待验 | host FUSE / 页面待验 |
| 本地协议 / 实时 / 手动 VAD | 待验 | 待验 |
| Recorder / 标记 / 动画时序 | 待验 | 待验 |
| Dock 在 entry/protocol/audio 后复验 | 待验，保留先前失败顺序 | 不新增应用认证 |
| 当前光标正常 / 取消 / 映射恢复 | 待验 | 受控 native / XWayland 待验 |
| Files mixed / long / cancel 与 Editor | 待验 | 不新增应用认证 |
| Codex / Claude 真实私有离线 TUI | 待验 | 不新增应用认证 |
| 实际包运行 | 提取运行待验，不宣称 guest FUSE | 私有真实 FUSE 待验 |

逐门填写原进程自然终态、实际来源、截图 / 接收证据、资源恢复和原始路径。图标须审实际侧栏画面，不能以 Gio 解析或进程0替代。发送耗时与画面跨度分开，CLI progressive-full 与 strict每字帧分开。不得用0.7.0或0.6.8结果填新包通过，也不虚构未落盘的包装器文件。

## 必须保留的限制

24输入范围为Xorg；GNOME46原生Wayland未支持。26原生Wayland既有BMP范围，非BMP明确拒绝。26既有偶发field blur尚无根因定位，新门通过也不等于风险已修。真实物理麦克风开头 / 供应商准确率 / 录音→云ASR→目标应用端到端未验；本地协议和合成标记不替代。CLI可能合帧，不承诺每帧单字。

## 发布（待执行）

待上述同SHA双系统、host FUSE、实际图标与证据审阅完成后，记录main祖先关系、精确tag、GitHub草稿资产、远端下载校验及正式发布地址。本机旧稳定入口保持不变，不额外替换。后继报告为0.8.1，不重建已验0.8.0包。
