# InkEcho 0.10.0：同一候选包实际验收记录

日期：2026-10-24。**24.04 Xorg 的本轮受控门已完成；26.04 非输入与真实 FUSE 门已完成；26.04 原生 INPUT normal/cancel 和 Hybrid 正常切换也已由 root 限域验收；额外 Hybrid cancel14 失败必须保留。两专用VM均已正常清理关闭，源合入main/tag/上传/正式发布操作仍未执行。** 本记录准备为0.10.1报告后继提交；其元数据不改变已验0.10.0包或构建源。

## 精确来源与唯一候选

| 对象 | 固定身份 |
| --- | --- |
| 0.10.0 构建源码提交 | `2934280f809b025eb5d77fb8b4218747480b8f81` |
| 该提交完整源码工作流 | 2047 passed、2 skipped、58.66s；正常工作流，源码通过不替代桌面门 |
| AppImage | `InkEcho-0.10.0-x86_64.AppImage`，104303096 字节 |
| AppImage SHA-256 | `ca322f19c6306546698621f4d2301a6a6b03eeb06c6c6be6e9f3d1506f6a5234` |
| `.sha256` 侧车自身 SHA-256 | `00bdbb6744df834514bf416ac69fa04e505a731c20ab3a3ed1d859c9c4aba5ff` |
| 包内 inventory SHA-256 | `b3df9072ff1f0bcd5d02a85460b8b7a2b242e9de464745b7f7c365101004b5f1` |
| 新基线 helper manifest SHA-256 | `1aaf3faada58d78841fd993b7eeb72a1e781bc3607b41f2861ccb1f175ef5f93`，239 文件 |

构建前 clean HEAD，按 `env -u SOURCE_DATE_EPOCH uv run python scripts/packaging/build_appimage.py` 只构建一次；原 PID47915/start844598 自然 wait0，无信号。构建 log SHA-256 `c423263225138473abf1b01d4e38b02b3cd23e412f0ca33ab760e39492dfe4bf`。包中3675文件、1048链接逐项审计；66个应用文件与冻结源逐字节一致。包解释器、keyboard、output_pacing、x11_feedback 及原生 worker 的实际 origins 绑定选中包，没有 source overlay；没有用0.9.x解释器或旧包冒充本轮实际包。

新 output_pacing SHA `782380de847786d297546a6e52c803e716048fadc4458879263b9280deb015f0`，x11_feedback SHA `cb4e58f12b9409a72f0b7ec9a0c39aeb6b49f53e5915f4e30e3e8d830df471ac`，keyboard SHA `0591a43fb66bbbe05060bd7064d9c7aac69bd3bb678455e8a398b66a333a1362`。X11系统库没有伪称随包捆绑；包内 libei1.5.0 与系统 X11/SYNC/DAMAGE 分别记录。

构建源和未来报告后继提交分开：最终报告提交按规范为0.10.1，release tag 应指向已验0.10.0构建提交，不重建报告提交替换本包。

## 环境与非输入门

| 项目 | Ubuntu 24.04 | Ubuntu 26.04 |
| --- | --- | --- |
| 实际桌面 | 专用完整 Ubuntu24.04.5 VM，GNOME46.0，Mutter46.2 `.18`，Linux6.8.0-142，活动/解锁 Xorg | 独立完整 Ubuntu26.04.1 VM，GNOME/Mutter50.1，Linux7.0.0-38，virtio_gpu DRM/KMS虚拟seat0，GDM原生Wayland |
| 桌面归属 | 自有测试guest，不操作宿主用户seat | 自有测试guest，不是嵌套/headless compositor 或宿主seat |
| 同一 artifact / source 审计 | 通过，66应用文件与新两模块origins | 通过，同一ca322…产物及选包解释器 |
| 入口五页/单实例/IPC/cold控制/损坏配置保留 | 通过，root逐页看自有PNG | entry-r2通过，root逐页看原生Qt Wayland自有PNG；entry-r1 PNG写入race失败保留 |
| quiet / 本地WSS+SSE / VAD | 通过 | 通过 |
| 合成Recorder与动画 | 首帧13.128/13.973/4.011ms；全部首样本先于动画 | 首帧8.778/16.995/15.967ms；全部首样本先于动画 |
| 音频平台边界 | Xorg上的私有测试浮层/虚拟音频 | 音频验收Qt=xcb，为真实Wayland会话里的XWayland浮层，不等于原生Wayland浮层通过 |
| 实际FUSE | 本轮未单独声称24.04 FUSE门 | 新guest真实FUSE通过，五页/cold toggle-cancel-quit=0、私有配置不变、原wait0/无信号；root看图和挂载原证据 |

