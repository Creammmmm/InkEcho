# Fcitx 运行时版本候选：双系统独立实验

2026-10-28，使用 Ubuntu 24.04 隔离虚拟机的 GCC 13.3.0 / CMake 构建
`native/fcitx5`，得到候选 `libinkecho.so`，SHA-256 为
`532ef632385bfe9ae3b76312b74874a7cc562c58435bb07f430e704179ebd139`。
该文件暂存在被 Git 忽略的 `build/ime-feasibility/runtime-version-candidate/`，
当时没有覆盖 `assets/native` 的固定载荷；后续已将该候选集成到工作树，
仍须完成最终包验收。候选源文件 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `CMakeLists.txt` | `30cf333e2a67288c76b2d5b9dbf9095c8b68cde61c108653c277d8ef46faa850` |
| `focused_context.h` | `29d9ce8944be97cd1d993f0de41342094d6bac433b573fa34f6ba1762620b8a5` |
| `inkecho.conf.in` | `4911bd724fbd1035fb3d24dbe6e872ceb3e20fc38976a1db8af244ca0c689b0e` |
| `inkecho.cpp` | `309f5fbb0ed65b607ad0a6b96c9316e37579e0c0fd7a5abccf19318c8cb7e3f4` |
| `task_gate.h` | `88f2a9dc762d5d135818531621b85fa1873b132ecb2926a04e68456355df9a80` |
| `utf8_scalar.h` | `685754ac1701df448902bcc57adee099925b6dc80ecac06cbea7e669c6913da9` |

相同候选在 Ubuntu 24.04 / Fcitx 5.1.7 的 Xvfb 图形会话及 Ubuntu 26.04 /
Fcitx 5.1.19 的 GNOME Wayland 会话中的自有 XWayland GTK 控件分别实测：
查询运行时版本返回各自版本，控件收到合成字甲，取消后提交乙返回拒绝且
控件仍只有甲。停止并重启独立 Fcitx 进程后，24 的 owner 从 `:1.1` 改为
`:1.16`，26 的 owner 从 `:1.1` 改为 `:1.13`；旧唯一 owner 查询失败。
24 另有无目标时返回 3、取消后提交返回 0 的独立会话测试。两次测试均未
读取用户文字；来宾临时目录、自有进程已清理，两台虚拟机正常关机、容器
退出码均为 0。

## 复现

以下操作仅适用于隔离虚拟机，且需要 CMake、Fcitx5 开发包、GTK3、
`xdotool`、`gdbus`、Python GI；24 的图形测试还需要 `xvfb-run`。候选和
脚本应先复制到客机 `/tmp/inkecho-runtime-version`。版本配置行应使用
目标系统 Fcitx 版本；不要将候选安装到真实用户输入法目录。

```sh
mkdir -p /tmp/inkecho-runtime-version/build
cp native/fcitx5/* /tmp/inkecho-runtime-version/
cp experiments/fcitx-runtime-version/owner_probe.sh /tmp/inkecho-runtime-version/
cp experiments/fcitx-runtime-version/protocol_probe_measured.txt /tmp/inkecho-runtime-version/protocol_probe.py
cp experiments/ibus-gnome-shell/auto_detection/target.py /tmp/inkecho-runtime-version/
cmake -S /tmp/inkecho-runtime-version -B /tmp/inkecho-runtime-version/build
cmake --build /tmp/inkecho-runtime-version/build
sha256sum /tmp/inkecho-runtime-version/build/libinkecho.so
xvfb-run -a dbus-run-session -- /bin/sh /tmp/inkecho-runtime-version/owner_probe.sh
```

在 26 上使用**24 构建的相同二进制**，将配置中的核心依赖版本写为
`5.1.19`；在已登录的隔离 GNOME Wayland 客机中，设置该桌面会话的
`DISPLAY`、`XAUTHORITY` 与 `GDK_BACKEND=x11`，然后运行
`dbus-run-session -- /bin/sh /tmp/inkecho-runtime-version/owner_probe.sh`。
XWayland 使用的是来宾虚拟桌面，不是宿主用户桌面。

实测原始脚本仍在仓库：`owner_probe.sh` SHA-256
`3f1be55ac13cbac0e6e21e1397d178feb572df8a7a453e030656c037ff4194e9`；
`protocol_probe_measured.txt`（原 Python 脚本字节不变）SHA-256
`87398d104a85ff2fe1ffeef4a4eb35323aa2efc659cfe21a1549422631509230`；
`target.py` SHA-256
`d5ecb06be3fd9dfaa5c2e249bb42f2c0702e422624a9bb393f472cdd8317e76c`。
同目录 `protocol_probe.py` 后来仅调整 import 格式，调整版未在客机重跑。

## 范围与未完成项

这是独立插件实验，不是最终 AppImage 的双系统包验收；24 的 Xvfb 不代表
GNOME Xorg，26 的 XWayland 不代表原生 Wayland。尚未覆盖发送中 owner
切换、真实软件包升级、产品自动/显式路由、长文本和输出期间切换窗口。
`RuntimeVersion` 返回的是运行时调用的 Core 版本声明，不能证明全部辅助库
版本、目标已经显示文字，或竞态不存在。发送状态不明时仍不得重放。
发布前须更新并审查固定源码和二进制摘要，重新构建同一 AppImage，在两个
系统按项目规范完成实际包验收并记录未验限制。
