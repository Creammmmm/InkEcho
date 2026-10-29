# Fcitx focus protocol v2：完整构建与私有 D-Bus 验证

2026-10-29，在新建一次性 Ubuntu24.04 QEMU/KVM 覆盖盘内进行；原镜像与原状态盘只读，无外网，不连接宿主或客机图形会话。系统Fcitx/Core/Utils开发包均为5.1.7-1build3；实际编译器、CMake和ldd记录见raw/environment.json。

生产v2 addon原样完整configure/build自然0，旧v1对照和独立test-control也完整构建0。v2 libinkecho.so SHA-256为3a3c80fb464bbfce465b52cb73e998a00705998a768c45400416daf29e89a497；本目录只保留源码/脚本/文本记录，不包含二进制、对象或构建缓存。不替换仓库固定候选/安装目录，也不是AppImage包验收。

独立test-control创建真实Fcitx InputContext和两个FocusGroup；通过独立私有总线设置0/1/2个焦点，只接收固定公开甲乙并计数，不读取用户正文或周边文本。生产addon没有fixture宏或源码覆盖。

## 最终r3结果

| 检查 | 新v2插件 | 旧v1插件 |
| --- | --- | --- |
| 旧Begin，nofocus/多focus | 3/3 | 3/3 |
| Begin2(token,2)，nofocus/多focus | 3/4 | 不宣称支持Begin2 |
| 当前新Python client | 协商v2 | introspection发现无Begin2，正常退回v1 |
| 未发送seq重复尝试、focus恢复 | seq保持，唯一提交后重复seq拒绝 | 同左 |
| Cancel后提交 | 拒绝0 | 拒绝0 |
| auto首字前0或2focus | 真实bridge明确未提交后进入键盘spy；native计数0 | 同左 |
| auto已有一个前缀再出现多focus | 不handoff、不重放，接收仍仅前缀 | 同左 |
| 原始私有daemon退出 | 自然0 | 自然0 |

r3共7/5组断言通过，两次dbus-run-session原wait0，两个Fcitx原wait0。实际Python/native、私有D-Bus与真实Core均参与；系统框架detector和最终keyboard是控制性替身，后备只记录长度，不发送真实桌面键。不能因此声称完整系统自动检测、真实键盘后备或GTK/Qt/Chrome投递已验证。commitString和返回1仍是尝试，不是应用显示/接收回执。

## 原失败完整保留

- 初次容器使用旧KVM组108，实际设备组991，QEMU在客机启动前拒绝。仅修新容器补充组，未修改宿主权限；见failed-start-r1.json。
- guest既有network-online启动等待导致两次SSH banner超时，后正常启动，未修改网络等待服务。
- r1协议断言7/5组通过，但独立fixture错误地把InputContext作为值成员；Core finalize调用delete触发double-free、daemon SIGABRT(-6)。raw中passed=true只是初版脚本过早赋值，**不能视为清理或整体通过**。r1原result与fcitx.log均保留。
- 仅修test-control：上下文堆分配，Quit前显式注销并释放context/group；生产v2二进制未改。r2 daemon自然0，但最后80ms绝对deadline测试只允许partial_input_failed过窄，实际返回安全的fcitx_delivery_unknown，原断言失败保存。
- r3只修测试预期：deadline边界允许partial_input_failed或delivery_unknown，但两者都必须停止、无keyboard后备、无重放、接收计数只有先前一个前缀；未增加deadline或改变产品时序/底线。r2原记录未改，r3必须同时protocol断言与daemon退出0才passed=true。

## 复现与范围

只在已具备相同SDK的隔离Ubuntu24.04 VM运行scripts/reproduce.py。传入包含本轮匹配源文件的InkEcho仓库和dbus_next包父目录（dbus-next0.2.3）；脚本先检查VM、UID、源/依赖散列，任何不一致就拒绝，绝不安装包或改系统输入法。脚本使用/tmp/inkecho-fcitx-v2固定新目录，已存在则拒绝，不删除旧数据。frozen保存实际native/fixture源，scripts/*measured*保存实测脚本原字节，raw/source-pins.json记录Python/dependency源身份。

完整构建命令是对frozen/{product-native,legacy-native,test-control}分别执行cmake -S/-B及cmake --build -j2，原argv/stdout/stderr见build-receipts.json。run_protocol_measured.py.txt以dbus-run-session启动，每个variant全新私有总线，过程使用私有HOME/XDG_CONFIG_HOME/XDG_DATA_HOME/XDG_RUNTIME_DIR，禁用wayland/xcb/clipboard等桌面前端，结束经自有Quit正常退出。

没有测试Ubuntu26/Fcitx5.1.19、原生Wayland、XIM/GTK/Qt/Chrome的真实焦点切换、系统选择能力或最终AppImage；SDK兼容或内存上下文不得冒充这些支持。没有通用客户端逐字回执时，唯一Fcitx上下文并不能排除不同IM控件或异步切换造成的静默丢失。本轮改进提供原子无/多focus风险分类，不宣称彻底解决所有控件。

测试结束确认自有私有Fcitx进程为空；一次性VM正常systemctl poweroff，原docker wait0，exited/Runningfalse/ExitCode0/OOMfalse；正常关机记录在raw中。共享工作树、用户配置和固定产物均未修改。
