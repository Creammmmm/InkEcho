# 输入提速：实施与验收追踪

2026-10-18。目标是在不使用剪贴板或系统输入法的前提下，按顺序实践安全后端路由、
原生事务/映射复用、分阶段等待校准，取得实际输入提速，并保留当前光标、取消与
不重放语义。**阶段1源码有限验收已通过**：冻结A稳态和受控mixed提供有限实际
输出证据，当前默认factory接线、188项focused检查及1478项完整自动测试通过。
实际A测试是显式构造Hybrid，不是最终包默认factory的自动桌面验收；历史false和
scope限制保留。**阶段2源码有限实际验收已通过**：主 Agent独立工作树全套1513项
通过，24项单后端对照及B的4项受控跨后端交接均通过。普通文本事务由7次减少为
1次，原生重复文本在本次70ms供给下约14.5秒→7秒；受控交接不证明无暂停切窗原子性。
不把单对差异作普遍速度或可靠性分布结论。阶段2检查点1cffa59的完整clean-HEAD
工作流已通过1513项；阶段3参数实验56项实际通过，当前源码采用X3/N3等待设置。
可复用CLI的R1烟测第3项失败/例外SIGINT终exit1保留；R2当前defaults真实factory四项通过。
阶段3提交d49c64d的clean-HEAD完整检查已通过1536项、3跳过（39.50秒）。
[a15同包验收](a15-dual-ubuntu-validation.md)已由主 Agent审查：产品来源27aef8c，
同SHA `b92ffd979f2faa979a22e9fd9a0be8cd187607009bd42313ef34fd91e660a598`，
host20项与guest9项实际包门通过；范围分别为host原生Wayland/XWayland与guestXorg。
稳定入口仍为a14，新报告/验证器最终提交检查及部署尚待完成。

## 已有基线与本轮边界

[a14输入基线](input-speed-baseline-a14.md)保留原始结果：本机GNOME Wayland默认
原生路径三次100码点样本的中位吞吐为7.037码点/秒；工具直接调用X11后端的
XWayland对照为13.840码点/秒。两组均准确读回并通过取消、按键与映射恢复。
a14产品来源为 `43c20edcd652020bfe51b959b85f2f90d8b75059`，包SHA256为
`bce09c895d51c01c11c73b67aef709632a7514545f0a7fdb6114748c70c8cc96`。

旧应用在GNOME Wayland固定选择原生后端；仅切换Chrome为XWayland不会自动获得
对照组速度。因此13.840不是新路由已经带来的产品收益。a14及其已验收记录保持历史
范围，不把后续源码或新包结果回填旧包。OpenLess机制比较也保留在基线报告中，
不以不同操作系统或输入法/粘贴实现的等待常量作同约束实测倍数。

本轮先验证输入后端与当前光标路由；不要求通过新增云请求、真实录音或密钥访问证明
键盘速度。不修改用户快捷键、录音设置或供应商配置来制造性能差异。

## 不得削弱的行为

- 开始录音不捕获或检查输入目标；录音、转写、润色期间焦点变化不取消任务。
- 字符发往发送时的当前光标，输出中可切换native与X11/XWayland，不锁定旧窗口。
- 取消、过期、被替代和关闭后停止未发送正文；必要的释放按键与恢复仍须完成。
- 已尝试投递的字符不得因换路、错误或确认不明而重放；不回退剪贴板或系统输入法。
- 映射只恢复自身拥有的改动，不覆盖第三方变化；源码通过不替代实际包验收。

## 按顺序实施

| 阶段 | 目的与验证重点 | 当前实现/合成证据 | 实际验收状态 |
| --- | --- | --- | --- |
| 1 安全X11/XWayland路由 | 对可识别的X11目标使用其路径；原生目标仍走原生路径；验证跨后端切窗、取消、任务隔离、映射独立恢复及不重放 | factory最小接线完成；188focused及完整1478测试通过；早期102项只属合成证据 | 阶段1源码有限验收通过；A显式Hybrid实际证据不替代最终包默认factory桌面验收，历史false保留 |
| 2 原生重复事务/最近映射复用 | 跨SSE片段复用输出scope与单项最近映射；保留所有权、deadline和键盘状态检查 | 实现/合成审核完成；子Agent224测试通过，主Agent独立1513全套通过 | 提交前源码有限实际验收通过：24单后端case+B受控交接4case；提交后完整检查以绑定本报告的clean-HEAD回执为准；非最终包factory验收，未打包/部署 |
| 3 逐阶段等待校准 | 分别研究映射、按下、释放等待，记录每个候选的准确性和成本 | 单变量及组合profile获审；修复后工具26纯测试、采用后六模块282项检查通过 | 56参数case及当前defaults真实factory四项实际通过；源码采用X3/N3；d49c64d完整1536/3通过；CLI R1失败保留，新a15实际包另见下行 |
| 新候选包 | 将最终获审源码打成独立版本；同一包与SHA分别在Ubuntu24.04/26.04实际验收 | a15 / 产品27aef8c / SHA b92ffd…a598 | [实际包报告](a15-dual-ubuntu-validation.md)：host20+guest9通过，主 Agent已审；稳定部署待执行 |
| 稳定入口更新 | 双系统包验收及主 Agent审核通过后，执行并核对实际版本与配置保留 | 尚未执行本轮提速版本部署 | 待验，不因源码或合成测试通过提前更新 |

每阶段先完成项目规范第25节要求的实际可行性检查，再交主 Agent审查验收。
明确记录未通过的候选，不用后续通过覆盖前次失败。若某项没有收益或不能安全实施，
记录实际原因，由主 Agent依据证据决定后续，不将设计意图写成完成结果。

## 证据表

