# X11 映射稳定等待：本地验证记录

日期：2026-10-28。

## 范围和语义

配置 `x11_mapping_wait_ms` 默认为 40，允许 20–250 毫秒。它控制 X11 键盘输出中，实际修改键盘映射后、后续按键前的等待；只在确实修改映射时生效。首次映射仍等待 100 毫秒，按键按下和释放后各等待 10 毫秒。映射缓存复用不增加该等待。X11 自适应节流和反馈事件合并保持独立；原生 Wayland 和输入法路径不使用此设置。

设置页的「X11 键盘映射稳定等待」自动保存。每次录音任务开始时读取一次；任务进行中修改设置，下一次任务才生效。Hybrid 输出在同一任务内切换原生和 X11 目标时也沿用该次读取的值。旧配置缺少该字段时读取默认值，读取本身不改写文件。

此等待不确认目标应用处理、绘制或呈现文字，也不修改任何第三方窗口的帧同步状态。交接文档的受控实验中，40 毫秒并非普遍可靠的平滑输出阈值；不能把默认值当作逐字显示保证。

## 可复现的本地检查与结果

在仓库根目录执行：

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_config.py tests/test_keyboard.py tests/test_hybrid_keyboard.py tests/test_wayland_keyboard.py
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_ui.py::test_settings_autosave_and_separate_data_logs
.venv/bin/ruff check src/inkecho/config.py src/inkecho/app.py src/inkecho/platform/keyboard.py src/inkecho/platform/hybrid_keyboard.py src/inkecho/ui/information.py tests/test_config.py tests/test_keyboard.py tests/test_hybrid_keyboard.py tests/test_ui.py
.venv/bin/ruff format --check src/inkecho/config.py src/inkecho/app.py src/inkecho/platform/keyboard.py src/inkecho/platform/hybrid_keyboard.py src/inkecho/ui/information.py tests/test_config.py tests/test_keyboard.py tests/test_hybrid_keyboard.py tests/test_ui.py
```

配置、X11 键盘、Hybrid 和原生 Wayland 测试共 264 项通过；设置页测试 1 项通过。检查包括旧配置读取、取值范围、首映射及按键时序、缓存复用、会话内快照及 Hybrid 目标切换。ruff 检查结果见本轮执行记录。

将 `tests/test_startup_shortcut_health.py` 加入上述组合的两次运行均在末尾停滞，已手动中止；该测试尚未通过，不能计入通过数。

## 尚未完成

两系统均有下述虚拟桌面源码实验；尚未完成真实目标应用绘制进度及最终 AppImage 验收。上述检查不能替代双系统包验收，也不能证明 40 毫秒适用于所有目标或负载。

## 隔离桌面探针

`scripts/validation/x11_mapping_wait_probe.py` 要求实际 Ubuntu 24.04 Xorg 虚拟机，以及已审查的候选包或冻结源码快照；它校验包摘要及包内源码来源，或完整校验快照和导入来源。每次创建新私有配置和自有 Chrome 接收窗口，从真实 `Session` 读取指定等待。它通过窗口 PID、进程起始时间、顶层焦点和近期接收框焦点守卫每次按键；失去所有权时停止，释放按键仍允许执行。

在受控 VM 中，使用同一个候选 AppImage、解包路径、冻结源码及唯一的新结果路径，分别运行 20、40、80 毫秒和 `normal`、`cancel`、`currentcursor` 选项；每例例子中的路径、摘要和版本须由执行者替换：

```sh
QT_QPA_PLATFORM=offscreen "$PACKAGE_PYTHON" scripts/validation/x11_mapping_wait_probe.py \
  --artifact "$APPIMAGE" --package-root "$PACKAGE_ROOT" \
  --frozen-source-root "$FROZEN_SRC" --expected-sha "$SHA256" \
  --expected-version "$VERSION" --wait-ms 40 --mode normal \
  --output "$NEW_RESULT_JSON" --work-root "$NEW_PRIVATE_WORK" --run-host
```

探针记录映射准备返回到下一次成功按键的时间、实际读取的配置、精确回读、平衡事件、映射恢复、取消后 1.2 秒静默和进程退出。它不观察绘制帧；不能用其通过结果证明逐字可见或用户界面本身完成端到端操作。还需独立观察自有 GTK 测试窗口的绘制，以及完成 Ubuntu 26.04 和同一包的正式验收。

探针离线 fake-driver 测试：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_x11_mapping_wait_probe.py`，7 项通过；这不是真实桌面输入。

## Ubuntu 24.04 Xorg 源码桌面实验

