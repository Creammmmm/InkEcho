# a15 同一 AppImage 双 Ubuntu 验收

2026-10-18。同一 a15 AppImage 已完成 Ubuntu24.04.5 KVM 的真实 Xorg 桌面与
Ubuntu26.04.1 GNOME50.1 Wayland 主机的限定实际包验收；主机分别验证原生 Wayland
与 XWayland 接收方。主 Agent已独立审查必需原始结果和两系统九页截图，确认本节
所列同包门通过。这不表示所有会话、应用、麦克风或云端语音链路均已支持。

双系统结果与升级前完整检查经主 Agent审核后，稳定入口已更新为受验 a15，托管图标
已替换；同一路径的私有配置实际 FUSE 启动与自退出也已通过。用户配置和旧版本保留，
没有控制原用户应用实例。本轮未创建新的 GitHub release。最终文档提交的完整检查仍
以精确HEAD回执为准。

## 已完成：候选构建与来源核对

| 项目 | 固定值/实际结果 |
| --- | --- |
| 产品版本 | `0.1.0a15` |
| 构建源码提交 | `27aef8c1ee6ac33cc152e8588cc83daa727d4533` |
| Artifact | `dist/InkEcho-0.1.0a15-x86_64.AppImage` |
| Artifact SHA256 | `b92ffd979f2faa979a22e9fd9a0be8cd187607009bd42313ef34fd91e660a598` |
| 大小 | 108866040 bytes |
| 原构建观察handle | 31812，原owner确认自然exit0 |
| 实际提取AppDir | `build/a15-build-preparation/extracted-r1/squashfs-root` |
| 清单核对 | 3959文件、1048链接、44源文件与构建提交/计划一致 |
| Inventory SHA256 | `282b03e1b4e31af6b6814f2ea9af77513cb878d565199e8d3f8f73da075bb39d` |
| 其他核对 | artifact sidecar、四处产品pins、图标一致；旧稳定a14与用户配置保留 |

主 Agent已核对原构建记录；本报告只读核对结果metadata，证据
`build/a15-build-preparation/candidate-a15-build-result-r1.json` SHA256为
`ed23bc95a3dbd1f4d430924232dcea391fa8ee701f4ce69a8b975c6b7de03223`。
该结果明确 `desktop_or_cloud_launched=false`，构建与静态清单核对不证明运行时
origins、桌面输入或实际双系统兼容性。原构建、提取与保留记录位于相邻目录，
不得覆盖为后续新结果。

| `src/inkecho/platform/`下产品源 | 构建内SHA256 |
| --- | --- |
| `keyboard.py` | `c0d97c3bef0344465b40a547b89ca6284eb6b6bbd9fea17cb97f1092105b165f` |
| `hybrid_keyboard.py` | `4005f609b46a3e4bafef5cddf27e0672830f1d07b5611a0b29bcbd1c97b4c987` |
| `wayland_keyboard.py` | `908d5c61d0dec8066385554db7652d06e83a42dd5e736f3d96f7aa54c00cbf69` |
| `wayland_worker.py` | `9ecacec1dc36c34c52bbbec66cdf088712e5f0488c2d0dd02781557dfa6edd43` |

## 源码证据与完整检查的界限

[输入提速追踪](input-speed-optimization.md)保留阶段1路由、阶段2事务/最近映射复用、
阶段3分项等待校准的历史证据与失败记录。阶段3有56项实际参数实验；采用设置后的
当前源码factory另有4项实际normal/cancel8烟测通过。这些使用冻结源码与a14依赖，
不是a15实际包结果。特别是单insert参数实验、70ms生成片段流式实验、受控ACK/
前缀暂停交接分别有不同口径，不能拼成一个端到端提速比例。

