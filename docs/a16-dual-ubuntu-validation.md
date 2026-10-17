# a16 同包双 Ubuntu 实际验收

本页记录 `0.1.0a16` AppImage 的实际包验收。源码提速试验、未采用的缓存/并行方案及阶段 0 单槽验证见 [原生 Wayland 双槽优化](native-wayland-batch-optimization.md)。这些源码结果与本页包结果分开记录。

## 产物与可复现入口

- 产品提交：`f835e9d159925959527044193216f6d3de02b562`。
- 产物：`dist/InkEcho-0.1.0a16-x86_64.AppImage`，108866040 字节。
- 两系统使用相同 SHA-256：`5e0c39a8a77faf8d846b0cb915cf4345b619dbd205504498496ec8fa590ec320`。
- 独立构建与提取均由原 Popen 等待退出 0，未重新构建或重试输入。提取后核对 inventory 的 3959 个文件、1048 个链接及提交中的全部 44 个产品文件；inventory SHA 为 `dc8875e47f5701919c88534f81cd19d678410900c633b474255babad47dacf7c`，application 为 `0.1.0a16`。
- `build/a16-acceptance-preparation/frozen-r1-manifest.json` 冻结该提交全部 382 个 tracked 文件，SHA 为 `8fba0b0cfab6c7fcfccf84bd362cfb7cc903a0ad538846353e85277772467060`。运行时使用实际包 Python/依赖及产品模块，不以源码覆盖包；19 个模块来源包含真实 Hybrid 工厂路由。

正式源码前置检查使用 `scripts/validation/workflow.py run --module native-batch --evidence docs/native-wayland-batch-optimization.md`，精确 clean HEAD f835e9d：Ruff、290 文件格式检查及 1574 passed / 3 skipped（40.86 秒）通过。收据位于 `.git/validation/f835e9d159925959527044193216f6d3de02b562.json`。这是源码/打包前收据，不代替以下两系统实际包门。

构建固定命令为 `env -u SOURCE_DATE_EPOCH .venv/bin/python scripts/packaging/build_appimage.py`。验收逐项命令及私有环境固定在 `host-preview-r1.json`、`guest-plan-r2.json`；host 用 `approved-host-owner-r1.py MODE`，guest 用 `approved-guest-dispatch-r2.py MODE`，均位于 `build/a16-acceptance-preparation/`。必须先检查清单 hash、创建新的工作/结果路径并审核后运行，不能直接覆盖本次证据。guest SSH owner 采用实际已解锁 Xorg 会话，AppRun 清除开发变量并使用独立配置；不读取凭据、使用麦克风或请求云端。

## 实际结果

| 系统及会话 | 通过范围 | 原进程终态 |
| --- | --- | --- |
| Ubuntu 26.04，GNOME 50.1 Wayland，native 与 XWayland | 21 项：界面/协议、local HTTP+WSS、native 5、AppRun 九页、XWayland 4、真实工厂 4、受控双方向切换 4、额外 native cancel7 | 21 个原 owner 均等待退出 0，每项保全一致 |
| Ubuntu 24.04.5 LTS，kernel 6.8.0-142，GNOME 46.0，session20 Xorg | 独立提取及 9 项：界面/协议、local HTTP+WSS、AppRun 九页、Xorg 4、真实工厂 normal/cancel8 | 提取和 9 项本地 SSH/guest 两层原 owner 均等待退出 0，每项保全一致 |

普通、contenteditable、混合 Unicode、partial cancel、输出时光标位置及工厂路由均按各门检查。输入门精确读回、真实 press/release 平衡、guard 拒绝 0；scope 与最终映射恢复、worker/target 原 wait、清理门通过。cancel8 及额外 cancel7 都从完整 100 字单次 insert 请求中实际中止；cancel7 第八字只作为未发出的 hint，最终仅 7 字，0.5 秒观察无尾随。

