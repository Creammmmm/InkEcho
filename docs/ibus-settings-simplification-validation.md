# IBus 设置入口简化验证

2026-11-09。本改动仅简化设置页面，不改输出后端、路由、已保存配置或自动模式。
待验源码基于 `06a551f72b3b48166f121a9884bd4f41fdb72aba`。
`src/inkecho/ui/information.py` SHA-256 为
`e653121eb01d479f90907ae0677e517b743e1ef5d78654a05614fb98941eb11c`。

## 页面行为

新配置不显示旧 V2 IBus 选项。已保存的 `ibus` 值仍可读取、显示和使用原后端。
仅在实际 GNOME Wayland 的已有旧配置中保留旧扩展检查与停用按钮，删除安装、
启用入口。没有自动迁移旧用户。

当前选项明确标为“IBus（GNOME Wayland）”。仅在 session 为 wayland 且桌面
组件包含 GNOME 时推荐此选项及所需扩展管理入口。Xorg、未知会话或其他桌面
不为新配置提供该选项，但已保存的 `ibus-owned` 值保留并显示适用范围诊断。
真实后端仍需要的 GNOME Wayland owned 安装、启用、检查和停用入口继续保留。

打开页面不写配置。写设置失败后，若磁盘已由其他操作改成隐藏的旧值，界面
补回该已保存选项，而不是留下空选择。非 GNOME Wayland 的自动模式文案只
描述 Fcitx5 与键盘，不暗示可用 GNOME 扩展。没有宣称 stock Xorg IBus 直接
输出可用，相关边界见[阶段 0 报告](stock-xorg-ibus-phase0.md)。

## 自动化检查

五个受影响文件共 155 项通过。覆盖新旧配置、实际 GNOME 组件匹配、其他桌面、
打开不写入、40 ms 设置保留、异常写入后的旧值恢复及原有维护生命周期。
Ruff 与差异空白检查通过。

```sh
PYTHONPATH=src:tests:scripts/validation QT_QPA_PLATFORM=offscreen \
  python -m pytest -q tests/test_ibus_extension_visibility.py \
  tests/test_explicit_owned_ui.py tests/test_ibus_xorg_guidance.py \
  tests/test_owned_upgrade_guidance.py tests/test_ui.py
```

这些测试的桌面参数是受控夹具，不代替下面的实际会话观察。

## Ubuntu 26.04 GNOME Wayland 源码页面观察

独立客机实际环境为 Ubuntu 26.04.1、ubuntu:GNOME、Wayland，Qt 使用 wayland。
以已验 0.16.14 AppImage 作为运行时，仅替换 information 模块为上述源码。
其余模块仍从包中加载。这不是包含此 UI 改动的新包验收。

三个独立临时 ConfigStore 分别保存 auto、ibus、ibus-owned。实际显示页面后
三者配置均不变，选择值保留。auto 无旧 V2 入口，ibus 仅有旧扩展检查与停用，
owned 管理按钮保留。未调用安装、启用、停用或服务操作，也未改变桌面输入法。

原始报告为 `/tmp/inkecho-ui-wayland26/REPORT.md`。最终三张截图和结构化结果
位于其 `output/ui-smoke-final`，记录模块来源和最终哈希。早一次检查使用改写
Xorg 文案前的源码，保留在 `output/ui-smoke`，不作为最终源码证据。

这是独立 CompatibilityPage 的控制项检查，没有完整 MainWindow 的主题和
布局。截图顶部部分长说明和表单被裁切，不能称为完整视觉美观度验收。
客机测试进程清空，正常关机，QEMU 和容器返回 0，专用容器已删除。

## Ubuntu 24.04 Xorg 源码页面观察

独立客机的最终源码结果位于
`/tmp/inkecho-pkg-01614-auto-fcitx24.XGUOXU/output/source-only-ui/result.json`。
实际模块哈希与本文一致。新 auto 配置只显示 auto、keyboard 和 Fcitx。
已保存 legacy 或 owned 各保留自身选项，并显示 Xorg 适用范围诊断。
不存在扩展管理按钮或服务调用。三个临时配置在打开页面后均保持不变。

该检查同样是旧运行时上的源码页面观察，单独页面截图也存在长说明裁切。
两组实机结果证明选项与控件条件，不构成完整主题布局或新包验收。

## 交付边界

本次未打包、未更新稳定入口或发布。0.16.14 同哈希包的既有验证不包含本次
设置页变更。后续新包仍需按项目规范完成同版本同哈希的双系统验收。

## GNOME Wayland 的 IBus 输入桥配置合并