阶段3提交 `d49c64d37be41e56904ad1056f930a131ede0910` 已完成clean-HEAD工作流：
**1536 passed、3 skipped，39.50秒**，实际receipt为
`.git/validation/d49c64d37be41e56904ad1056f930a131ede0910.json`，绑定当时证据
`docs/input-speed-optimization.md` SHA256
`df27df9f40181f5f2f046e864ca34d5ee3a67594a9557afba9d7861c6ca10920`。
此历史回执不覆盖后续提交。升级前验证器与同包报告提交
`71b58cd97c23bfae845a23da9ee0994017986b44` 已完成clean-HEAD完整检查：
**1542 passed、3 skipped，39.70秒**，receipt绑定当时a15报告SHA256
`d8cd0551ed5dace6a0eb8e6958b461496dca150dff6e7143f3b2897ad3a3c9be`。
它不自动覆盖本次部署后文档更新；最终文档提交仍须自己的精确HEAD/evidence回执。

## 同 SHA 双系统实际包结果

| 环境 | 同一 a15 实际结果 | 原始证据 |
| --- | --- | --- |
| Ubuntu24.04.5 LTS / KVM / kernel6.8.0-142-generic / GNOME46.0 / session20 Xorg | 9项实际模式通过；独立包提取原 owner退出0；GNOME原身份26971，逐模式验证未锁屏 | `build/ubuntu24-perf-vm/output/a15-acceptance-r1` 与 `a15-factory-r2` |
| Ubuntu26.04.1主机 / GNOME50.1 / Wayland；native及XWayland目标分别实测 | 20项实际模式通过；每项原 Popen owner退出0 | `build/a15-acceptance-preparation/results-r2` |

双系统综合结果 `build/a15-acceptance-preparation/dual-os-results-r1.json` SHA256：
`36dad91abb89a71203b9872d0e90f03b2b157595c66e264cd2676406d5dcd90f`。
它绑定 host20 汇总 SHA
`18c04b313c49222d67e0f56061c583acb4c096088fff2ffe82a4135994b834b6`
与 guest9 汇总 SHA
`086b1fa26d288eddba4486e2ac6eda3945f1c8091329f6c61f7bf15e1eca69c2`，
包含各原始结果、原 owner/终态、私有截图和配置/旧产物保留记录。早期 host汇总生成时
尚未完成 guest，保留其当时 `not_dual_os_complete_yet` 字段；最终状态以综合结果和
对应实际原始回执为准，不回写早期快照。

### 来源、清单和新验证工具

受验包始终为上表唯一 `b92ffd...a598`、108866040 bytes，产品源码始终为27aef8c，
没有为验证器修复重建产物。新冻结树为
`build/a15-acceptance-preparation/frozen-r1`，226文件、44产品源文件，manifest SHA256
`437b5eefdbe2b9c63a14e56d82917bfcc15d808728da8cec0978e160106f08f8`。
从精确 git 对象复制 tracked 源码、工具和许可；额外受审 mixed辅助 SHA256为
`4548dae17985a4d62327e2956f9a78de6603d304096db5a1d00cc908bc2ea58e`。
实际包解释器审计3959文件/1048链接/44产品源/19模块来源（含Hybrid），不从源码
覆盖产品。host只读运行时审计 SHA256
`6ccaf792259133450d11f109357b1a5c1737ad4e144caa596ff286157f0c437c`。

实际 host R2 全20项 argv/环境增量为 `host-preview-r2.json`，SHA256
`5628fad486c41fff49522a331f62c08beff6f52cfdc7c0f63e9ada5869adaee2`；
其原 owner脚本 SHA256
`312d376ba1ae558ab6e5dd2d353767075d546326ea8c050950913df8f2b6438b`。
Guest原计划 `guest-plan.json` SHA256
`4edb418a22a45adffb834e025cf144cc4fc51b278068d96e923fac6be7178d01`，
AppRun显式清除六个开发变量，只保留实际图形会话和私有XDG；host亦清除对应变量。
本地 SSH 与 guest实际 producer 分别由原 Popen owner等待，未以PID消失代替退出码。

Guest最后两项使用独立验证器修正树 `guest-factory-r2/frozen`，226文件中只有
`input_speed_probe.py` 与原树不同，产品44文件逐字节完全相同。新 manifest SHA256
`61a2f5432dab9838ee19890ca950e7eee92955d569dacdeafaf9f1613eb9deaa`，
修正工具 SHA256
`bd0248d7f0a49ba37545028d0eee4525da5d461fa97e427da8b6d70d37ccb176`，
新两项计划 SHA256
`b87dae666baddcaad6c4a18f226c2f91f0201a962fcc0ce32e0c854b4131f2c1`。
这份工具与受验 mixed辅助现已保存至 tracked `scripts/validation/`，正式测试保存至
`tests/`；该后续验证脚本提交不改变已受验包及其产品源码提交。