| 项目 | 复现入口/来源 | 当前结果与限制 |
| --- | --- | --- |
| 已安装a14输入基线 | [原基线报告](input-speed-baseline-a14.md)及其两个结果SHA | 历史单insert输入后端测试，非本轮候选结果 |
| 阶段1早期合成检查 | 候选代码及102项纯测试 | 当时通过；不是GUI、实际切窗或速度验收 |
| 阶段1 factory/当前回归 | GNOME Wayland→Hybrid；188focused、1478全套 | 源码有限验收通过；真实A显式构造，不回填最终包默认factory GUI |
| 阶段1 phase0只读焦点分类 | `build/input-speed-router-preparation/result-r1.json` | 13稳定阶段0 mismatch；全程4错、passed=false；没有输入/映射修改，不能称阶段1完成 |
| 阶段1候选实际投递r1 | `candidate-native-result-r1.json`，冻结44源/19origins | 原生首行KeyboardError，press/release均0、passed=false；映射差异未解释；XWayland组未启动 |
| r1之后只读begin诊断A/B | `begin-diagnostic-{native,hybrid}-result-r1.json` | 两次begin/finish完成，禁key/set_map；不是打字或恢复验收，不解释r1失败 |
| 阶段1候选r2 | `candidate-{native,xwayland}-result-r2.json` | 原生3×100+cancel8通过；X第0行100exact、第1行DOM99后fail-stop；无整组提速结论 |
| 阶段1 R3 A稳态 | `candidate-a-{textarea,contenteditable}-result-r3.json` | 5次100exact及两次cancel8通过；只限稳态，mixed/默认工厂/新包待验 |
| 阶段1受控mixed r1 | `candidate-a-mixed-result-r1.json` | 前3项精确/恢复通过，第4项首次按下前被测试guard拒绝，整组false；受控边界不是连续post-map切窗证据 |
| 受控mixed R2第四场景 | `candidate-a-mixed-result-r2.json` | setup ValueError，0insert/guard/press/release/maps；formal baseline未建立，第四场景仍未验 |
| 受控mixed R4第四场景 | `candidate-a-mixed-result-r4.json` | X10→native4/cancel14两字段exact、恢复与终态通过；仅受控边界，默认工厂/连续竞态仍未验 |
| 阶段2实现/合成检查 | 输出scope/最近缓存与取消清理修复；224相关测试、1513完整测试 | 通过；纯调用数不作真实吞吐或缓存收益 |
| 阶段2实际源码对照 | `build/input-speed-stage2-preparation/stage2-matrix-summary-r1.json`及其24份raw指纹 | 24项通过，单后端scope/取消/empty与恢复；重复文本实际收益受70ms供给限制，不作intrinsic-cache速度或重复可靠性分布 |
| 阶段2 B受控mixed | 同目录 `stage2-mixed-summary-r1.json`及其4份raw指纹 | 双向normal23/取消14精确，epoch互斥/恢复/原owner终态通过；显式Hybrid、ACK/cap10暂停边界，非factory/无暂停post-map原子证明 |
| 阶段3校准 | `build/input-speed-stage3-preparation/stage3-measurement-summary-r1.json` | 56项通过；full100单insert，非70ms流式供给；该56项属源码参数证据，后续a15包验收另列 |
| 新包Ubuntu24.04 | a15同b92 SHA、真实KVM/GNOME46/Xorg，19origins/44产品源 | 9项通过；含独立修正验证器factory2；GNOME46原生仍未支持，失败历史见a15报告 |
| 新包Ubuntu26.04 | a15同b92 SHA、GNOME50.1/Wayland，19origins/44产品源 | 20项通过；native/XWayland、factory4/受控mixed4分别记录，主 Agent已审 |
| 稳定部署 | 待实际目标/SHA、备份、配置保留和正常启动观察 | 待验 |

## 阶段1 phase0：真实只读焦点分类

主 Agent已独立读取 `build/input-speed-router-preparation/result-r1.json`，SHA256：
`f66a8e8087afeee583856c65fb0762d5acc2cc88a3681c54586ae99c7c0efa3b`。
实际a14在本机GNOME Wayland只采样焦点，没有请求键盘输入或修改键盘映射；
7个自有Chrome的原owner均自然exit0，映射前后相同，cleanup_errors和fixture_errors为空。

13个稳定phase全部0 mismatch；但全程 `global_unique_focus_mismatch_count=4`，
`body_passed=false`、`passed=false`，必须保留机械验收未通过的结果。
四次均处于旧native DOM仍报focus=true、新XWayland DOM尚无首份snapshot的边界，
当时root active、raw focus和guard已接受新X owner；不是观测到新native已就绪后
仍接受旧X。各来源是异步采样，不能据DOM旧状态自行推断另一种错误方向或原子焦点。

20ms只是计划采样间隔，实际最大采样gap为538.992ms，另含DOM heartbeat/IPC延迟；
不声称20ms误差界限或分类原子保证。这份有限稳定分类证据支持继续候选私有试验，
该次只读观察不证明跨后端文字投递安全、当前光标无竞态或实际提速；当时阶段1未完成。
候选另已修正关闭清理，102项纯测试由主 Agent复跑通过；该合成结果不覆盖上述4错。

## 阶段1候选源码r1：原生首行失败

主 Agent已核验 `build/input-speed-router-preparation/candidate-native-result-r1.json`，
本报告另只读重算SHA256为：
`3294967147d710853b7c33914b072a9e9de74f2e959b165d26df99b30e312d61`。
运行来源是获审冻结44个候选源文件、19个实际origins，依赖受验a14包；不是新包结果。

原生第0行进入 `_insert_prefix` 后约3.009秒返回KeyboardError；旧工具仅保存异常
类型和通用 `candidate_benchmark_failed`，未保留该KeyboardError的具体code，故未知。
未记录begin ACK，仅有cancel/close ACK；未见X11前缀或开启的映射epoch。
独立counts为press0/release0/guard0，没有发出任何字符，不能计算正常输入吞吐。
不按约3秒的时长猜超时、连接或其他根因。row及总结果passed均false。

before map SHA为
`395d025fd51b8aeff2c67f887c99ddbca5054b97e77cb12151158f6e721bf9ed`，
after为 `6d79c7c44480a2cdd0ce78be1821452ae4b86568aad07600955d22749ae7f45b`，
`native_mapping_restored=false`；两者group0/depressed0/latched0/locked16。
映射差异尚未解释，不能写成恢复通过，也不能据差异证明发生自有映射写入。

原worker713236/start44494062与target自然exit0，原benchmark owner713210/
start44494002自然exit1；cleanup_errors和fixture_errors为空，不覆盖正文/映射失败。
本轮按fail-stop未启动XWayland cohort，原r1保留、未重跑，不记为阶段1或提速通过。
后续已完成下述只读诊断；原r1失败及映射差异仍保留，未因诊断成功而改写。

## r1后只读begin诊断A/B