所有云端协议均为本地服务/虚假认证，所有音频均为自有合成/虚拟输入，默认设备不变、模块清理通过；不等于真实麦克风或真实供应商账号的语音准确率。26.04 FUSE初次launcher误把SSH会话当桌面而在创建应用前失败，纠正仅环境发现并保留原exit1；第二次真实运行通过。

## Ubuntu 24.04 Xorg 的实际新路径

真实系统库：libX11 `2:1.8.7-1ubuntu0.1`、libXext `2:1.3.4-1build2`、libXdamage `1:1.1.6-1build1`、libXtst `2:1.2.3-1.1build1`、GTK3 `3.24.41-4ubuntu1.3`。SYNC3.1 / DAMAGE1.1 可用，生产反馈确为第二counter+自有Damage的DRAW提示，不以内置after-paint回调驱动生产调度。独立observer只读目标属性，创建/销毁自己的Alarm/Damage；所有成功门清理错误0。

固定公开混合Unicode受控GTK样本，无时序参数覆盖。首字分别记录 insert `begin` 与 `prepared` 两个起点，包含实际bind开销；发送跨度是首末press，不用scope关闭代替绘制完成。

| 单例 | begin→首press | prepared→首press | 首末press跨度 | 最大相邻after-paint间隔（含首次完整正文） | 准确性/平衡 |
| --- | ---: | ---: | ---: | ---: | --- |
| 混合38 | 121.676ms | 122.710ms | 2061.937ms | 149.533ms | exact38、38press/38release |
| 混合114 | 102.766ms | 103.762ms | 6605.731ms | 143.349ms | exact114、114press/114release |

38例首press至完整绘制2063.027ms；两例完整绘制均先于最后release约10ms，不把这个负差称为负处理时间或物理呈现。38例21mapwrite/20MappingNotify，114例58/57，恢复逐项读回一致；DRAW bind分别0.431/0.348ms。root实际查看中间长度12/25/38、38/76/114与最终自有PNG，证明这些受控例有中间可见推进。GTK Unicode控件回调press数并非底层事件全量；按键平衡依据sender原XTest调用计数。

取消门通过 can_continue 在首字回调中失效：仅1press/1release，失效后接收端持续1.613s最多1字且前缀正确，映射与资源清理通过；这是主动失效，不是物理ESC实测。

真实受控A→B→A门在同一output_session中按4A/4B/30A完成：A34/B4最终准确、全部changed前缀正确，38次press/release平衡，实际pacer代际1/3/4且三次真实DRAW，映射两次完整readback均一致；最后insert完成后两个接收器持续约1.467s，无额外字符。root审两个fresh ready的PID/start/XID/expiry，后审最终自有图。只在预定两次转换中对本身窗口各发一次EWMH激活，不修复意外失焦、不重放未确认正文。

该focus门的两个工具失败均保留：r1返回A的Gtk.present激活被桌面策略拒绝，A4/B4后安全停止（sender1，receiver自然0）；r2真实route/代际正确但GTK选中旧A4，后A30替换选区导致A30而非34，exact门失败。r3仅关闭fixture当前进程select-on-focus并删重复grab_focus，新的窗口/闭包重验通过，未修改产品焦点或输入语义。另有三个前置工具调用/路径错误均在创建相应目标或输入前拒绝，原失败与部分tar退出2保留。

所有成功sender/observer/receiver均原进程自然wait0，无强制信号。24.04完成后只读检查owned候选脚本进程为空，经guest systemctl poweroff及原docker wait0恢复初始停止态，不留后台快捷键或自有测试进程。

## Ubuntu 26.04 原生与 Hybrid 实际输入

原生 normal 门已完成并由 root 审查：同一候选包在隔离26.04完整原生Wayland桌面的自有Chrome目标中，经虚拟音频、本地ASR/SSE和真实生产Hybrid/原生输入路径，最终固定9字exact；可信DOM前缀1至9全部出现，root实际查看最终9字图。9次成功ACK、9次press/9次release、guard rejection0；keymap散列、group、depressed/latched/locked前后相同。sender10644、worker10672、browser4849、controller4836均原进程自然wait0，无强制信号。

