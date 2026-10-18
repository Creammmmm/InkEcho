# a17 四槽同包双 Ubuntu 验收

本页记录 `0.1.0a17` 实际 AppImage 验收。四槽采用132/97/197/202，hint最多3且从不自行发送，逐字ACK/取消/原等待保持；源码三轮对照、单槽探测失败和八槽候选不足的结论见 [多槽源码验证](native-wayland-multislot-optimization.md)。本包不宣称八槽或六槽组合支持。

## 产物与复现身份

- 产品提交：`d44d21ec37d29c8747e8f2a123f85cad1908be22`，功能提交 `4046d6e`。
- `dist/InkEcho-0.1.0a17-x86_64.AppImage`：108866040字节；两系统使用同一 SHA-256 `6d547ecdce671c06f9e153e2f55694a6085de3e473d75a356550dbd97619fbd6`。
- 唯一构建及独立提取均由原Popen等待退出0；inventory application字符串为`0.1.0a17`，SHA `5afd49f8f1543015e060760839508b0b25fed868f3c9051c29da201201a8b4c1`。逐项核对3959文件、1048链接、44产品源与提交匹配。
- `build/a17-acceptance-preparation/frozen-r1-manifest.json` 冻结exact提交384个tracked文件，SHA `0aacb0edc1c1f0e4ffd72099a8a13927f8a3d8ec511210c76eda772ddefc47ea`。实际运行包Python、依赖及产品模块，19个来源包含真实Hybrid工厂；不以源码覆盖包。
- clean HEAD源码前置workflow：`scripts/validation/workflow.py run --module native-four --evidence docs/native-wayland-multislot-optimization.md`，d44d21e的Ruff、292文件格式检查和 **1582passed/3skipped，41.22秒**通过，收据 `.git/validation/d44d21ec37d29c8747e8f2a123f85cad1908be22.json`。这不代替以下双系统实际包门。

构建使用 `env -u SOURCE_DATE_EPOCH .venv/bin/python scripts/packaging/build_appimage.py`。精确逐项argv、私有环境与hash固定在 `build/a17-acceptance-preparation/host-preview-r1.json`、`guest-plan.json`、`guest-stage-preview-r1.json`。Host入口 `approved-host-owner-r1.py MODE`；guest入口 `approved-guest-dispatch.py MODE`，两层原owner正常wait。重测须新路径并审核模板，不能覆盖本次证据。Guest按copy2传输388个精确文件，stage artifact预先验证0755和同SHA，再独立提取；不重复a16初次stage权限错误。

## 实际结果

| 环境 | 验收范围 | 结果 |
| --- | --- | --- |
| Ubuntu26.04、GNOME50.1、Wayland，native及XWayland | 21项：UI/协议、local HTTP+WSS、native5、AppRun九页、XWayland4、真实工厂4、受控双方向mixed4、额外cancel5 | 全通过，21原owner wait0，每项保全一致 |
| Ubuntu24.04.5 LTS、kernel6.8.0-142、GNOME46.0，真实session20 Xorg且未锁定 | 独立提取及9项：UI/协议、local HTTP+WSS、AppRun九页、Xorg4、真实工厂normal/cancel8 | 提取及9项本地SSH/guest两层原owner wait0，每项保全一致 |

所有输入门按各自样本精确读回、实际press/release平衡、guard0、scope和最终映射恢复、worker/target正常退出、cleanup空。混合Unicode、contenteditable、partial cancel与输出当时光标位置均有对应实际门。额外cancel5仍提交完整100字单次insert，实际只发5字，后3字仅预备hint；0.5秒观察无尾随，恢复完整。每字发送确认仍为1，没有一次自动发送4字。

**实际包native普通100字单样本**：总scope **5357.479ms**，首字 **71.750ms**，**18.665字符/秒**，100成功press/release、guard0。源码同环境三轮两槽均值7024.206ms、四槽5397.927ms，减少23.152%；两者分别是包单样本与源码三轮对照，不能混作包均值或任意应用统计。Guest Xorg工厂100字单样本5011.676ms，后端不同，不能据此衡量native槽优化。

Mixed仍是已确认前缀10字暂停、自然启动新自有目标ready后的受控边界（normal23/cancel14，两方向），不能称无暂停原子切换、真实任意时机竞态或切换吞吐。九页中文、图标、布局和版本分别存图；它们使用私有默认配置，不是用户现有配置。

## 证据与交付范围

- 构建：`build/a17-build-preparation/build-result-r1.json`、`build-r1-{owner,terminal}.json`、`extract-r1-{owner,terminal}.json`、无GUI包19来源审计 `package-audit-preview-r1.json`。
- Host：`build/a17-acceptance-preparation/results-r1/`、`host-summary-r1.json`、`host-pages-contact.png`。
- Guest：`build/ubuntu24-perf-vm/output/a17-acceptance-r1/`、`build/a17-acceptance-preparation/guest-owner-results-r1/`、`guest-summary-r1.json`、`guest-pages-contact.png`。
- 同包汇总：`build/a17-acceptance-preparation/dual-os-results-r1.json`。本轮所有包case首次完成，无输入失败重试；历史源码103读回失败及旧mixed外层manifest误pin均保留在源码报告，不能倒填为包失败或抹除。

两系统同SHA包门已通过。按独立获审计划，稳定入口 `dist/InkEcho-0.1.0-alpha-x86_64.AppImage` 及sidecar已更新至上述a17 SHA；旧两文件先备份至 `build/a17-acceptance-preparation/deployment-r1/backups/`，完整暂存校验后逐文件原子替换。其余51路径（含全部版本产物、配置、启动器、图标及缓存）保全一致。证据为同目录 `deployment-r1/result.json`；未控制用户实例，本次未创建新GitHub release。

随后从该稳定路径以全新私有配置实际FUSE启动，观察到自有进程挂载 `/tmp/.mount_InkEchDlcGgB` 内的a17，inventory、3959文件、1048链接及44产品源完整匹配；九页截图、原Popen wait0及before/after保全通过。证据为 `build/a17-acceptance-preparation/private-fuse-r1/{result,terminal}.json` 和 `pages/`。私有默认配置的安装状态不用于判断用户实际managed launcher是否存在。

GNOME46原生Wayland仍不支持；guest Xorg成功不改变此结论。物理快捷键、真实麦克风、认证云服务及guest FUSE未实测；local HTTP/WSS成功不能代替认证云端或真实录音。host稳定路径私有FUSE已按上述隔离范围实测。本次未读密钥、未使用剪贴板或系统输入法。