两份actual raw由主 Agent全文验收，本报告只读独立重算SHA256：

| 诊断 | `build/input-speed-router-preparation/`下结果 | SHA256 | begin耗时 |
| --- | --- | --- | ---: |
| A纯native | `begin-diagnostic-native-result-r1.json` | `cb2dea3c9f221da5173efd98d9eacff225b8d41c468d7c0d3b0331f37fa6e816` | 8.368ms |
| B Hybrid加X连接 | `begin-diagnostic-hybrid-result-r1.json` | `15c68eabebb6e678bd1e8bae36628bb734f4303fa1d3752863fe39a6f1960f82` | 7.994ms |

两者生产begin/finish均收到ACK，key/set_map被禁止，未执行insert；worker、target和
原benchmark owner均自然exit0，cleanup_errors/fixture_errors为空。连接前、连接后、
清理后三份native metadata各自一致，映射SHA均为
`6b19630e18f35206efdf196a5a5a36c9768b1b838e7862ff157610b02216c192`，
group0/depressed0/latched0/locked16；caps mask为2，locked16不表示CapsLock启用。
B的X映射前后同为 `9b2a12a0a34bd01a9a57d336167472e418f0ef56cfb867e6cbbca6659748cfcf`，
`x11_selected=false`，符合此次原生字段。这只是无写入读取事务的一致性证据，
不是文字投递、映射修改后恢复或速度通过；两次结果不解释r1失败，也不支持归因X连接。

下一轮r2速度入口仅增强诊断：保存request错误code/phase，将输出恢复baseline移至
完整setup和字段ready之后，同时保留setup初始SHA。既定产品三项指纹不变；随后实际结果如下，不以工具诊断增强记为产品修复或性能收益。

## 候选源码r2：原生通过，XWayland读回失败

本报告只读两份actual raw并独立重算SHA256，主 Agent已核验全部行：

| `build/input-speed-router-preparation/`下结果 | SHA256 | 结果 |
| --- | --- | --- |
| `candidate-native-result-r2.json` | `d48f101eeeff948ca06e1da0633de8c3a3b21d73509d2d23d045b081a954fb08` | passed=true，3×100exact+cancel8 |
| `candidate-xwayland-result-r2.json` | `4ac169f85534af96fd2e435caa957d81776ffaa1efcadae8869bb44f401f5691` | passed=false，第1行readback失败后停止 |

原生组中位scope返回14215.126ms、吞吐7.034760码点/秒；每行仅native发送、按下/
释放平衡、guard0、映射与modifiers恢复，cancel8精确且0.5秒无尾部。它证明本次
原生组正确，不构成相较a14约7.037码点/秒的提速证据。

XWayland第0行100exact，scope返回6772.369ms、14.765882码点/秒，仅是单个通过行。
第1行有100次press/release、guard0、native0，前缀返回confirmed_count=100；但
最终DOM为99码点、exact=false、first_mismatch_index=0，在readback等待40秒后
ValueError。未保存正文，不能唯一断言“缺首字”或确定缺失位置/内容，更不推断根因。
本行没有完整exact时点，不能作为通过的速度行或据第0行宣称整体提速。

两组所有已启动target/worker原owner自然exit0，映射恢复为真、cleanup/fixture错误
为空；原benchmark owner717716/start44561476自然exit0，720786/start44566848
自然exit1。X第2行和cancel未启动，fail-stop；恢复通过不覆盖文字读回失败。
主 Agent已核验本轮fresh收尾 `candidate-post-preservation-r2.json`，SHA256
`f36708698cdfd46f3c3ca91c0cfca24ed84cff391679165ed96bee016697e4d0`：
三份用户配置和a14稳定包SHA保持本轮开始值，没有新云请求、录音或密钥访问。

下一最小候选拟仅把每次新X mapping loan的首次map等待设为100ms，其余20/20/20ms
及native等待不变；r3工具拟增加数字形式的单码点缺失位置候选、prefix/suffix诊断。
该准备之后实际执行的A稳态结果如下；未进行机制归因，匹配启动延迟控制B未执行，
当前也不因不作机制归因而安排该控制。仅该轮不足以称第一阶段整体通过。

## R3 A候选：两类字段限定稳态通过

受验是44源的候选A，source manifest SHA256为
`231a80d957f9666dc0631f55250af457ec18595e2cc21110c965502cbad0169d`，
`keyboard.py` SHA256为
`4281c1e1480e870cd3fd26858e1494d81f7d352fe356e5784c67e016c970ec58`。
每次新X mapping loan首次map等待100ms，其余20/20/20ms及原生等待不变。
这是新候选源码配a14依赖，不是已更新的a14或新AppImage。

主 Agent已全文验收，本报告只读重算两份raw SHA256：

| `build/input-speed-router-preparation/`下结果 | SHA256 | 正常/取消次数 | 中位首发 | 中位scope返回 | 中位吞吐 |
| --- | --- | --- | ---: | ---: | ---: |
| `candidate-a-textarea-result-r3.json` | `696a605f8ef8823baf3ce3554067d477656800ffa9571149ca7f82bda009d55c` | 3×100+cancel8 | 106.397ms | 6835.183ms | 14.630186码点/秒 |
| `candidate-a-contenteditable-result-r3.json` | `9fde86307346dfc157392c1778737896c0fa45579d3464cf70f1089e70e5529d` | 2×100+cancel8 | 103.307ms | 6852.683ms | 14.592882码点/秒 |

五个正常行均100exact、100对press/release、Xonly/native0/guard0，first callback各1；
双map/modifiers恢复、cleanup错误空。两次取消均精确8字符且无尾部；全部7个target、
7个worker及两个source cohort原父owner自然exit0。

这些结果只支持A在此次稳定自有字段的文字投递、取消和恢复。没有匹配的启动延迟B
控制，不作失效机制或首map等待的唯一因果归因；也不把有限重复当可靠性分布。
保留phase0四次边界错、r1未发送失败及r2的100发送/99读回反例，不改为通过。
受控mixed四场景及后续factory源码验收见下节；此次A并未运行默认factory路径，
也不将这次稳态吞吐宣传为已部署产品的新速度。

## A源码受控mixed r1：前三项通过，第四项测试guard拒绝

