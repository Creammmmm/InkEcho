# a18 输入等待与识别收尾重叠的同包双 Ubuntu 验收

本页记录 `0.1.0a18` 实际 AppImage 验收。原生释放等待从30改为10 ms，首次映射50 ms、后续映射30 ms和四槽/逐字ACK不变；可信整句最终转写可提前启动原有流式润色与输出，同时监督ASR协议收尾。源码对照见[释放等待](native-wayland-release-pacing.md)及[整句完成重叠](realtime-completion-overlap.md)。这不是多段边说边润色，也未增加八槽。

## 产物与来源

- 产品提交 `0a9d8c648e72e4b1461281e0f1c5033568f4a5cf`，A功能提交 `9ffa33e`、B功能提交 `48b2ce5`；metadata仅三处a17→a18。
- `dist/InkEcho-0.1.0a18-x86_64.AppImage`：108870136字节，两系统同SHA-256 `7645b01c6fb4977a9644506cf388d6b39272ee77fb19437e2930d78d96fe993d`。
- 唯一构建和独立提取均由原Popen wait0。inventory application为`0.1.0a18`，SHA `dc93c366aaa61444ac24d2834398698249c2db4ae51d2868778ac11b3df8e075`，逐项核验3959文件、1048链接、44产品源。
- `build/a18-acceptance-preparation/frozen-r1-manifest.json` SHA `ffad964f189a2a4d81d78f077d1fe1f0e9e562063b86478c15f3b2fa1c455c2a`，冻结该提交388个tracked文件及44产品源。实际使用包解释器/依赖/产品，19个模块来源包含真实Hybrid工厂，无源码覆盖包。
- 正式clean HEAD源码workflow为 `run --module latency --evidence docs/realtime-completion-overlap.md`，收据 `.git/validation/0a9d8c648e72e4b1461281e0f1c5033568f4a5cf.json`；Ruff/296文件format及1605 passed、3 skipped /39.93s通过。它不替代双系统实际包门。

构建命令为 `env -u SOURCE_DATE_EPOCH .venv/bin/python scripts/packaging/build_appimage.py`。a18构建计划R1误留旧`proposed_source_after_version`字典，尚未构建即发现；保留R1，以独立R2 `abc0bf466708b4ccd63cc60bdb0d9bc466ec52b2c5aff0e56c8c08ae9a9bd5b8`修正后44哈希再构建，三metadata预期与53保全未变。uv离线检查初遇缓存只读，授权原命令通过，未改依赖绕过。

## 实际包结果

| 环境 | 有限范围 | 结果 |
| --- | --- | --- |
| Ubuntu26.04、GNOME50.1、Wayland native及XWayland | 25个不同必需门：原21项UI/本地协议/native5/AppRun九页/XWayland4/工厂4/mixed4/cancel5，另native512及真实Session流水线3 | 25个有效成功门，各原owner wait0/保全一致；另保留3个前置失败尝试 |
| Ubuntu24.04.5、GNOME46.0，真实session20 Xorg且未锁定 | 独立提取加9项UI/本地HTTP+WSS/AppRun九页/Xorg4/真实工厂normal及cancel8 | 提取加9项本地SSH和guest两层原owner wait0，各保全一致 |

Guest按copy2传输392个精确文件，预先核同SHA及0755再独立提取，未覆旧stage。主机未完成的门不冒充guest成功，guest作为独立环境在无主机GUI活动时完成。九页中文、图标、布局与a18版本分别存图并经视觉复核；使用私有默认配置，不是用户现有配置。

各输入成功门均按对应样本精确读回、真实软件按下/释放平衡、guard0、作用域及最终映射恢复、worker/目标原wait0、清理无误。cancel5提交完整100字，实际仅发5字，预备hint不自行发出，500ms无尾随。Mixed仍是确认前缀10字暂停、自然新建目标ready后的受控切换，normal23/cancel14，两方向；不宣称无暂停原子切换或任意切换竞态验证。

实际包native普通100字**单样本**scope **3307.207ms**，首字 **70.912ms**，30.237字/秒，100/100/100、guard0和全恢复。512字混合Unicode/标点/空格/换行单样本 **16683.775ms**，512/512/512、guard0和全恢复。源码三轮30/20/10 ms均值分别5486.926/4312.455/3350.912 ms，10相对30减少38.93%；不能把源码均值与包单样本混为包均值，也不把有限自有窗口当任意应用可靠性统计。

## 实际 Session、本地协议与原生工厂闭环

三个附加门使用合成PCM、验证TLS的localhost WSS/HTTPS SSE、真实Session/ManagedQtEventLoop/ProviderClient/QwenRealtimeSession与实际`keyboard_for_desktop()`，仅向自有Chrome native textarea发送软件键事件。自定义system prompt与完整user整句逐项精确核对。以下时间为各helper起点相对ms，包含本地协议开销，不与纯打字scope混算：

| 顺序 | completed | 首次软件press | SSE结束 | 输出scope关闭 | session.finished | 最终success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SSE先结束 | 100.463 | 216.469 | 230.845 | 3411.917 | 3412.011 | 3414.655 |
| ASR收尾先结束 | 129.488 | 243.605 | 256.745 | 3521.928 | 256.135 | 3522.763 |

两normal均精确100/100/100、guard0、全恢复；firstpress早于finished，而success晚于finished。cancel5是真正Session `cancelled`，精确5/5/5、guard0、无尾随且全恢复；不是把输入失败当取消。`physical_keyboard:true`字段在此仅指实际桌面后端的软件按键事件，不表示物理硬件按键或快捷键已测。