当前 Wayland 页面将安装、启用合并到「配置 IBus 输入桥」，保留检查和停用。打开
页面或保持自动模式不触发配置。明确点击后，缺少时安装随应用提供的校验文件，随后
尝试由 GNOME 启用。安装和启用纳入一次输入维护操作。GNOME 若尚未识别新文件，
界面提示重新登录并再点同一按钮。旧扩展升级仍遵循停用和卸载指引。GNOME 50.1 的
本地安装命令把文件移入用户扩展目录，运行中的 Shell 拒绝尚未登记的 UUID 时，
启用命令报告失败。 [GNOME 安装命令](https://github.com/GNOME/gnome-shell/blob/50.1/subprojects/extensions-tool/src/command-install.c#L121-L150) · [GNOME 启用命令](https://github.com/GNOME/gnome-shell/blob/50.1/subprojects/extensions-tool/src/command-enable.c#L40-L78)

独立 Ubuntu 26.04.1 GNOME 50.1 Wayland 客机使用 Qt Wayland、IBus 1.5.34~rc2-1
与 GTK 3.24.52。运行时为 0.16.14 AppImage，SHA-256 为
`1294d46ccaa35878011c462407c44d025ac405b12ea5293ee6256d633bdeb8b9`。仅在
解包的运行时中覆盖 `information.py` 和 `owned_extension.py`，对应源码 SHA-256 为
`34a8e357890adf2741cd2a96e9127bfcf652b993ec2513d2dfc0eb576f490bc3` 和
`fce207ae707de005bfe8c4ff371c617ccc5603d42e1f8da3e9bc8255828a589d`。

- 暂存客机原扩展并重新登录，打开独立 `CompatibilityPage`。页面显示单个配置
  按钮，打开前后临时应用配置、扩展文件状态及 GNOME 设置一致，输出方式为 auto。
  对真实可见按钮发送一组 Qt 鼠标按下、释放事件，确认仅触发一次。首次安装七个
  匹配内置摘要的文件，目录 0700、文件 0600。当前会话没有启用扩展，界面给出
  重新登录、再点同一按钮的提示，GNOME 设置仍与点击前一致。
- GDM 重新登录后，同一按钮一次点击完成启用。UUID 目录和七个文件的 inode、
  修改时间、权限及文件摘要均相同。运行探针为 `enabled`，Shell 接口返回
  `owner-loss-focus-recheck-v2`。应用配置字节、auto 与系统输入源保持原值。
- 两个独立原生 GTK 文本框验证启用后的自动输出。A 收到「甲」，B 实际获得焦点
  后收到「乙丙」，无迟到或键盘回退调用。路由选中 IBus、记录三次派发和
  `ibus_delivery_unknown`。实际正文由 GTK 事件独立观察，路由状态本身不确认接收。

在 `/tmp/inkecho-ibus-configure-wayland26.Gd1n6o/` 可重放夹具。按 `launch.json`
启动一次性客机，将 input 挂载到 `/mnt/input`，output 挂载到 `/mnt/output`。
用测试用户运行 `desktop-state.py stage` 后重新登录，依次运行
`launch-configure.py initial`、再次重新登录、`launch-configure.py retry` 和
`launch-probe.py`。两个按钮阶段均退出 0。首次夹具因包内无 QtTest 而未点击，
最终使用 QtGui 鼠标事件。GTK 首次遇到夹具 JSON 读写竞争，保留失败日志，改用
原子写入后复验通过。原始 JSON、页面截图、输出及清理日志均在 `output`。

本轮是 Ubuntu 26.04 Wayland 源码覆盖验证，目标是独立测试窗口。未覆盖完整主窗口
布局、物理鼠标或全局快捷键、活动组词、真实语音、Xorg 或新 AppImage。客机原扩展和
设置已恢复，夹具进程为空，QEMU 与容器正常退出 0，专用容器已删除。

### Ubuntu 24.04 GNOME Wayland 按钮复验

一次性 Ubuntu 24.04.5 LTS 客机的座席会话为 active Wayland，Qt 使用 wayland。
运行时为上文同 SHA-256 的 0.16.14 AppImage，两处源码覆盖的 SHA-256 也与上文
一致。打开页面时临时应用配置、系统输入源、扩展文件及 GNOME 设置均保持原样。
真实可见的「配置 IBus 输入桥」按钮接收一组 Qt 鼠标按下、释放事件。首次点击
安装七个与内置摘要匹配的文件，界面提示重新登录后点击同一按钮，扩展尚未启用。

客机 GDM 重新登录后，Shell 总线拥有者由 `:1.27` 变为 `:1.23`。再次点击同一
按钮后，运行探针为 `enabled`，接口返回 `owner-loss-focus-recheck-v2`。从首次
安装到第二次点击完成，扩展目录及七个文件的 inode、修改时间、权限与摘要完全
一致。两次应用配置均为 auto，系统输入源保持原值。

原始 JSON、按钮可见截图与夹具位于
`/tmp/inkecho-ibus-configure-wayland24.3p2GXU/`。从只读基盘启动一次性客机，
将 input 挂载到 `/mnt/input`，output 挂载到 `/mnt/output`，依次执行
`guest-setup.sh`、`desktop-state.py stage` 和 `launch-configure.py initial`。
重新登录后运行 `launch-configure.py retry`。两个阶段均退出 0。清理恢复了
客机 GNOME 设置和 GDM 配置，移除了测试扩展，夹具进程为空。QEMU 与容器均
退出 0，专用容器已删除。本轮仅验证源码覆盖下的配置按钮及扩展运行状态，
未测 GTK 输出，未生成新 AppImage。