主 Agent全文核验，本报告只读重算
`build/input-speed-router-preparation/candidate-a-mixed-result-r1.json` SHA256为
`00621ff1d7210032fa6807cac35e6112bf573b94d3993e22c7024d54f2cc8c78`。
固定样本23个BMP码点，前缀10含中文、é、Ω与换行，新窗口后缀从Latin `k` 开始。

| 场景 | 实际读回/计数 | 结果 |
| --- | --- | --- |
| native10→X13正常 | 两字段分别10/13 exact，23对按键、guard0 | 通过 |
| X10→native13正常 | 两字段分别10/13 exact，23对按键、guard0 | 通过 |
| native10→X4，cancel14 | 两字段分别10/4 exact，14对按键、guard0、无尾部 | 通过 |
| X→native，cancel14 | 首次X按下前被测试owned_focus guard拒绝；X press0/release1/guard1、native0，单字段0字符 | 未到handoff，失败 |

前三项first callback各1、映射epoch互斥、双map/modifiers恢复，cleanup/fixture错误空。
第四项output_error=input_cancelled，随后readback ValueError；原工具没有保存具体
测试guard拒绝原因，故未知。它不是生产主动取消或真实漏字的证据，不能重新标记为
“环境无效”以删除失败；清理release1不表示成功发送过正文按下。整份passed=false。
7个自有Chrome、4个worker原owner均自然exit0，父owner自然exit1；已启动资源均清理。
只读收尾 `candidate-a-mixed-post-preservation-r1.json` SHA256为
`9d186a7cd80f09411c4ada195451584cb43845980be6587b9bad79e29f036733`，
三份用户配置、两个artifact及冻结源均未变；没有新云、录音、密钥或剪贴板/IME调用。

这些切换使用测试控制：native在第10字ACK边界暂停，X请求前缀人为cap10；暂停期间
建立新字段并等fields-ready后继续。不是在真实post-map/按下前竞态内无暂停切窗，
不证明原子分类、安全覆盖所有焦点时序或切换吞吐。三个成功场景不补齐第四场景。

下一r2只拟补测试guard同一次读取顺序的详细布尔值、age、PID/XID及精确取消阈值，
再单独验证尚未覆盖的第四场景；实际R2在setup停止，结果如下，不写为修复或阶段1完成。

## A源码受控mixed R2：第四场景setup停止

本报告只读原始结果与post并独立重算SHA256，主 Agent已验收：

| `build/input-speed-router-preparation/`下证据 | SHA256 |
| --- | --- |
| `candidate-a-mixed-result-r2.json` | `8f862e84537a516b7ff500d3845dba4e9dee655acacf7ff7493358cdade1fbe0` |
| `candidate-a-mixed-post-preservation-r2.json` | `f41e826545966a263c5b2645d044d7c5de05db139402b7e07c7884aec0ab00c5` |

这次仅选第四场景X→native/cancel14；failed_phase=setup、ValueError、具体error_code
为null，passed=false。insert前缀和映射epoch均为空，guard/press/release/map write/
restore call全部0，first callback0，没有发字或到达handoff，不能算取消14已验。

`formal_ready_baseline_established=false`。原始两个mapping_restored字段为false，
但正式ready恢复基线尚未建立，不能称恢复失败；post确认setup初始native metadata
与清理后相同。这也不是注入/改图后恢复通过的证据。

原target734597/start44663295及worker734593/start44663242均原owner自然exit0，
父owner734577/start44663183自然exit1；cleanup/fixture错误空、stderr0字节。
只读post确认fresh配置/artifact、A44源快照、工具、冻结220依赖和mixed r1 raw均不变；
setup失败后停止，没有重试、改变factory或控制用户应用。原false与完整回执保留。

R2结束时第四场景仍未覆盖，默认工厂等门禁当时未完成；后续R4与源码有限验收见
下节。不由资源清理推定其他门禁通过，阶段2/3、新包及稳定更新仍待。

## A源码受控mixed R4：第四场景有限通过

主 Agent已独立全文核验，本报告只读重算原result/post SHA256：

| `build/input-speed-router-preparation/`下证据 | SHA256 |
| --- | --- |
| `candidate-a-mixed-result-r4.json` | `8a1c7663053e17471a6fb558554188bd399ef09a4700308f76f10312afcd4678` |
| `candidate-a-mixed-post-preservation-r4.json` | `e41918765d316949c1bf32c525a2282fd3af1ebfe76786f08cd802ba25a744b8` |

这次仅验证第四场景：X10→native4，cancel14；两字段10/4 exact，14对press/release、
guard0、first callback1，双map/modifiers恢复，output epochs关闭，0.5秒无尾部。
两个原target、worker及父owner均自然exit0；父身份739914/start44711360，
cleanup/fixture错误为空。自然启动新字段，不使用CDP焦点激活；mixed R3激活准备
方案没有执行，不与此前稳态R3 A的已执行结果混淆。

这是同样受控ACK/请求cap10、暂停等字段ready的有限场景，不是无暂停post-map竞态、
原子分类或切换吞吐证明。R1前三项与此次第四项构成有限受控输出门证据，但不解释
R1具体guard拒绝或R2 setup失败，不覆写它们的false，也不宣称连续无损焦点切换已验。
post保留原失败raw、fresh配置/artifact、冻结源/依赖与工具；没有新云、录音或密钥访问。
该次实际A仍是显式构造Hybrid，不是factory自动GUI；后续源码factory/回归有限验收
如下。当时阶段2/3、新包及部署仍未完成，R4的有限scope不因此扩大。

## 阶段1默认接线与当前自动检查

当前 `keyboard_for_desktop()` 在GNOME Wayland通过局部import返回Hybrid；构造时
不查焦点、不connect。Xorg及其他原有分支保留旧类，不新增平台支持声明。Hybrid的
说明去掉“非默认”，没有把记录开始时捕获目标带回实现。

当前tree相对冻结A44除独立图标更换、factory接线、Hybrid说明及模拟driver契约同步
外，输入算法未变。此前实际A的44源/19origins仍绑定原冻结快照，不改写为当前tree
或新factory已经过实际GUI的证据；最终包factory还须同包两OS实际验证。

