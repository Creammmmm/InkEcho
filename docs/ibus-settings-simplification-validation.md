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