### 各模式实际覆盖

| 模式 | 实际结果与界限 |
| --- | --- |
| 两系统 ui-protocol | 5/5 checks：HTTP协议不匹配标注、切实时清除、切回HTTP再标注、私有保存重载、提示不声称OS不支持。实际Qt平台host wayland/guest xcb，19包来源，真实密钥读取0 |
| 两系统 local-wss | 包内Session运行本地 TLS/WSS与HTTP/SSE，生成音频/受控输入，25字符最终结果精确；第二任务取消无尾部、固定服务及线程清理成功、server_errors为空。不是麦克风或真实桌面输入，不访问云 |
| 两系统 AppRun九页 | 使用各自提取的真实 AppRun、私有HOME/XDG/config/data，九页截图与原退出0；主 Agent已逐图视觉审查中文、新图标、a15版本和布局 |
| host native textarea/contenteditable | 各29码点BMP混合样本精确、29对按键、guard0、first callback1、Chrome/worker均0；map/group/所有modifiers前后完全相同 |
| host native cancel/nonbmp | cancel在8字符停止，0.5秒无尾部，8对按键；非BMP明确unsupported_text、0按键/0callback，不能写成emoji可用 |
| host native-mixed（旧直接后端） | 29字符精确、29对按键、3callbacks；仅为直接后端补充结果，不代替下列工厂自动路由验收 |
| 两系统 X11字段与取消 | textarea/contenteditable各31码点混合样本（含中文、组合字符、emoji、换行）精确、31对按键；cancel8精确，0.5秒无尾部，guard0、map恢复/driver关闭/目标退出0 |
| 两系统 X11 currentcursor | 同输出事务内切换两个自有窗口，精确分段[5,26]，31对按键、两Chrome退出0；guest是Xorg，host是XWayland |
| host factory4 | 实际keyboard_for_desktop创建Hybrid，native与XWayland各100字normal及8字cancel精确；route正确、1callback、balanced、guard0、scope仍开时及最终的双映射恢复、worker与Chrome退出0 |
| guest factory2 | 实际Xorg工厂创建KeyboardInput，normal100字与cancel8精确，route正确、1callback、balanced、guard0、X映射作用域内与最终恢复、Chrome退出0；native观察明确N/A，无native worker |
| host factory controlled-mixed4 | 双方向正常各[10,13]精确23字；取消各[10,4]精确14字，input_cancelled，1callback、guard0、两后端mapping epoch不重叠且闭合，双映射恢复、两Chrome及worker退出0 |

最后一行在真实native key ACK/有限X前缀边界暂停后自然打开自有窗口，没有CDP激活
焦点或bootstrap按键。这证明受控交接及当前光标的有限语义，不证明未暂停的post-map
切换race、跨窗口原子性或所有应用。输出焦点本身不使产品任务取消；测试owned guard
只防止测试正文进入用户窗口。没有剪贴板或系统输入法回退。

实际包100字普通BMP、完整文本就绪的单次测速（各环境仅1次）为：host native
9.976秒/首按键80.45ms；host XWayland4.761秒/首按键106.85ms；guest Xorg5.031秒/
首按键106.84ms。均包含owned guard和事务清理，不是SSE供给速度、云识别延迟或可靠性
分布，不能跨环境拼成提速比例。阶段3参数对照的中位数口径另见输入提速报告。

### 保留的失败和显式新实验

1. Host R1首项 `ui-protocol` 原producer823067/start45112892自然退出2，stdout为
   acceptance_preflight_failed、stderr0B。新owner漏建公共work-r1父目录，工具在
   QApplication创建前的mkdir失败，未显示UI或发键；不是产品输入失败。
   原日志/owner/terminal与preservation未变记录保留。经主 Agent审查，新R2只改变
   独立work/results路径，显式创建一次work-r2父目录，随后20项全部通过。