历史首次完整测试在受限沙箱发生socketpair.send EPERM并中断；随后获准环境的完整
重跑曾为8 failed、1467 passed、3 skipped，30.77秒，原失败记录保留。8项位于
performance_cloud_comparison的模拟normal/focus/cancel/expire及parent显示流程，
以及performance_live_comparison的offline normal/cancel/expire，观察到output0。
确认为模拟MemoryDriver未实现新增 `applied` 生命周期：AttributeError被Session失败
路径处理，导致无输出。最小修正为初始None、普通map赋值、restore清空；未放宽断言，
不解释为真实云端或桌面输入失败，也不据此改写此前候选raw。

子 Agent相关检查为**188 focused passed，18.42秒**，经主 Agent审查；主 Agent
独立完整复跑为**1478 passed、3 skipped，38.87秒**，Ruff check全部通过、format检查283文件通过。
这些是源码自动检查；最终提交后的clean-HEAD receipt仍另行记录，不提前宣称已提交。

可复现自动检查（本机socket/本地TLS测试须在允许相应操作的环境执行）：

```sh
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest -q
```

## 受控切换与取消复现步骤

1. 使用获审冻结A44及a14包依赖、私有配置与fresh自有Chrome字段，区分实际native与
   XWayland协议。禁止剪贴板/IME，不向用户窗口发送文字；原始完整argv及owner记录
   保留在上述raw相邻preview/终态文件中。
2. 复用23BMP样本，UTF-8 SHA256为
   `9460b4558b23250ad64bc86daeb2d2521395d3e05d583d65359b24123907feec`。
   显式Hybrid单任务开始输出，native第10字ACK边界暂停或X请求前缀cap10；自然启动
   第二个自有字段，等fields-ready再继续，不用CDP激活。这是测试控制，不改称无暂停
   post-map窗口切换，也不宣称焦点查询与事件发送具有原子性。
3. 正常两方向分别核对10/13 exact和23对按键；取消两方向均在总成功按下14时停下，
   核对10/4 exact、14对按键及0.5秒无尾部。每任务callback1，双map/modifiers恢复、
   映射epoch互斥，并读取原target/worker终态与post保留证据。
4. 稳态100BMP速度与正常/取消边界另作上述独立组，不把受控暂停用时算成生产吞吐；
   新factory的自动桌面路径待最终新包同SHA双OS验收，不能从显式构造测试中外推。

## 阶段2：实现与合成审核及24项实际源码证据

本节是阶段2新工作树；阶段1节的“当前tree/算法未变”仅指阶段1当时的检查点。
当前Hybrid/native输出scope可跨SSE片段复用；空scope保持懒惰，不查询焦点或begin。
事务使用固定、有限的绝对deadline，片段到达不会续期或在片段间过期后再加60秒。
owner发生异常后scope被poison，不能被catch后继续复用；外来任务busy，切换backend
先restore再交接。开始录音不捕获目标和当前光标语义不变。

Guardian增加单项“最近确认character/code”缓存，独立于 `last_confirmed` 与
`pending_map`：合成检查中AA及A/换行/A复用，ABA仍执行3次map；不宣称多字符
预映射或无界cache。每次source/group/modifiers/map检查与真实key release保留，
原生50/50ms和X11等待常量均不变。减少纯测试中的map调用数不是实际速度证据。

审查与新增失败测试复现后，修正了两项实现缺陷：

- cleanup ACK仍待确认时double cancel曾使旧owner过早释放，新任务可begin/key。
  现在清理task绑定进程且排他；旧任务不能修改新generation锁，重入取消不提前
  放行未清理的guardian。已有测试覆盖失败时序，不用忽略异常或放宽断言通过。
- 初版修正又会在cleanup_pending后永久阻止connect。现在只有旧guardian确认退出
  后才允许显式新generation connect；不自动重连、恢复正文或重放未确认输入。

新增检查包括片段间expiry不续期、double cancel、cleanup失败、旧/新进程互不干扰，
以及旧guardian自然终态后的显式恢复。相关子Agent执行**224 passed，6.03秒**；
主 Agent最终独立完整工作树复跑为**1513 passed、3 skipped，41.56秒**，
Ruff check全部通过、format检查283文件通过。此为最终锁修正后的结果，不把此前
锁修正前的中间检查当作最终验收；阶段1各次历史与false原样保留。

本节记录阶段2提交前实际验收，没有新包或稳定部署。下述24项实际源码对照已核实普通/
重复文本、单后端片段间取消及empty；另4项B受控交接已独立验收，合计28项提供
阶段2源码有限实际通过证据。保留旧A历史，不用A的mixed替代B的实际回执。

### 24项实际源码对照：native/XWayland与两类字段

主 Agent独立逐一读取24份raw的counts、请求、精确读回、恢复与原owner终态。
本报告另只读重算24份raw指纹并核对passed/exact均true；汇总及进度指纹如下，
完整逐例raw路径、哈希、时间和owner保留在汇总中，不在此展开24组日志。
证据均位于 `build/input-speed-stage2-preparation/`：

| 证据 | SHA256 |
| --- | --- |
| `stage2-matrix-summary-r1.json` | `a1bea53ee8f71c629129f146a04ec5db59301526b6a1286c83971df74926ed60` |
| `remaining-matrix-progress-r1.json` | `8576d135642c87ea8525e9db74478b58e92f01c60ad25a7b5621f1811bf7a113` |

对照A为冻结A44；候选B的 `source-b-r1/manifest.json` SHA256为
`db9c92962ad0ef12d19c8fe40b98269576858a9772d3d142cad04ad898e44cb1`。
B实际审计的四处源码指纹如下，不回填A的origins：

| `inkecho/platform/`下源码 | B SHA256 |
| --- | --- |
| `hybrid_keyboard.py` | `6b6b8ab3e23b2a2aeb0e71aca37743526825c06cb2d93d14d35bbe7b1b6172f7` |
| `wayland_keyboard.py` | `e8301f4c002a460f186d48db275314553394995e5021e34c1ac7ae62f68edf20` |
| `wayland_worker.py` | `c7bf083c2841163f2c16fad0440f1c35e2a9f9fbcb382ad1e6ab9c4338ccff9d` |
| `keyboard.py` | `4281c1e1480e870cd3fd26858e1494d81f7d352fe356e5784c67e016c970ec58` |