采集到9个合法数值INPUT样本，其中3次实际映射、6次缓存；请求RTT12.059–79.685ms，映射设置10.648–24.398ms、映射确认1.501–2.479ms。实际pacer origin仍是包中782380…015f0，不用测试controller伪造反馈。INPUT ACK仅为输入链路进展，不等于目标绘制/呈现。DOM第二至第三字约398.7ms间隔包含本地SSE故意0.35s调度，不能当作纯键盘延迟或与24.04固定整串span比较；delivery保留本地服务ConnectionClosedError记录，terminal按实际完整结果accepted=true。

原始路径 `build/release-0.10.0/guest26-native-normal-r1-raw/guest-native-normal-r1/`，独立child manifest `cc241fefc81caba672550b9fdd2d804e18424cb483f8063141786484126af31f`；terminal/delivery/native-counts/native-cleanup/receiver-final及原controller owner散列见consolidated JSON。此前pre-send wrapper的int/string检查错误在RemoteDesktopSession建立前安全拒绝，原失败由root保留，无正文或重放。

原生取消门也已由 root 查看最终图和raw验收：production first_sent回调取消，epoch1→3且任务inactive，最终只有首字“本”、trusted前缀长度1；1ACK、1press/1release、guard rejection0。接收器取消后持续1.209801s、sender1.260168s均无尾部正文。单个合法INPUT样本RTT87.991ms、映射设置16.969ms、确认1.858ms；keymap/group/modifiers恢复，默认音频不变，cleanup空，sender12315/worker12343/browser11067/controller11054原自然wait0。该case是真实生产首字回调取消，不是实际ESC按键验收。初次cancel-r1的错误case参数被argparse在创建窗口/会话/输入前拒绝（原wait2），新r2使用实际cancel-after-first协议；失败保留，无重放。

取消原证据 `build/release-0.10.0/guest26-native-cancel-r2-raw/guest-native-cancel-r2/`、`guest26-native-cancel-summary-r2.json`。原生normal/cancel与FUSE的59份记录/截图入口 `guest26-native-fuse-evidence-pins-r1.json` SHA `665127b3139a993fbe5c881b60c8a15b7d6f3155e4cfda1abea8789e825e08c7`。

Hybrid normal-r2 已由root独立读取原始结果并限域验收：同一生产factory/output_session实际从原生10字切至XWayland13字，合计23字exact、23press/23release、guard rejection0；1.25s尾观测后两框仍exact；native和X11映射恢复、映射epochs无重叠，cleanup空。worker16269、Chrome16271/17554和owner16239原wait0。raw：`build/ubuntu26-release-vm/hybrid-normal-r2-raw/`，具体result/side-closure/原terminal散列已追加consolidated JSON。该helper未捕获输出后的final图，不虚构图审；验收依据自有页面DOM readback及原始事件/恢复记录，ready图已实际审查。

其首次r1原始失败保留：root审查耗时超过原25s fixture gate，原生10字后安全停止，XWayland0字、无重放且状态恢复。r2仅把受审工具gate改为60s，并使用一个包含root审查的绝对90s deadline；没有改产品或按键/映射底线。不能把审图间隔视为连续发送性能。

额外计划的 Hybrid cancel14 **FAILED，未验收为通过**：`build/ubuntu26-release-vm/hybrid-cancel-r1-raw/hybrid-cancel-r1/work/2/result.json` 明确passed=false/target1_ready ValueError。第二次人工审查超过60s fixture gate，原生只发10字（10press/10release），XWayland0次press/release；原生readback10 exact，X框0而计划4，故extra case未完成。两端映射仍恢复，cleanup/guard/fixture errors为空，两个Chrome和worker20212原进程自然0，无重放。不能称XWayland部分输出取消已通过，也不重跑旧窗口来掩盖失败。

root对本轮必需类别的接受是明确限域的：真实生产Hybrid factory的原生完整9字与首字取消1字（双端>=1.2s无尾），以及同一output_session原生10→XWayland13的当前光标切换，配合24.04 Xorg受控输出/取消/A→B→A、同SHA包与非输入门。该类别判断不把额外cancel14的FAILED改为PASSED；XWayland部分输出取消、所有历史变体仍未由本轮桌面实测覆盖。XWayland DRAW仍禁用，源码取消回归通过也不代替这项桌面case。