包内 native 普通 100 字单次测量：总输出 scope **6972.585 ms**，首字 **68.228 ms**，**14.342 字/秒**，100 次成功 press/release。此为一次实际包样本，包含自有目标守卫成本；不能把源码三轮均值 7064.025 ms 当成包均值或跨应用可靠性统计。源码普通三轮从 10057.854 ms 降至 7064.025 ms（约 29.77%），仅作独立源码证据。Ubuntu24 Xorg 工厂普通样本 100 字为 5013.421 ms；它与 native 使用不同后端，不能直接归因双槽优化。

mixed 四项按已确认前缀 10 字的受控暂停边界切换，再验证后续文本及取消 14。这证明已检查边界下不重放及恢复，不证明无暂停原子切换，也不是切换吞吐量测量。两系统九页截图已保存；host 是私有默认配置，并非用户现有配置。

## 证据及失败历史

- 构建：`build/a16-build-preparation/build-r1-{owner,terminal}.json`、`extract-r1-{owner,terminal}.json`、`build-result-readonly-r2.json`。
- Host：`build/a16-acceptance-preparation/results-r1/`、`host-progress-r1.json`、`host-summary-r1.json`、`host-pages-contact.png`。
- Guest：`build/ubuntu24-perf-vm/output/a16-acceptance-r2/`、`build/a16-acceptance-preparation/guest-owner-results-r2/`、`guest-summary-r2.json`、`guest-pages-contact.png`。
- 汇总：`build/a16-acceptance-preparation/dual-os-results-r1.json`。owned 目标正常关闭，所有原 owner 正常等待；未控制用户应用。

构建 controller 首次汇总把 inventory.application 字符串误作字典，发生 TypeError；此前实际构建/提取已退出 0，文件/链接/源码校验已通过。保留原失败，只独立只读纠正汇总，未重建或重新提取。

Guest 初次 R1 stage 使用 copyfile 丢失可执行权限（原文件 0755、stage 0664），extract 在创建实际子进程之前失败，local SSH exit2，未产生 inner owner/terminal，无 GUI/输入。保留 R1 空日志及失败收据；只修该自有 stage artifact 权限为 0755，字节 SHA 不变。R2 使用新的 owner/plan/output/runtime 路径执行，未覆盖旧失败。其余 386 文件内容不变，仅追加两个获审 R2 owner/plan。此为测试准备错误，不把旧失败改成通过。

## 交付边界

同 SHA 的 Ubuntu26 native/XWayland 与 Ubuntu24 Xorg 包门已通过。按独立获审计划，稳定入口 `dist/InkEcho-0.1.0-alpha-x86_64.AppImage` 及其 sidecar 已更新至上述 a16 SHA；两文件均先备份至 `build/a16-acceptance-preparation/deployment-r1/backups/`，完整暂存校验后逐文件原子替换。旧版本产物及另外 49 个路径（包括配置、启动器、图标和缓存）全部保持校验一致；未重启或控制用户实例。本次未创建新的 GitHub release。

随后从该稳定路径以全新私有配置执行真实 FUSE 启动，观察到自有进程 `/tmp/.mount_InkEchLCdjEi` 下实际 a16，inventory、3959 文件、1048 链接及 44 产品源均匹配。九页截图和原 Popen wait0、before/after 保全通过；证据为 `build/a16-acceptance-preparation/private-fuse-r1/result.json`、`terminal.json`、`pages/`。私有默认配置中的安装状态不用于判断用户实际 managed launcher 是否存在。部署证据为同目录 `deployment-r1/result.json`。

GNOME46 的原生 Wayland 仍不支持，不能由 guest Xorg 成功推断支持。未实测物理快捷键、真实麦克风、认证云端服务、guest FUSE；截图及本地模拟协议也不能替代这些门。host 私有稳定入口 FUSE 启动已按上述范围实测。构建及验收期间保留旧 stable/a15/a14、用户配置、启动集成、图标和缓存；不使用剪贴板或系统输入法。