实际GNOME Wayland自有Chrome分别使用native/XWayland、textarea/contenteditable，
显式构造Hybrid，使用候选源码与a14依赖；不是新包，也不是factory自动GUI验收。
普通100BMP样本SHA为
`92a3e661ef711faaf474ced4b3c6418aa06d3242333a976a87ed1328d1f9387d`。
重复100BMP样本SHA为
`c995e6dc89306882cbd51772f896d366bad9bcc9a88f925d5e4c319c392613bf`。
生成片段计划间隔70ms，实际通过生产StreamingOutput排队与合并，未等待未来片段
制造批次；没有云、录音、密钥、剪贴板或IME操作。

| 后端/字段/100字模式 | A scope毫秒 | B scope毫秒 | A→B映射写入计数 |
| --- | ---: | ---: | --- |
| native textarea ordinary | 14467.017 | 14173.502 | SetMap ACK 107→101 |
| native contenteditable ordinary | 14662.620 | 14284.808 | SetMap ACK 107→101 |
| native textarea repeat | 14499.446 | 6990.237 | SetMap ACK 107→6 |
| native contenteditable repeat | 14427.092 | 6994.535 | SetMap ACK 107→6 |
| XWayland textarea ordinary | 7875.188 | 6974.227 | write 114→101 |
| XWayland contenteditable ordinary | 7990.061 | 6955.469 | write 115→101 |
| XWayland textarea repeat | 7899.159 | 6953.591 | write 114→101 |
| XWayland contenteditable repeat | 7992.097 | 6991.033 | write 115→101 |

上表16个case均100exact、100对press/release、guard0，非选中后端没有按键。
native正常任务A均7begin/7finish，B均1begin/1finish；X11 write包含最后恢复，
不是全都叫“字符map”：A各14或15次restore，B均1次。实际批次随排队变化，
callback严格每insert一次；例如首对普通textarea A7批、B8批，并非每scope仅一次。

另8项是textarea的单后端取消/empty（A/B×native/XWayland）：取消均8字exact、
8对按键且无尾部；native B为1begin/1cancel、9SetMap ACK，XWayland B为9write/
1restore。empty均0字符、0按键/映射/首字callback，也无begin，不把0字算正常吞吐。
4项empty不创建Chrome；20个Chrome、24个worker及24个probe原owner均自然wait0，
48份stdout/stderr日志为空，cleanup_errors和fixture_errors均空。

24项均在scope结束、inputs仍open时核对native map/modifiers与baseline一致；
close之后原native metadata仍相同，X11 before/after映射也相同。相邻preservation
核对用户配置、旧artifact、A/B源码与工具before/after一致。

普通native两字段只见单对约0.29/0.38秒差异，不作普遍显著提速结论；实际事务7→1
是明确证据。重复native两字段约14.5秒→7秒且ACK107→6，是本次固定样本与供给的
有限实际收益。70ms供给约14.3码点/秒，实际排队间隔另有记录；scope含供给等待与
监督开销，不能据约7秒测出缓存自身的intrinsic吞吐上限。XWayland约8秒→7秒同样
受该供给口径约束。24项是不同条件各单例，不是重复可靠性分布；B的新scope跨后端
受控交接见下节，阶段3/新包/部署仍待。

最早operator在写保留证据时因 `Path.open(opener=...)` 返回TypeError，发生在Popen
之前：probe、Chrome、worker均未启动、0GUI/0输入。原
`control-native-textarea-ordinary-operator-failure-r1.json`保留；改用builtins.open后
才开始上述首次真实case，不称为产品失败或产品重试。

### B的4项受控跨后端交接

主 Agent独立逐一验收4份raw；汇总
`build/input-speed-stage2-preparation/stage2-mixed-summary-r1.json` SHA256为
`81b5cf00005df59cc76bf47f100bf81ba5c40b748639770ad47acb7d86993baf`。
本报告另只读重算汇总与4份raw指纹，均匹配：

| case（`candidate-mixed-…-result-r1.json`） | 两字段精确字数 / press与release各自合计 | raw SHA256 |
| --- | --- | --- |
| native-to-x-normal | 10 / 13，23对 | `daca1a7774f9a71d3ab89f62c7446795c2a1e795b394b08df7746d0797e48311` |
| x-to-native-normal | 10 / 13，23对 | `896020b1e21d03beb2a21827287015552c51eecdddbe43e03df8ef84d6f8fada` |
| native-to-x-cancel14 | 10 / 4，14对 | `0edc38529e59abfa9dfbad7a6729287964fcaac242d57dc3d0071b6bc15498cc` |
| x-to-native-cancel14 | 10 / 4，14对 | `a7b6608273edb40c6cd8c53524f3c36b4368f984f86ca542e48e0e53f62d3ac4` |

各任务guard0、callback1，取消后0.5秒无尾部；native/X11映射epoch无重叠。
每项 `ready_native == scope_after_native == after_native`（包含map与modifiers），
X11 before/after一致，scope后仍open与close后恢复均通过。原4probe、4worker与
8Chrome均自然exit0；cleanup/fixture为空，preservation和19origins核验通过。

native→X取消项的restore计数2仅为wrapper成功返回次数，含幂等noop，不是两次
真实映射rewrite；该项5次map write是4次字符map加1次实际restore。

这些是B冻结四pins、source+a14依赖、显式Hybrid的独立证据：沿真实native ACK或
X前缀cap10暂停，自然启动新字段并等待fields-ready后继续；不含CDP激活，不作
无暂停post-map竞态、切窗原子性或切换吞吐证明，也不改写旧A的失败与origins。

提交前当前tree另为两个公开 `output_session` 补齐 `AsyncIterator[None]` 标注及导入。
主 Agent逐AST移除仅该导入与返回标注后，Hybrid/native parent与实测B的AST完全
相同，keyboard/worker仍byte-identical；类型补齐后子Agent224 focused通过，5.99秒。
当前Hybrid SHA为 `4005f609b46a3e4bafef5cddf27e0672830f1d07b5611a0b29bcbd1c97b4c987`，
native parent SHA为 `908d5c61d0dec8066385554db7652d06e83a42dd5e736f3d96f7aa54c00cbf69`。
B快照保持原四pins/44源/19origins不变，不重标为当前tree。此后提交
`1cffa59cbf80eb56e0c2bd93f5adbf2fb29fb390`的完整clean-HEAD工作流已通过：
**1513 passed、3 skipped，41.50秒**。实际receipt为
`.git/validation/1cffa59cbf80eb56e0c2bd93f5adbf2fb29fb390.json`，绑定当时本报告SHA
`8f604a376d04fd962ca41d55d393577044b9672d64b9db280e6aa7759b0da219`；
该历史回执不绑定本次新增阶段3文字或替代后续最终提交检查。

