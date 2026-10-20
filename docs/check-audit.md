# Test and check maintenance audit

Audit baseline: `2c562ea` (0.6.1), 2026-10-21. The authoritative baseline completed
normally: **2158 passed, 3 skipped, 66.66s**. There were 80 `test_*.py` modules
plus `conftest.py` (81 Python files). Counts below describe files, not a target
for deleting parameterized boundary cases. Final results must be measured again;
one original skip belongs to the historical accessibility opt-in test.

Disposition is a review decision, not permission to delete a safety test while
its tool remains callable. Historical tools and their tests retire together only
after their incoming imports and current acceptance dependencies are resolved.
The detailed AST inventory and baseline measurements are in
`build/check-cleanup-audit/`; the baseline log is
`build/check-cleanup-baseline-pytest.log` (local generated evidence).

## Necessary coverage and changes

Keep product cancellation/stale/replacement boundaries, current-cursor semantics,
protocol framing/auth/error limits, credential ownership/atomic writes/symlink
rejection, task snapshots, startup/IPC and held-key/mapping recovery. Keep actual
package identity and isolated-target guards. Large parameter matrices are not
redundant merely because they share a function.

The old cloud/live comparison tools repeat local TLS experiment arms, accounting
for approximately 16–17 seconds among the baseline's slowest cases. Retire those
only with their obsolete experiment closure; retain current production local
HTTP/WSS/SSE integration and cancellation tests. Actual source and package
acceptance remain distinct. Shared desktop preflight and current package fixtures
must be extracted or retained before removing callers of old experiments.

In `test_package_factory_mixed.py`, remove the AST import-spelling assertion: it
only verifies syntax, not execution. Retain the real factory construction,
HybridKeyboardInput type and unopened native/X11 driver checks. Preserve all four
`test_desktop_acceptance.py` groups: delayed credential focus, adversarial late
reply, polishing failure policy and actual qasync worker delivery have distinct
Session integration contracts. Pytest collection scope, skip rules and hooks are unchanged. The only pytest
configuration change adds `scripts/validation` to pythonpath for an explicit
non-production synthetic provider fixture.

## Per-file disposition

“Retire with tool” is conditional on the companion tool audit; a retained shared
fixture or guard can change that decision. The original audit inventory is kept
here even when a subsequent cleanup removes the listed file.