2. Guest原factory-normal原producer64487/start18434353与本地SSH均自然退出2。
   验证器在try前访问不存在的KeyboardInput.backend，stdout仅安全AttributeError，
   初始raw保留，worker列表和浏览器目录均空，0Chrome/0输入。已过7项未重跑。
   修正为可选getattr并增真实无I/O Xorg工厂测试；经主 Agent审查的独立R2两项
   使用同包/同AppDir和新工具快照实际通过。取消项在原失败队列中未启动。

两次失败均未kill、重放正文或覆盖历史证据，也未修改产品包。更早源码测速工具的
r1自有测试线程残留及已授权清理例外保留在输入提速报告，不能混为本次包成功结果。

## 已完成：稳定入口、托管图标与私有 FUSE 启动

双系统同包必需门、原始证据审查及71b58cd完整检查通过后，主 Agent批准精确部署计划，
仅更新13个白名单文件：稳定AppImage及sidecar、managed launcher、8尺寸图标、两个
正常桌面缓存（mimeinfo.cache与icon-theme.cache）。实际包的
`DesktopIntegration(STABLE).install()` 使用正常PATH并正常刷新缓存，没有改产品实现。
此前managed launcher的_owned与_entry精确一致，8旧blue图标均被识别，未知图标/符号
链接会在写入前拒绝。旧autostart和scalable SVG均不存在，部署后仍不存在。

实际apply原owner835489/start45218367正常退出0；
`build/a15-acceptance-preparation/deployment-r1/result.json` SHA256：
`3eae3f4aecceeffce3fa472cf7c1471f0ec7eff5bfe99bd7d3585e2dde1351ab`。
稳定入口 `dist/InkEcho-0.1.0-alpha-x86_64.AppImage` 与sidecar现为受验b92完整SHA。
13个原文件已逐字节备份在deployment-r1/backups，目录0700、文件0600；backups.json
记录原路径、mode和SHA，所有备份均与原值匹配。原versioned a14文件仍为bce09c…cc96，
versioned a15仍为b92ffd…a598，没有删除旧产物。launcher保持正确稳定路径，8图标
逐个匹配新包资源；两个derived缓存分别记录部署前后SHA，不假定其内容不变。

三个用户配置文件前后SHA完全不变，仅作hash核对，不读取或记录凭据正文：

| 文件 | 保留的SHA256 |
| --- | --- |
| config.json | `d4c65ca0558163fe56baf344ce10d2769cc0e25c9e8d05bea15b773ef9d16287` |
| providers/qwen.json | `54a3fafcb898192e19782d6b25daefb2add196036c21e2de79587c95ac66bf9d` |
| providers/deepseek.json | `ac458a84ae771564ffafa6529fee231c8813b9ab7082124f80ded7acf04c3306` |

没有更改快捷键、API配置、自启动或用户实例状态，没有IPC退出/强杀原用户应用。
没有为部署访问keyring、云服务或启动录音。

随后从同一稳定路径启动唯一私有配置实例，使用新独占config/data/HOME/XDG、清除六个
开发变量，截图九页并由`--quit-after 3`自行退出。原producer837474/start45225918
退出0，实际观察到FUSE挂载 `/tmp/.mount_InkEchgcpDFB` 的包内Python与a15版本；
完整3959文件/1048链接清单和44产品源均匹配，13部署文件/原配置/旧版本保留检查通过。
这不是提取AppRun冒充FUSE。结果 `private-fuse-r1/result.json` SHA256：
`2827a5af9928486e13964473b14975fde1272a9faedecf5cd46275a53e69446f`；
原终态SHA256为
`97807daa62fba844040347bb7e5182df39b2a152a07777afade0f9f75e2e71fd`。
stdout确认screenshots9/platform wayland/visible true；stderr400字节仅Qt FFmpeg启动
信息和两条Wayland textinput disableSurface焦点警告，无异常。该Qt警告不表示本应用
采用系统输入法投递文字。