## 阶段3：56项实际参数实验与当前采用设置

本轮实际来源为 `build/input-speed-stage3-preparation/stage3_probe.py` 与独立物理
源码快照，使用a14包依赖。baseline精确来自类型标注前的旧B四pins，不是当前tree
回填、不是新AppImage或默认factory自动GUI验收。单次公开insert直接接收完整
100BMP样本，无SSE或70ms供给等待，不与阶段2流式scope混为同口径。

初始四个单变量profile/registry获审、10项纯测试通过；初始registry SHA为
`b74eac095d60a1766a284c0706f23c2ae6cf4b51956983506aef73206154d6e9`。
组合候选另经r2/r3审查，最终 `candidate-registry-r3.json` SHA为
`03abfab9cbac5003f8d1b539c6659131494842b312e4fea4ad6ce93739be571b`。
下表单位毫秒，未列等待保持baseline：

| profile | 等待设置 | 实际状态 |
| --- | --- | --- |
| baseline | X首次map100、后续map/press/release各20；native首次/后续map及release各50 | 14项通过 |
| x1 | 仅X press 20→10 | 7项通过 |
| x2 | 仅X release 20→10 | 7项通过 |
| n1 | 仅native release 50→30，首次map50不变 | 7项通过 |
| n2 | 仅native后续map 50→30，首次map50不变 | 7项通过 |
| x3 | X press/release各10，首次map100/后续map20不变 | 7项通过；当前源码采用 |
| n3 | native后续map/release各30，首次map50不变 | 7项通过；当前源码采用 |

主 Agent逐raw独立验收全部56项，本报告另只读重算聚合列出的56份raw指纹均匹配。
完整逐例路径、SHA和owner保留在同目录聚合，不逐项重复展开：

| 汇总 | SHA256 |
| --- | --- |
| `stage3-measurement-summary-r1.json`（56项） | `0441646c0d21777c1ae4f5930189985810d68c0d39900aeb2fcc705a0e787f43` |
| `stage3-x3-summary-r1.json` | `da4f771b4dded12a97a4aaa787aaf5319bc2fd65574f0ce6f0a1800da2271401` |
| `stage3-n3-summary-r1.json` | `59ad57ecddf72c95550f358384511449f2e1b39980324cb2302934a4473a24b8` |

每个后端/profile执行fresh textarea正常3次、contenteditable正常2次，分别cancel8
一次。正常项100exact、100对按键、callback1；取消项8exact、8对按键、callback1。
正确路由/guard0、preclose与final native map/modifiers及X映射恢复、原probe/
worker/Chrome自然exit0、preservation均通过。取消不计入下表正常scope中位数：

| XWayland字段 | baseline毫秒 | x1毫秒 | x2毫秒 | x3毫秒 |
| --- | ---: | ---: | ---: | ---: |
| textarea | 6914.326 | 5803.176 | 5804.492 | 4779.377 |
| contenteditable | 6906.167 | 5801.487 | 5833.986 | 4795.190 |

| native字段 | baseline毫秒 | n1毫秒 | n2毫秒 | n3毫秒 |
| --- | ---: | ---: | ---: | ---: |
| textarea | 14182.158 | 12120.486 | 12246.988 | 10035.368 |
| contenteditable | 14213.435 | 12178.658 | 12260.369 | 10082.764 |

本次X3约4.779/4.795秒，相对匹配baseline约减少31%；N3约10.035/10.083秒，
约减少29%。只代表本次样本/字段/有限次数，不外推所有应用、任意切窗或可靠性
分布，不覆盖历史10ms/30ms负例。当前源码采用X3/N3，类型标注保留；X11与实测
X3仅注释不同，worker与实测N3仍byte-identical，SHA为
`9ecacec1dc36c34c52bbbec66cdf088712e5f0488c2d0dd02781557dfa6edd43`。
最终源码完整clean-HEAD回执、同SHA双OS新包与部署仍待，不提前宣称新HEAD通过。

### 长期CLI与独立烟测边界

tracked `scripts/validation/input_speed_probe.py`最初有主 Agent23项纯测试通过，它
不是上述56项来源。独立证据 `build/tool-smoke-preparation/` 前2项native normal100/
cancel8通过，使用旧baseline B真实factory，不是当前新defaults或新包。第3项
XWayland normal raw为false：protocol confirmed=false，X PID/class尚未出现，
native baseline未建立，无正文投递证据；setup记录ValueError、target cleanup记录
FileNotFoundError；原raw SHA为
`391bf7a6dbefaeb16f7b29f96ace456c2c2f802c439b51f1935ec53dedced0ce`。
原worker自然0；原Chrome经一次正常Browser.close回收exit0，证据
`xwayland-r1-normal-close-recovery.json` SHA为
`44fd77570a5346ad002e13edaa41246650b6a38eeed463fc2b155ae236f96c92`。
原probe809730/start45024477残留non-daemon HTTP线程，按主 Agent批准的精确
清理例外发送SIGINT；原handle16166最终exit1，第四项未启动。例外记录
`xwayland-r1-probe-cleanup-exception.json` SHA为
`b785c2000df9d410ab8ef7824706325fc0868a6bba96ee9cb7075d00e8b49469`。
旧terminal中的natural字段只表示原owner的wait观测，必须合读SIGINT例外，不能
把该项写为自然退出通过；无baseline的false也不证明映射恢复失败。

tracked工具随后补X protocol初始化until、端点等待及finally HTTP清理；冻结SHA
`8e8d3333f00bb47a26d4ba04bea3f916ae8648c0c1d6f5a2dfeca4ea510b640a`，
主 Agent26项纯测试通过，0.16秒；采用设置后的六模块282项相关检查独立通过，
4.95秒，均不替代实际工具烟测。R2使用当前新defaults的44源快照，manifest SHA为
`5c9b251b4dc2223bead87ca8bd0f4bb1b601d65460853a1e70c2db80f8cdf9da`，
完整四pins与审定命令在 `tool-smoke-preview-r2.json`，SHA为
`c36ae22b4616e09806cbd619853561259ccad481dfcc7d845675d7bd2ce44899`。
R2四项由主 Agent逐raw独立验收通过，原handle48081经原owner确认自然exit0。
当前44源manifest/19实际origins、正确路由、按键平衡、guard0、scope仍open与final
双后端映射恢复、cleanup空、原Chrome/worker/probe终态0及preservation均通过。
汇总 `tool-smoke-progress-r2.json` SHA为
`0fb971a32be104a344edd0a652310e69b8ad0f6fc32fb7130269ce5528ac0d24`，
本报告另重算四份raw SHA与progress逐项匹配。仅是当前源码factory与旧a14依赖：

