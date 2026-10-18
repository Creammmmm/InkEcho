# 多供应商适配：同包双 Ubuntu 验收

本页记录0.2.10候选包的实际验收；供应商协议依据、独立实现及各批源码测试见[适配记录](provider-adaptation-validation.md)。本轮没有发布新GitHub release或调用真实供应商账户。

## 固定来源

- 产品源码：`de504c6416feeaa69375ef2e60c4c6607d0f58e1`，版本0.2.10。该clean HEAD完整检查为1920 passed/3 skipped，63.65s，Ruff/format320通过；receipt evidence SHA-256为`deaa7d5da32fa3b5e508eed77a78654731fd5b7b4fa8e09067016db8548f7aa8`。
- AppImage：`dist/InkEcho-0.2.10-x86_64.AppImage`，108894712字节，SHA-256为`18b6ad26a39032d930a2f319cd497641639910f69cb3402da8ac75ee7d2a63bd`。sidecar SHA-256为`7b0847a246b26da0c0219cc77f1d6943f83b6f849fbd09b710af516b65e46b58`。
- 实际inventory为3970 files/1048 links；55产品文件完整集合及每个hash与冻结来源一致。显式30个模块来源加所有实际加载产品/运行依赖均须位于包内并符合inventory。
- 产品包不随后继诊断版本0.2.11/12/13重建；这些提交只修诊断来源、Qt内嵌来源或UI验收语义，并同步三处版本字段。实际产品仍固定上述0.2.10来源。

## 实际验证

| 环境 | 协议与桌面门 | 结果 |
| --- | --- | --- |
| Ubuntu 26.04.1，GNOME50.1 Wayland及XWayland | 实际包Python `-I`隔离收集226 IDs/0call，然后226实际本地TLS/WSS/SSE测试；25桌面门 | 协议226 passed/0 skipped/0 failed，20.61s；25原owner终态0；主Agent逐项raw及九页视觉审通过 |
| Ubuntu 24.04.5，GNOME46实际KVM Xorg会话 | 同SHA独立提取、同226 IDs协议门、9桌面门 | 协议226 passed/0 skipped/0 failed，22.98s；extract及两协议阶段、9桌面门共12原owner终态0；主Agent逐项raw及九页视觉审通过 |

协议测试固定五个模块及226 node IDs，使用冻结501文件的pytest诊断依赖，不把测试框架或InkEcho源码overlay进入产品运行库。前后完整source/inventory与所有加载来源检查；Qt内嵌模块须由真实loader、archive/member及库存libshiboken载体精确证明。仅收集不计协议执行成功。

Host25包含实际ProviderPage模型过滤与私有保存、本地Qwen WSS/HTTP、九页AppRun、原生与XWayland textarea/contenteditable/Unicode/nonBMP/取消/currentcursor、真实工厂100字/cancel8/cancel5/512字、受控10ACK边界双向混合路由及三项Session整合。三项整合是合成PCM→本地WSS→HTTPS SSE→真实Session/ManagedQtEventLoop→实际桌面后端软件按键事件，检查两种收尾顺序与真实cancel5；不是物理快捷键/硬件按键测试。正常整合first press早于session.finished，最终success晚于finished；自定义整句prompt精确检查，partial cancel不重放。

Host实际包单次100字输出scope为3001.087ms，首字98.526ms；这是本地固定文本的一次输出观测，不是识别、云延迟或多次性能均值。映射scope与最终恢复、guard、按压释放平衡、目标退出和无尾随均由原始收据核验。双向混合使用受控暂停边界，不外推为无暂停原子切换证明。

## 失败记录与诊断来源

框架准备最初错误排除pytest distribution-owned `py.py`，实际host R1在导入pytest前失败，0测试。R2收集226 IDs后，后置审计将PySide6内嵌虚拟路径误当物理文件而失败，0协议调用；均保留原wait1、日志及保护收据。诊断修复后R3隔离收集及226实际协议测试通过。详细carrier证据及失败历史见适配记录末节，不修改旧冻结快照或产品包。

桌面host R1首UI门要求旧tooltip提示，但新需求为过滤不兼容模型，因此失败并停组，其余24未执行。诊断改为HTTP/实时切换无重新发现即重过滤，并加纯文本/TTS负例、手填模型正确协议保存；新R2全25通过。旧失败保留，不宣称它是产品丢字或云连接失败。

原始材料位于`build/provider-acceptance-preparation`：`protocol-host-r3-{collection,tests}`、`results-r2`与LAB根`host-progress-r2.json`；冻结来源413文件、选定测试manifest与外置helper provenance各自独立pin。复现须先按固定preview核artifact、全部文件hash与私有目录，运行原owner等待终态，失败停，不自动重跑。不得使用宿主site-packages或把源码导入冒充实际包。

## 交付与限制

同SHA双系统协议与桌面门均已通过。随后在host仅启动版本化候选的私有配置实例，实际FUSE mount读取0.2.10/inventory3970 files1048 links与55源码hash、九页截图，原Popen终态0且保护值一致；未使用提取AppRun冒充FUSE。原始收据为`build/provider-acceptance-preparation/candidate-fuse-r1/result.json`。在双系统、候选FUSE及报告经主Agent核验后，仅备份并暂存校验、替换稳定AppImage与sidecar两文件，原owner终态0。稳定路径`dist/InkEcho-0.1.0-alpha-x86_64.AppImage`现SHA-256为上述18b6ad26候选；`deployment-r1/result.json`为passed，其他57路径逐hash保全，备份在`build/provider-acceptance-preparation/deployment-r1/backups`。配置、launcher、图标、缓存、自启动与既有版本包不变，不控制正在运行的用户实例。旧stableFUSE计划保留为未执行，不重复同SHA启动。

云测试只使用合成本地TLS/WSS/SSE；真实账户鉴权、配额、模型权限及服务端字段变化未认证。未测物理麦克风、物理快捷键、真实云ASR/润色、Ubuntu24原生Wayland或guest FUSE。GNOME46原生输入仍不支持，本次24.04范围为Xorg；不能把容器或离屏协议检查称作桌面输入支持。未使用剪贴板或系统输入法，没有控制用户应用窗口或读取真实密钥。

最终分支合并与推送由主Agent在精确最终HEAD完整检查后执行并核远端；此处不预写尚未发生的合并结果，也不为最终remote hash再制造文档提交。