2026-10-28，在独立 Ubuntu 24.04.5、GNOME Xorg VM 的自有 Chrome 文本框进行五例源码实验。快照由本轮未提交源码冻结，SHA-256 `42fda9ef70214340ece7b99ff872575eb42ee7a9eedb72bdf2465e7bff1cb617`，使用既有 0.10.0 AppImage 的解包 Python 和依赖，**并非当前源码的 AppImage 包验收**。五例各自使用新配置及接收窗口，保存值与 Session 输出会话读取值均一致，结果如下：

| 设置 | 场景 | 首次映射后最短等待 | 后续映射后最短等待 | 结果 |
|---|---|---:|---:|---|
| 20 ms | 正常输出 31 字 | 102.053 ms | 23.891 ms | 精确回读、31 次按下及释放、映射恢复 |
| 40 ms | 正常输出 31 字 | 107.513 ms | 41.957 ms | 精确回读、31 次按下及释放、映射恢复 |
| 80 ms | 正常输出 31 字 | 101.808 ms | 81.058 ms | 精确回读、31 次按下及释放、映射恢复 |
| 40 ms | 8 字后取消 | 103.036 ms | 43.623 ms | 精确前缀、1.2 秒无尾字、8 次按下及释放、映射恢复 |
| 40 ms | 输出中切换两个窗口 | 104.857 ms | 42.980 ms | 两窗口各得预期片段、31 次按下及释放、映射恢复 |

五例均无身份守卫拒绝，自有浏览器正常退出。原始 JSON 和日志归档在 `build/x11-mapping-wait-results-r1.tar`，SHA-256 `05d895feca20dfa5117acff912a8d4ed0f449376a458c500605ad270d880e744`。启动期间 SSH 两次在 banner 等待时超时；虚拟机在 networkd 启动等待后自然就绪。测试结束后自有测试进程检查为空，来宾正常关机，容器 `docker wait` 返回 0。上述数据仅证明受控源码路径和按键时序，不证明图形逐字呈现、实体按键取消或 26.04 体验。

## Ubuntu 26.04 Wayland / XWayland 源码实验

独立虚拟机的真实 logind 会话为 Wayland，受控 Chrome 窗口使用 XWayland；这不是 Xorg 会话，也不代表原生 Wayland 目标通过。源码快照 `build/x11-mapping-wait-source-r3.tar` 的 SHA-256 为 `1b99f1449e93d4c13459f93c53d00d0f086c1544c6b15bf2d418244f919a7159`，包含当时的输入路由更改；后续源码若改变，须重新验收。

40、20、80 ms 的三个单窗口正常例分别以 30 字精确回读、30 对按键和映射恢复通过；后续映射到按键的最短实测分别为 40.938、20.835、81.968 ms。40 ms 取消例只发送 8 字，持续 1.2 秒无尾字，按键及映射恢复通过。所有窗口均由探针创建并按 PID、焦点和时效逐次守卫；这些例不验证逐字绘制或 AppImage。

40 ms 跨窗口 `textarea` → `contenteditable` 例失败两次：均发送 30 对按键、守卫拒绝 0，浏览器正常退出；重试记录显示首窗口 5 字完全一致，第二窗口 25 字与预期长度一致但摘要不同。离线对照摘要可确定第二窗口仅换行前的 U+0020 被 U+00A0 替代，不可将失败改写为通过。

随后在同一产品源码快照上增加固定样本对照：`textarea` → `textarea` 切换例 30 字精确通过，两窗口的差异列表均为空；不切换焦点的单窗口 `contenteditable` 例仍失败，其唯一差异为位置 24 的 U+0020 变为 U+00A0。二者均为 30 对按键、守卫拒绝 0、测试窗口正常退出。该对照说明差异不依赖焦点切换，支持它与 `contenteditable` 内容处理相关；没有直接捕获 DOM 或 input 事件，不能断言具体浏览器内部机制，也不能把严格码点差异称为通过。对照结果归档 `build/x11-mapping-wait-26-results-r6.tar`，SHA-256 `fd6197792ccb398219a529cb22b08ab9b9f6a83e5aaa0eeeb7d604b8edf86e22`；对照包 `build/x11-mapping-wait-source-r6.tar` 的源码与 r3 相同，仅探针增加诊断，归档 SHA-256 `522808c53d7d46f94985905d540eb00931cd5687028ac4aed3bf7b6b75373f4e`。这只验证冻结快照，最终集成后的源码和实际候选包必须重验。