服务器故意控制完成顺序以验证生命周期，不能把约3秒的受控finished延后当真实云端收益。保持manual单commit，只使用可信整句completed；部分转写不输出。最终成功仍确认finished和全文一致，尝试后不fallback/重放。

## 保留的三次主机前置失败

1. R1 `native-textarea` 首次守卫拒绝：0press/0release、guard1、suppressed-unattempted-release1；worker/Chrome0，原图精确恢复、清理及保全正常。旧工具未保存细分flags，原因未知，不能归因10ms或产品丢字。独立R2只增加双fresh100ms、正式baseline及失败诊断，guard250ms和输出不变，新case精确29通过；未重跑UI/local成功门。
2. 余22 R2的`x11-textarea`在任何输出/映射写入前失败，全部相关计数0，driver关闭、Chrome0/保全正常；旧generic错误未记录phase，原因未知，X后端未因本次release10而改变。新X R3保留10s owned-focus门，仅双fresh100ms及失败only16份布尔/age/安全错误类型，新case31平衡通过。原失败不覆盖。
3. 余16 R3的`factory-mixed-native-to-x-normal`首次native key守卫拒绝，0press/0release、guard1、尚未切换，cancel/close ACK、worker/Chrome0、双map恢复、清理和保全正常。旧单份ready与失败allowed合并位不足以确定细分原因。R4仅复用源码阶段已验的每目标连续fresh100ms、正式baseline及失败16份flags；guard250ms、受控10ACK边界与产品不变。独立新case和剩三mixed均通过，成功门不重跑。

每次失败均停止对应组，原raw/owner/terminal保留；没有未知按键重放、窗口激活、强杀或产品重建洗白。25个有效成功门分组为2+1+5+1+7+4+1+4；三次旧失败不计入成功数。各新实验有独立输出路径和已审模板。

## 复现材料与交付边界

完整精确argv、私有环境和pins在 `build/a18-acceptance-preparation/`：原host-preview-r1、host-ready-preview-r2、host-remaining-preview-r2、host-xready-preview-r3、host-remaining-preview-r3、host-independent-preview-r4、host-mixed-ready-preview-r4、host-final-preview-r4及各original owner/runner。汇总为`host-summary-r1.json`、`guest-summary-r1.json`、`dual-os-results-r1.json`，输入raw分别位于同名results目录，失败原路径保留。Guest在`build/ubuntu24-perf-vm/output/a18-acceptance-r1/`，本地SSH owners在`guest-owner-results-r1/`。

真实pipeline辅助目前仅保存在ignored实验材料，非clone自带validator：`native_pipeline_adapter_r1.py` SHA `c843fdef1ae28ba5b0e1ff86a2732ae0a5a19f1fdf0d83d08c449a00be308f88`；薄接线`input_speed_probe_pipeline.py` SHA `1b9f48e77ec662c3594aadc1e9c639dbf789c2e9bdb2e5cb33eee787bacad17c`。新克隆不能仅靠这些相对路径重跑实际桌面门；需取得这些精确材料、重新审模板及fresh路径。仓库内`tests/test_application_early_realtime.py -k actual_local`可复现合成本地TLS协议门，不能冒充真实桌面输入。

同包双系统有效门完成并经独立审阅后，已执行获审两文件计划：稳定入口 `dist/InkEcho-0.1.0-alpha-x86_64.AppImage` 及sidecar更新为上述a18 SHA，原执行句柄30327退出0。计划`deployment-plan-r1.json` SHA `354e7a826cd52cef35ba059b74f8814bee309804c9a6aa37c62186c128fd3342`只更新stable AppImage与sidecar，先备份，两文件完整暂存校验后逐文件原子替换，其余53路径含配置、旧产物、启动器、图标、缓存逐hash保全一致；不控制用户实例。备份在`build/a18-acceptance-preparation/deployment-r1/backups/`，结果`deployment-r1/result.json`记录stable SHA及sidecar SHA `f6be866abe3012be4215715b40bda469647e34171a38efc8238ee37b22df8bdb`。

FUSE私有启动预览SHA `e24ca687119feee3550db325f07fb40df8a965902d85619eec3e4856c5e97e84`及observer SHA `7a69135fec83a0e7ef7d34da4b7382e7ea086ec6a7267239c99df649fa41c99c`已实际执行，原observer句柄74392退出0；私有子进程991603/start49779460原Popen wait0，实际FUSE挂载 `/tmp/.mount_InkEchHnaAkk` 内a18，inventory/3959文件/1048链接/44产品源匹配，九页与53保全通过。结果在`private-fuse-r1/{result,terminal}.json`和`pages/`，page09已视觉复核；私有配置显示安装状态不用于判断用户managed launcher。准备初版observer的全局版本字符串替换误及旧hex内部，导致测试pin没更新，执行前发现并仅修pin；未执行原稿按旧SHA `d20734f00d8892d7e6e87390ae23a1f5b6575b5cd38a45af8d50d0f3f36d0793`留存`verify-private-fuse-unexecuted-r0.py`。这是测试准备错误，不是包启动失败。

GNOME46原生Wayland仍不支持，guest Xorg成功不改变结论。物理快捷键、真实麦克风、认证云服务及guest FUSE未测；host稳定路径私有FUSE已按上述私有范围实测。本次不读用户密钥，不使用剪贴板或系统输入法，未创建新GitHub release。