26.04收尾已由root独立读取原记录接受：owned candidate/browser/worker进程为空，临时idle-delay恢复uint32 300、lock-enabled恢复true；正常ACPI关机、原docker wait输出0，容器exited/Running=false/ExitCode0/OOMKilled=false。未操作宿主用户桌面。原件见 `build/ubuntu26-release-vm/final-owned-process-check.json`、`idle-profile-restored.json`、`final-normal-powerdown.log`、`final-container-state.json`。

## 保留的源码探索失败与外推限制

此前源码受控实验中，38字自适应跨度2271.080ms，相比同环境20ms固定基线1759.641ms反而增加约29.1%；最大末尾绘制间隔204.351417ms，超过事先200ms目标。相对60ms保守基线缩短34.29%不能抹去该失败。114字相对同长度60ms基线缩短38.27%仅各一例，缺同长度20ms对照。更新Mutter `.18` 的当前VM没有复现历史 `.15` 的整句卡顿，不宣称旧故障在所有环境消失。probe-only250ms尾hold实验中正文在hold前已绘制，不支持给产品加入固定等待。

本次包38/114各一例达到受控200ms目标，不抹去此前204.35ms失败，也不证明任意负载、第三方终端/浏览器或桌面版本平滑。光标闪烁、动画同样产生DRAW提示，不能按通知逐字释放或把通知数当字符ACK。焦点切换保持“输出当时光标”语义；取消、过期和替代硬停止；无剪贴板或系统输入法回退。24.04验收仅Xorg，GNOME46原生Wayland未宣称支持；XWayland DRAW不外推。

原生Wayland保留既有BMP字符边界，非BMP明确拒绝；不宣称完整Unicode、Windows或macOS支持。未在本轮完成的物理麦克风、真实云供应商、物理全局快捷键/ESC、native浮层焦点、第三方终端矩阵、负载/毁窗以及所有依赖缺失桌面矩阵保持未验。离线单测与桌面结果分列，不互相替代。尚未改用户安装/稳定入口，尚未merge/tag/upload/publish；root已接受上述有限必需类别及两系统清理收尾；发布前仍需0.10.1报告提交的完整源码检查、正常hook推送、0.10.0构建源可达main、精确tag/远端产物核验。

## 原始证据与可复现入口

- 0.10.0 source workflow：`build/release-0.10.0/source-workflow.log`；正式构建/提取/审计：`build-receipt-r1.json`、`extract-receipt-r1.json`、`freeze-and-audit-summary-r1.json`。
- 24.04冻结summary：`build/release-0.10.0/ubuntu24-acceptance-summary.json` SHA `fc5ef6b27278e110eb5f263bdd11212e2d957881211b5dddc75612b2d95ab8d0`；259个原文件pins：`ubuntu24-evidence-pins-r1.json` SHA `4b0d5cff11779860fd30f9166f04ca0524b46d03030a4591c2cfc6ecb1dfc651`。所有raw目录、ready身份、原工具session、原wait和fixture失败均在其中。
- 26.04非输入：`build/ubuntu26-release-vm/package-noninput-raw-r1/`，原传输tar SHA `69f1e17286b71b0e8409a3e65b6c68904e0fe01a83a0d8ac20ccc0576d0358da`；entry-r1失败不覆盖，entry-r2独立侧helper通过。
- 26.04真实FUSE：`build/release-0.10.0/guest26-fuse-r2-raw/`、`guest26-fuse-launch-owner-r1.json`（失败）和`guest26-fuse-launch-owner-r2.json`（原wait0）；精确结果文件散列见consolidated JSON。
- 源码探索完整时序/失败：`docs/adaptive-output-validation.md`、`build/adaptive-output/result-summary-final.json`、`build/adaptive-output/FINAL_EVIDENCE.md`，不能当作本次包结果。

复现必须先对选中的同版本同SHA包、sidecar、inventory和冻结helper manifest完整核验；在对应完整桌面自解压并用包解释器通过audit-only，随后新建自有窗口，审PID/start/XID/backend/空白图/expiry，在发送前再核对期限及held keys。24.04使用冻结guest.py的`entry/quiet/protocol/vad/audio/output-normal/output-long/output-cancel`门；实际focus使用独立side manifest `5a78b4c868490b494a94449ea8483b5f04b4fc84c31976f556b6134791365c19`和新fresh双receiver。发送严格一次，尾部观测至少1.2s，停止文件后保留原wait/cleanup。不得把历史PID或ready文件拿来重新发送，也不得在宿主用户桌面执行此流程。