首轮五例因探针未兼容 Hybrid 所用的另一种 X11 驱动，在任何按键之前失败；修复探针后另一次启动因会话锁屏而在发送前被安全检查拒绝。首轮失败归档 SHA-256 `93686e150400ac4c53a1908ae1b5bd6680b80d05069096ad97c872b2d29873ff`；第二轮成功和切换失败归档 SHA-256 `b48c6a282edebd77a989726aee9c308e7449486c717e3b8c8f0d7de274be525a`；切换重试失败归档 SHA-256 `05b832bbe09c96eb42e03fcb029daf0f35120b3ec3c5531450b466634827b5f8`，均位于 `build/x11-mapping-wait-26-results-*`。实验后测试进程为空，来宾的 idle-delay 300 和 lock-enabled true 已恢复，正常关机且 `docker wait` 返回 0。

## 独立的 X11 绘制反馈超时下限

现增加 `x11_feedback_timeout_ms`，默认 40 毫秒，可设 20–250 毫秒；设置页自动保存，录音任务加载设置时形成快照，输出会话及 Hybrid 后端切换沿用该值。它只改变 X11 键盘输出中 DRAW 反馈等待的动态超时下界；收到合格绘制提示仍可提前继续，无提示则按动态时限退让。动态时限也会受反馈延迟估计和 250 毫秒上限影响，故不是恒定每字等待或窗口帧同步配置，也不保证目标应用已显示文字。此值与键盘映射稳定等待独立，原生 Wayland 和输入法桥不使用它。

本地测试覆盖配置范围、保存、会话快照、Hybrid 切换，以及既有反馈提示、超时、取消与焦点代际失效：`QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q tests/test_output_pacing.py tests/test_config.py tests/test_keyboard.py tests/test_hybrid_keyboard.py tests/test_output_router.py tests/test_ui.py::test_settings_autosave_and_separate_data_logs`，261 项通过。新参数尚未在隔离桌面测量 changed/draw/after-paint、目标实际可见进展或最终 AppImage；不能据此宣称 40 毫秒提升或保证逐字显示。

### Ubuntu 24.04 自有窗口反馈超时对照

2026-10-28，在独立 Ubuntu 24.04 Xorg 虚拟机、自建 Chrome 文本框，使用冻结源码 `build/feedback-wait-source-r1.tar`（SHA-256 `c26f8c88070df0ee1ece088194fb64675284a6d57f35e1d64c4c28327fd69216`）和既有 0.10.0 AppImage 解包的 Python 运行时执行扩展探针。该冻结源码不是当前 AppImage 的双系统验收。映射稳定等待均固定 40 ms，独立反馈超时下限分别为 40 与 80 ms；输入由真实 Session 配置和 X11 键盘路由执行。每例均保存不同私有配置和自建窗口，读取结果为：

| 反馈下限 | 场景 | 实际 Session 值 | 输出总耗时 | 结果 |
|---|---|---:|---:|---|
| 40 ms | 正常 | 40 ms | 2179.8 ms | 31 字精确回读，31 对按键 |
| 80 ms | 正常 | 80 ms | 1709.8 ms | 31 字精确回读，31 对按键 |
| 40 ms | 8 字后取消 | 40 ms | 516.9 ms | 前 8 字精确，之后 1.2 秒无尾字，8 对按键 |
| 40 ms | 输出中切换窗口 | 40 ms | 2190.3 ms | 两窗口各获预期片段，31 对按键 |

全部例子的配置保存值与会话读取值一致，映射恢复、按键释放及身份守卫通过。输出总耗时包括输出会话清理；切窗例还包含目标窗口切换。单次样本无法证明 40 比 80 快或慢，探针也不观察绘制帧或逐字可见性。应用层独立测试还验证录音开始后修改映射等待及反馈超时仅对下一任务生效；本桌面实验直接创建 Session 输出会话，未模拟真实录音或实体 ESC。

使用 `scripts/validation/x11_mapping_wait_probe.py` 和上文同一包/源码来源校验方式，增加 `--feedback-timeout-ms 40` 或 `80`，保持 `--wait-ms 40`，分别执行 `normal`、`cancel` 和 `currentcursor`。完整结果归档 `build/feedback-wait-results-r1.tar`，SHA-256 `9f6269ff781d0b9ab8bded0182782ac647b1b47e00d4453a6699db9df9987a5e`；执行器 `build/feedback-wait-runner-r1.py`。虚拟机启动有五次 SSH banner 超时，随后自然就绪；实验文件清理，自有测试进程退出，来宾正常关机、容器退出 0。