| Baseline test file | Disposition | Reason |
|---|---|---|
| `test_a14_input_speed.py` | Retire with obsolete tool closure | 旧 a14 固定样本/指标副本；现行 test_input_speed_probe 已检同类100字样本、无效时间和吞吐。不删现行输入guard。 |
| `test_application.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_application_early_realtime.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_application_realtime.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_application_streaming.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_artifact_acceptance_controls.py` | Keep current guard/shared fixture | 现行包来源、完整source绑定、guard新鲜度、owned Chrome退出与无重放等验收真实性边界，属于交付安全契约，不因在scripts目录就删。 |
| `test_audio.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_audio_probe.py` | Keep device-probe guard | Tool closure review retains scripts/audio_probe.py; empty/invalid real-device capture protection is still relevant. |
| `test_autostart_autosave.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_billing_updates.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_config.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_core.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_dashboard_layout.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_dashscope_realtime.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_desktop_acceptance.py` | Keep current guard/shared fixture | 前3个Session场景可与application/core核对合并，第四个真实qasync credential+delivery是跨层契约必须保留。未逐条证明等价前不删。 |
| `test_dual_ubuntu_packaging.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_eis.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_host_mixed_probe.py` | Keep current guard/shared fixture | 现行owned目标身份/字段/env/settle边界安全；保留，不把焦点guard与产品焦点自由语义混淆。 |
| `test_hotkeys.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_http_asr.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_hybrid_keyboard.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_input_speed_probe.py` | Keep current guard/shared fixture | 当前真实factory benchmark审计、包/源码区分和未知输入不重放，保留。其样本/指标可承接a14副本测试。 |
| `test_integration.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_keyboard.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_keyboard_latency_probe.py` | Keep current guard/shared fixture | 现行guest Xorg门依赖verify_ubuntu24_vm_x11；保留实际OS/VM/session/owner/readbudget安全测试。仅可精简旧CLI非现行分支，须先分离shared helpers。 |
| `test_logging.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_model_configuration.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_model_style_layout.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_native_cloud_probe.py` | Retire with obsolete tool closure | 旧AT-SPI native_cloud_workflow_probe 的只读配置guard自测；与旧capturedtarget入口一并退役，不删除现行凭据store/endpoint安全测试。 |
| `test_native_wayland_probe.py` | Keep current guard/shared fixture | host_mixed_wayland_probe仍复用SAMPLE/load_package/metadata，保留ownedguard、包来源、精确balanced事件断言；先抽公共helper再评估旧CLI。 |
| `test_notifications.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_overlay_host.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_overlay_probe.py` | Keep current guard/shared fixture | 現行悬浮窗探针安全边界/只自有窗口，不是产品视觉断言替代；保留或随实际调用图简化。 |
| `test_owned_memory_text_fixture.py` | Retire with obsolete tool closure | 旧memory-target匿名UNIX socket GTK fixture；仅当live/noble/memory实验及其全部caller退休才删。保留仍在用的natural_owned_browser。 |
| `test_package_factory_mixed.py` | Keep current guard/shared fixture | 包范围与来源guard保留；test_actual_factory_import_and_construct_without_desktop_io中AST import语法子断言可删/改行为（constructor断言保留）。 |
| `test_packaging.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_performance.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_performance_baseline.py` | Retire with obsolete tool closure | 人为sleep的同步/流式比较，证明脚本自身安排的先后，不验证产品性能；已有test_application_streaming与performance产品时间schema。 |
| `test_performance_cloud_comparison.py` | Retire with obsolete tool closure | 旧两臂合成实验runner自测，normal/focus/cancel/expire/late双TLS重复产品Session端到端；只有与旧实验工具闭包成套退休才删。 |
| `test_performance_host_a13.py` | Retired; shared guard migrated | Preflight and missing-session/lock protections moved to `desktop_preflight.py` and `test_desktop_preflight.py`; current acceptance callers retain the shared checks. |
| `test_performance_live_comparison.py` | Retire with obsolete tool closure | 旧付费/live比较runner预算和双TLS实验；如果整套旧live工具退休则删；仍可执行时必须保留出站预算、凭据防漏和无重放测试。 |
| `test_performance_live_handoff.py` | Retire with obsolete tool closure | 旧live实验匿名pipe凭据/音频交接协议，仅服务该实验闭包；可以随闭包整退，不能只删测试留下可付费入口。 |
| `test_performance_memory_target.py` | Retire with obsolete tool closure | 旧双臂实验的独立memory-target管理层，仅在上述实验闭包中保留价值；随调用闭包退役前检查其它fixture引用。 |
| `test_performance_noble_comparison.py` | Retire with obsolete tool closure | 旧Noble对比实验专用VM/计划runner；与新现行包验收分离，随旧实验闭包退役。 |
| `test_performance_noble_live.py` | Retire with obsolete tool closure | 旧Noble live云实验/网络桥恢复runner，测试大量维护其特有状态机。闭包退役后成套删；如果工具保留，网络清理/不重试的测试不能删。 |
| `test_performance_package_probe.py` | Keep current guard/shared fixture | 现行manual localWSS package gate仍复用其fixture（private clone），保留固定PCM/ownedmode/取消统计/无额外cleanup等契约。旧命名不代表死代码。 |
| `test_platform_accessibility.py` | Retire with obsolete tool closure | 明确测试 historical_accessibility 的 captured-target/失焦取消旧语义，与2026-10-14现行契约相反；随旧AT-SPI入口闭包退役。 |
| `test_platform_capabilities.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_polish_protocols.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_polish_stream.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_polish_stream_probe.py` | Keep current guard/shared fixture | 有显式live入口的润色诊断；若保留入口，必须保留无live不读key、旧schema只读和失败脱敏，不因只4defs而删。 |
| `test_provider_capability.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_provider_catalog.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_provider_guidance.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_provider_package_probe.py` | Keep current guard/shared fixture | 测试运行时+诊断framework隔离、禁止overlay产品/Qt虚拟模块核验；用于包级验收可信性，保留。 |
| `test_providers.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_qwen_vad.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_realtime.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_realtime_preview.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_realtime_silence_probe.py` | Keep current guard/shared fixture | 有显式授权的生成静音诊断，保护真实key/endpoint和协议观察不造假；仅工具整体退役可删，不可裸删安全测试。 |
| `test_runtime.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_runtime_streaming.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_security.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_shortcut_probe.py` | Retire with obsolete tool closure | 旧stage0原始keycode匹配工具，与产品GNOME快捷键注册/物理捕获不同；随该旧CLI退役可删，保留test_hotkeys和startup health。 |
| `test_signed_asr.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_startup.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_startup_shortcut_health.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_statistics.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_step_realtime.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_streaming_output.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_ui.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_ui_protocol_acceptance.py` | Keep current guard/shared fixture | 现行包UI过滤/私有保存工具契约，但可把重复UI断言委托同一场景helper，勿直接删唯一工具接线测试。 |
| `test_versioning.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_wayland_keyboard.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_wayland_keymap.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_wayland_worker.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_workflow.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_workspace.py` | Keep product contract | 生产行为/用户契约回归；保留。按失败触发边界评审是否重复，不按文件行数或参数个数删。 |
| `test_x11_acceptance.py` | Keep current guard/shared fixture | 现行包Xorg/XWayland实际验收依赖的ownedfocus及成功事件计数，不是历史语义；必须保留。 |
| `test_x11_probe.py` | Retire with obsolete tool closure | stage0独立inject复制实现，test_focus_change_stops_remaining_input属于已废弃语义。只随旧probe闭包删，不动test_keyboard当前cursor安全。 |
| `conftest.py` | Keep shared fixture | Qt and isolated test initialization; not an independently redundant suite. |

The implemented closure retains `test_audio_probe.py` and retires
`test_performance_host_a13.py` after moving its live desktop preflight
contracts to the new `test_desktop_preflight.py`. The new shared implementation
`desktop_preflight.py` serves current native/Xorg acceptance callers; its test
module preserves missing-session and lock checks and adds unavailable-state,
wrong-user/type/lock and invalid-session-ID boundaries. The final deletion index and shared
guard migration are documented in [retired validation tools](retired-validation-tools.md).

## Measurement and execution

After reviewed deletions, collect the final tests and run the unchanged full
workflow on its clean final HEAD. Record actual pass/skip counts and duration;
do not treat the restricted duplicate diagnostic run (terminated with exit 143)
as a product result. Use focused tests while editing. Compare elapsed time under
the same authorized local environment, recognizing normal timing variation.
Current execution requirements are in the [acceptance checklist](acceptance-checklist.md).
