# Owned IBus 首片拒绝后的组词保护

2026-11-09。修复的是已选中 owned IBus 后，首片保护检查拒绝且确认零派发时，
自动模式绕过该保护转用键盘的缺陷。此前双系统 Chrome 反例见
[v0.16.7 记录](v0.16.7-ibus-handoff-composition-defect.md)。

## 行为与范围

在原有 `close_after_no_service` 完成后检查取消/期限；若是自动模式已经选中的
owned 路由，返回 `input_capability_unknown`，不再连接、授权或发送键盘输入。
清理失败仍报告 `ibus_cleanup_failed`，取消/期限优先，不重放未知结果。

初始没有兼容桥时的键盘选择、Xorg 自动路径、Fcitx 与显式 legacy IBus 的既有
规则不变。焦点变化本身不取消任务；兼容目标继续接受的输入不触发这项停止规则。
协议的 `no_service` 没有区分活动组词与其他目标保护失效，故首片拒绝时即使没有
组词也会停止。这是阻止已证实的保护绕过，不是完成免扩展 IBus 支持或扩大覆盖率。

## 两系统真实源码覆盖验证

两客机均使用 `e3a51740009f2c392bfe67802d1aa7e0c101d71c` 源码加精确四行修复。
`platform/output_router.py` SHA-256：
`16dfa3291a03b45ed1b48785825ced903374459adf22ffacee40a8c0ffe716f3`。
使用已核验 0.15.0 AppImage 的 Python/Qt 运行时，其 SHA-256：
`94a73232871abaca8c91fb5f58e52059be404f10605955562d39bf31ec64354a`。
这不是新版本 AppImage 验收，也不证明旧包已经修复。

| 环境 | Ubuntu 24 | Ubuntu 26 |
| --- | --- | --- |
| 系统 | 24.04.5 LTS | 26.04.1 LTS |
| GNOME / 会话 | 46.0 / Wayland | 50.1 / Wayland |
| Chrome / 后端 | 156.0.8078.79 / XWayland | 154.0.8037.97 / XWayland |
| IBus | 1.5.29-2 | 1.5.34~rc2-1 |
| ibus-libpinyin | 1.15.7-1build2 | 1.16.5-2 |
| 夹具输入 n、i、空格 | XTest | QMP 虚拟硬件按键 |

复现步骤：在隔离客机安装匹配 owned 扩展并加载 GNOME Wayland，启动自建空白
原生 GTK Entry 与私有配置 Chrome 合成页面。要求 GTK 实际 active/focused、
无正文/预编辑，真实 owned probe 成功。真实 DefaultAutoOutputRouter 自动选中
IBus；仅在 bridge 首次 insert 委托前暂停，切到自有 Chrome 输入框。确认 DOM
聚焦、实际引擎为 libpinyin，输入 ni 后已有 compositionstart/update(你)，没有
compositionend。然后委托真实 bridge 发送甲乙。键盘观察包装器只记录并调用原
实现，不阻止回退、不伪造成功。记录响应及全部合成页面事件，最后按空格。

两个系统均得到：

- 真实首片返回 `no_service`、累计派发尝试 0。
- 路由返回 `input_capability_unknown`，键盘 connect/insert 调用均 0。
- 拒绝前后 Chrome 的 composition/input 事件数组与值完全相同，没有提前结束组词。
- 空格随后产生 compositionend(你)，保留的原组词可正常提交；没有甲乙。
- 输出 scope 释放、键盘未连接，测试 Chrome/GTK 进程停止。

## 失败与清理

24 首轮因手工复制测试扩展文件权限 0664 被安装验证拒绝，改为 0600。
第二轮 setter `ibus engine libpinyin` 返回 1；最终显式 getter 确认实际已选中，
未替换引擎来绕过前置条件。夹具异常捕获移到 output_session 外，保留原诊断。
26 首轮同样遇到 setter 返回码和异常捕获问题；第二轮 CDP 未使 Chrome 真正聚焦，
第三轮 XTest 未产生组词，均不计有效样本。最终用自有 PID/标题定位并激活窗口，
确认 DOM 聚焦，再用 QMP 按键得到真实组词；没有放宽事件前置条件。

24 使用只读旧基盘和临时写盘，依赖、Chrome、扩展及登录会话调整仅在客机内。
26 使用既有只读快照链和临时写盘。结束恢复原输入源/扩展设置，26 比对设置相等
并恢复原扩展文件；24 恢复 GDM 文件，其余客机会话选择及安装文件随临时盘丢弃。
两客机正常 poweroff，QEMU/container 均退出 0，专用容器已移除。宿主输入法未改。

临时复现材料和原始失败保留在 `/tmp/inkecho-owned-stop-vm24` 与
`/tmp/inkecho-owned-stop26`：各自 `input/probe.py`、`input/launch-probe.py`、
`launch.json`、`REPORT.md`；24 最终 `output/final/result.json`、`probe-r3.log`，
26 最终 `output/owned-stop-result/result.json`、`probe-r4.log`、QMP request/ack。
路径是临时证据，不是持久发布资产；上述步骤和结果供独立复现审查。

离线回归使用真实 client/bridge 与合成 D-Bus，覆盖首片拒绝、清理一次、取消、
期限、清理异常、正常连续片段、初始无桥键盘、显式 legacy 和 Xorg。针对性测试
254 项通过；首次受限环境中两项本地 socket 测试因权限失败，在允许本地测试
socket 的环境正常通过。假 D-Bus 的连续片段测试不证明实际换焦兼容性。

本轮没有云端、物理麦克风、快捷键或任意其他应用验收；没有新包或 release。