主 Agent已查看私有FUSE的about页，a15、新图标和实际稳定路径清楚可见。该私有XDG
没有安装launcher，界面显示“尚未安装”是隔离配置预期，不代表真实用户目录的managed
launcher未安装；真实13路径已独立核对。没有因此再打开普通用户配置实例。

## 可复现入口与最终检查

先核对同包SHA、来源与已审快照；为每次运行选择新独占工作/结果目录。保留真实已
解锁桌面白名单，不输出环境或读取keyring。包解释器只加载其自身packages。具体
完整argv由上列固定预览保留，复现模板如下（不是自动运行/云请求授权）：

```sh
artifact=/absolute/path/InkEcho-0.1.0a15-x86_64.AppImage
appdir=/absolute/path/extracted/squashfs-root
frozen=/absolute/path/reviewed-frozen-repository
qa=/absolute/path/new-exclusive-output
sha=b92ffd979f2faa979a22e9fd9a0be8cd187607009bd42313ef34fd91e660a598
mkdir -m 700 "$qa"
env APPDIR="$appdir" PYTHONHOME="$appdir/usr" \
  PYTHONPATH="$appdir/packages" LD_LIBRARY_PATH="$appdir/usr/lib/inkecho" \
  QT_PLUGIN_PATH="$appdir/packages/PySide6/Qt/plugins" \
  PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 QT_QPA_PLATFORM=wayland \
  "$appdir/usr/bin/python3" -B "$frozen/scripts/validation/input_speed_probe.py" \
  --runtime package --artifact "$artifact" --artifact-sha "$sha" \
  --package-root "$appdir/packages" --backend native --field textarea \
  --work-root "$qa/work" --output "$qa/result.json" --run-reviewed
```

Host XWayland将backend改为xwayland；guest真实Xorg亦用该X传输参数名、Qt平台xcb，
报告仍须实际标Xorg。追加`--cancel`验证full100请求中止于实际第8次按键。工厂交接
入口为tracked `package_factory_mixed.py`，使用相同包来源参数（其选项为
`--expected-sha`、`--frozen-source-root`、`--expected-version 0.1.0a15`），case分别为
native-to-x-normal、x-to-native-normal、native-to-x-cancel14、x-to-native-cancel14。
只在实际支持的host Wayland会话串行执行，每次先等待原owner和目标/worker终态。
UI/local协议/九页与Xorg/原生后端的完整模板保留在host/guest计划，不从源码启动产品。

验证器修复与受验mixed辅助的相关正式测试本地结果为66 passed，0.19秒，Ruff通过；
这是纯测试，不替代上列实际包结果。71b58cd升级前完整检查已通过，部署后最终文档
提交仍须执行自己的干净HEAD完整检查：

```sh
.venv/bin/python scripts/validation/workflow.py run \
  --module a15-dual-ubuntu --evidence docs/a15-dual-ubuntu-validation.md
```

以精确HEAD的receipt及本报告SHA绑定为准；未产生最终receipt前不宣称此检查完成。
稳定入口替换与私有FUSE启动已按上节完成；不把升级前回执冒充部署后文档提交回执。

## 范围与未验限制

- 本次guest实际仅Xorg；GNOME46原生键盘API历史测得不可用，本次没有将它改写为
  原生Wayland支持。Host的实际范围为GNOME50.1的自有native/XWayland字段，不泛称
  所有Linux桌面、应用或跨平台均通过。
- 本轮没有真实麦克风、物理快捷键/F13/F14、overlay不抢焦点或官方云能力请求。
  旧a14官方Qwen能力成功不能回填a15云验收，更不代表语音准确率。
- 本地生成音频、固定协议服务、真实桌面键盘输入是独立检查，不能组合称为真实
  麦克风到官方云再输入的全链路端到端测试。密钥/keyring读取、云请求均为0。
- 双系统前置包验收使用提取后AppRun；部署后host真实FUSE及managed launcher/图标
  更新另已实测。Guest FUSE、路径迁移修复和登录自启动仍未验，自启动保持原缺省状态。
  原versioned a14、用户配置/供应商及旧artifacts全部保留，稳定别名现为a15。
- 原生非BMP仍明确不支持；不回退剪贴板或系统输入法，不重放不确定的已尝试输入。