| R2 textarea case | 精确字数 / press与release各自计数 | output scope |
| --- | --- | ---: |
| native normal | 100 / 100 / 100 | 9974.449ms |
| native cancel8 | 8 / 8 / 8 | 821.259ms |
| XWayland normal | 100 / 100 / 100 | 4790.427ms |
| XWayland cancel8 | 8 / 8 / 8 | 462.138ms |

取消为完整100字请求在第8次成功按下停止，不能将短前缀吞吐作为正常100字性能。
R1失败与SIGINT例外保持，不因R2通过重标自然成功；a15尚未构建，本节非新包验收。
R2实际结束后，artifact_scope才补动态Hybrid第19来源审计，旧MODULES18及无Hybrid的旧a14仍保持18；新增来源/tamper拒绝两项纯测试和相关45项纯测试通过，不改旧实际工具SHA，也不代表新包实际验收。

以下为长期CLI source-mode参数模板，默认仅audit/preview；非56项历史argv。
只有另行审核后才加 `--run-reviewed`，实际运行须真实桌面和fresh自有目标。
此处指定获审并实际烟测的R2当前defaults manifest与a14依赖，不替代最终包验收：

```sh
task_appdir=/home/lth/github/InkEcho/build/performance-a14-extracted-j1fjrht6/squashfs-root
task_source=/home/lth/github/InkEcho/build/tool-smoke-preparation/source-current-r2
env -u APPIMAGE -u APPDIR -u QT_PLUGIN_PATH \
  APPDIR="$task_appdir" PYTHONHOME="$task_appdir/usr" \
  PYTHONPATH="$task_appdir/packages" \
  LD_LIBRARY_PATH="$task_appdir/usr/lib/inkecho" \
  QT_PLUGIN_PATH="$task_appdir/packages/PySide6/Qt/plugins" \
  PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=wayland \
  "$task_appdir/usr/bin/python3" -B scripts/validation/input_speed_probe.py \
  --runtime source \
  --artifact /home/lth/github/InkEcho/dist/InkEcho-0.1.0a14-x86_64.AppImage \
  --artifact-sha bce09c895d51c01c11c73b67aef709632a7514545f0a7fdb6114748c70c8cc96 \
  --package-root "$task_appdir/packages" --source-root "$task_source/src" \
  --manifest "$task_source/manifest.json" \
  --manifest-sha 5c9b251b4dc2223bead87ca8bd0f4bb1b601d65460853a1e70c2db80f8cdf9da \
  --backend native --field textarea \
  --output /home/lth/github/InkEcho/build/input-speed-reviewed-fresh-result.json \
  --work-root /home/lth/github/InkEcho/build/input-speed-reviewed-fresh-work
```

每例须新的exclusive output/work；`--backend xwayland`选择X目标协议，
`--field contenteditable`选择另一字段，`--cancel`在完整100字请求的第8次成功
按下后取消。package模式另选获审包，改 `--runtime package`并删除source-root/
manifest/manifest-sha，不用source结果替代实际包验收。以上无云/录音/密钥/剪贴板/IME。

## 实测口径

复用基线的固定公开100码点BMP混合文本、fresh自有字段和明确后端/路由状态；
正常样本和cancel8分别记录。比较时保持目标、文本和测量方法一致；变化另行注明。
分别记录start→首次成功按下、首末按下跨度、insert/输出scope返回、DOM exact观测，
全程吞吐N/total与稳态(N−1)/span不混用；三次样本中位数只代表该次有限测量。
DOM轮询、fixture状态更新、IPC与guard开销不当成字形渲染时间或无误差确认。

正常输出须有精确读回、按下/释放平衡与映射恢复；取消须停止剩余字符、无延迟尾部。
跨路切窗需要分别核对各窗口实际接收前缀/后缀，不以发送成功代替接收正确。
源运行的解释器/依赖与候选源来源须明示，不能称为已验证的新AppImage。
完整命令、冻结源码/工具指纹及原owner终态随主 Agent验收的实际回执补入本报告。

## 已知负例与提速解释

X11历史10ms候选第二轮新Chrome textarea仅139/140，未保存丢字位置，不能描述成
“首中文”或猜其根因。原生30+30ms的混合contenteditable另有Latin首k丢失记录，
详见[具体诊断](native-wayland-mixed-private-diagnosis.md)；50+50ms后才通过。
不能仅因XSync、按键事件平衡或一次私有环境成功，就称更短等待已可靠。

任务级事务复用主要针对多个流式片段；单insert基线不能单独量化其收益。
减少映射编译/上传/刷新也不自动消除主动等待；每项收益须来自实际匹配测量。
本轮不承诺提速比例、不复制AGPL项目实现，也不将未测平台或应用写成已支持。

## 最终包与提交记录

按[项目规范](PROJECT_SPEC.md)第18、24节及[开发规范](DEVELOPMENT.md)执行：
最终同一版本、同一SHA的新AppImage必须在两系统分别实际验收启动/UI、声明协议的
配置与本地WSS、混合文字当前光标输入、部分取消和清理。容器、源码或单系统结果
均不能替代这一门禁；不因该门禁自动访问密钥或发云请求。

最终包a15已构建，产品来源27aef8c，SHA256
`b92ffd979f2faa979a22e9fd9a0be8cd187607009bd42313ef34fd91e660a598`。
[同包双Ubuntu实际报告](a15-dual-ubuntu-validation.md)记录host20+guest9门通过、
19origins/44产品源、两次验证器前置失败与明确新实验、有限速度及未验范围；主 Agent
已核原始结果和截图。最终新HEAD完整检查仍以其receipt及绑定evidence为准。
阶段3d49c64d的1536 passed/3 skipped为已完成历史；稳定入口仍a14，部署尚未执行，
未推送或发布。本段不回写旧实验或借其替代新包验收。
