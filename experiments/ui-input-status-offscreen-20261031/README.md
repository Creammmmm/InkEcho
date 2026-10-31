# 输入状态界面隔离验证（2026-10-31）

使用工作区源码、Python 虚拟环境中的 PySide6 6.12.0 和 Qt `offscreen` 平台，
以临时配置创建真实主窗口，切换至「设置 → 输入兼容性」并检查控件可见。此方式
不会连接或操作用户桌面、实际输入法、真实配置或扩展。它不是 Ubuntu Xorg 或
Wayland 桌面验收，也不证明真实桌面的焦点、布局、输入法和组词行为。

可复现命令：

```sh
TMPDIR=/var/tmp QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_ui.py -k 'extension_action_reports_success_when_followup_status_fails or xorg_keyboard_fallback_explains_composition_risk or xorg_other_input_methods_do_not_claim_keyboard_fallback_risk'
```

结果：9 项通过，121 项未选。测试替换桌面会话信息为 Xorg 或 Wayland，检查
Xorg 自动、模拟键盘、旧 IBus 的组词提示，以及 Fcitx、新版 IBus 和 Wayland
不出现 Xorg 提示；这些判断是受控 UI 检查，并非自动检测测试。扩展操作、状态
查询的失败与成功由测试替身模拟：操作成功后查询异常分别显示「操作已提交」和
「状态检查失败」；单独查询异常会覆盖旧状态；未预期异常的内容不显示。

实际旧版及新版扩展管理器的 `status()` 对各自捕获的预期 `ExtensionError` 返回
描述性状态文本，测试中直接抛出的异常用于覆盖意外或未来实现的防御分支，不代表
已在真实 GNOME 扩展中复现该异常。

## 隔离桌面补充

Ubuntu 24.04.5 GNOME Xorg 客机以只读父盘、独立临时磁盘和隔离网络启动；
使用旧 AppImage（SHA-256 `94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a`）
仅提供 Python 和 Qt 运行时，叠加本次未提交的源码。`information.py` 的 SHA-256
是 `ada048dbf69b70f979040c8b745a817f4a05a3706bccef81f12573251206a191`。
真实主窗口切换到设置的输入兼容性页面，Qt 平台为 xcb，输出方式和三个时间输入
控件的高度分别为 39、41、41、41 像素。自动、键盘和旧 IBus 的 Xorg 提示，
以及 Fcitx 和新版 IBus 不显示该提示，受控选择全部通过；扩展异常由替身模拟。
截图和客机日志保存在 `/var/tmp/inkecho-ui-session-20261031/xorg-output/`。
首次完整窗口探针因旧运行时没有 QtTest 退出，改用 Qt 事件循环后通过；首次将
子页面单独打开的 Wayland 截图不是实际主窗口，不能用于判断产品布局。

重新启动的 Ubuntu 24.04.5 GNOME Wayland 客机使用同一源码和运行时完成完整
主窗口检查，Qt 平台为 wayland。四个控件高度同为 39、41、41、41 像素，五种
输出选项均未显示仅适用于 Xorg 的提示；受控扩展状态异常检查通过。截图和日志
保存在 `/var/tmp/inkecho-ui-session-20261031/wayland-main-output/`。两套桌面的
截图均已人工核对，视口中可见输出方式与首个等待时间控件；较下方的等待控件未
完整出现在截图中。所有控件具有正尺寸和 Qt 可见状态，但本轮未操作滚动条验证
下方控件的实际视口显示，不能断言四项均在同一屏可见。两台正式探针客机及先前
独立子页探针客机均正常退出（退出码 0、未发生 OOM），本次创建的三个隔离容器
已清理；图形应用使用临时配置、模拟扩展操作，没有向任何输入目标发送文字。

[desktop-probe.py](desktop-probe.py) 和 [guest-bootstrap.py](guest-bootstrap.py)
保存了格式整理后的等价脚本；重现时分别放入客机输入共享目录作为 `ui_probe.py`
及 `guest_bootstrap.py`，并提供 `/mnt/input/src` 和同一运行时。原始测试用脚本
及私有客机回执保留在上述临时目录；本测试不是最终 AppImage 验收。
