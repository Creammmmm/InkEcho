# Retired validation tools

These historical experiments are no longer current acceptance commands. Their original source and recorded outcomes remain available in Git; historical validation reports are preserved without rewriting results. Current requirements are in [PROJECT_SPEC.md](PROJECT_SPEC.md) and current acceptance instructions in [acceptance-checklist.md](acceptance-checklist.md).

The first retired group contains fixed alpha package/source/VM procedures and the alpha6 audio adapter. No current release helper, tracked test or surviving script imports these entry points. These removals do not retire package provenance, desktop identity, current-cursor guards, cancellation or cleanup checks.

Frozen history: `2c562eae0c313a32f7f972572f8bfc77a61709f6`. Retrieve a file with `git show 2c562eae0c313a32f7f972572f8bfc77a61709f6:OLD_PATH`.

| Retired path | Historical source |
| --- | --- |
| `scripts/validation/artifact_runtime_probe.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/artifact_runtime_probe.py) |
| `scripts/validation/artifact_streaming_cursor_probe.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/artifact_streaming_cursor_probe.py) |
| `scripts/validation/audio_feedback_probe.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/audio_feedback_probe.py) |
| `scripts/validation/source_output_session_cursor_probe.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/source_output_session_cursor_probe.py) |
| `scripts/validation/source_pipeline_probe.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/source_pipeline_probe.py) |
| `scripts/validation/source_streaming_cursor_probe.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/source_streaming_cursor_probe.py) |
| `scripts/validation/ubuntu24_vm_a12.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/ubuntu24_vm_a12.py) |
| `scripts/validation/ubuntu24_vm_a12_paced.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/ubuntu24_vm_a12_paced.py) |
| `scripts/validation/ubuntu24_vm_a13.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/ubuntu24_vm_a13.py) |
| `scripts/validation/ubuntu24_vm_mapping_watch.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/ubuntu24_vm_mapping_watch.py) |
| `scripts/validation/ubuntu24_vm_package.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/ubuntu24_vm_package.py) |
| `scripts/validation/ubuntu24_vm_source.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/ubuntu24_vm_source.py) |
| `scripts/validation/ubuntu24_vm_source_output_session.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/ubuntu24_vm_source_output_session.py) |
| `scripts/validation/ubuntu24_vm_source_streaming.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/ubuntu24_vm_source_streaming.py) |
| `scripts/validation/ubuntu24_vm_streaming_stress.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/ubuntu24_vm_streaming_stress.py) |
| `scripts/validation/ubuntu24_vm_wm_diagnose.py` | [Git blob](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/ubuntu24_vm_wm_diagnose.py) |

## Retired captured-target and fixed-version experiments

The current desktop preflight remains in `scripts/validation/desktop_preflight.py`; its environment protection tests were migrated before retiring the old controller. Current package, focus guard, protocol and input checks remain active.

- [scripts/feasibility/accessibility_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/accessibility_probe.py)
- [scripts/feasibility/browser_target.html](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/browser_target.html)
- [scripts/feasibility/current_cursor_fixture.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/current_cursor_fixture.py)
- [scripts/feasibility/gtk_target.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/gtk_target.py)
- [scripts/feasibility/historical_accessibility.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/historical_accessibility.py)
- [scripts/feasibility/inspect_accessibility.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/inspect_accessibility.py)
- [scripts/feasibility/keyboard_backend_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/keyboard_backend_probe.py)
- [scripts/feasibility/listening_event_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/listening_event_probe.py)
- [scripts/feasibility/owned_browser_fixture.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/owned_browser_fixture.py)
- [scripts/feasibility/owned_memory_text_fixture.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/owned_memory_text_fixture.py)
- [scripts/feasibility/portal_keyboard_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/portal_keyboard_probe.py)
- [scripts/feasibility/portal_unicode_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/portal_unicode_probe.py)
- [scripts/feasibility/shortcut_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/shortcut_probe.py)
- [scripts/feasibility/terminal_keyboard_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/terminal_keyboard_probe.py)
- [scripts/feasibility/terminal_raw_fixture.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/terminal_raw_fixture.py)
- [scripts/feasibility/wayland_accessibility_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/wayland_accessibility_probe.py)
- [scripts/feasibility/wayland_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/wayland_probe.py)
- [scripts/feasibility/x11_browser_target.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/x11_browser_target.py)
- [scripts/feasibility/x11_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/x11_probe.py)
- [scripts/feasibility/xsend_transport.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/xsend_transport.py)
- [scripts/feasibility/xwayland_unicode_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/feasibility/xwayland_unicode_probe.py)
- [scripts/validation/a14_input_speed.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/a14_input_speed.py)
- [scripts/validation/artifact_output_session_cursor_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/artifact_output_session_cursor_probe.py)
- [scripts/validation/artifact_output_session_runtime_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/artifact_output_session_runtime_probe.py)
- [scripts/validation/current_cursor_workflow_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/current_cursor_workflow_probe.py)
- [scripts/validation/native_cloud_workflow_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/native_cloud_workflow_probe.py)
- [scripts/validation/native_voice_workflow_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/native_voice_workflow_probe.py)
- [scripts/validation/performance_baseline.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/performance_baseline.py)
- [scripts/validation/performance_cloud_comparison.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/performance_cloud_comparison.py)
- [scripts/validation/performance_comparison_fixture.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/performance_comparison_fixture.py)
- [scripts/validation/performance_host_a13.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/performance_host_a13.py)
- [scripts/validation/performance_live_comparison.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/performance_live_comparison.py)
- [scripts/validation/performance_live_handoff.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/performance_live_handoff.py)
- [scripts/validation/performance_memory_target.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/performance_memory_target.py)
- [scripts/validation/performance_noble_comparison.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/performance_noble_comparison.py)
- [scripts/validation/performance_noble_live.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/performance_noble_live.py)
- [scripts/validation/voice_workflow_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/scripts/validation/voice_workflow_probe.py)
- [tests/test_a14_input_speed.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_a14_input_speed.py)
- [tests/test_platform_accessibility.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_platform_accessibility.py)
- [tests/test_x11_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_x11_probe.py)
- [tests/test_shortcut_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_shortcut_probe.py)
- [tests/test_performance_baseline.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_performance_baseline.py)
- [tests/test_performance_cloud_comparison.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_performance_cloud_comparison.py)
- [tests/test_performance_live_comparison.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_performance_live_comparison.py)
- [tests/test_performance_live_handoff.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_performance_live_handoff.py)
- [tests/test_performance_noble_comparison.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_performance_noble_comparison.py)
- [tests/test_performance_noble_live.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_performance_noble_live.py)
- [tests/test_performance_memory_target.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_performance_memory_target.py)
- [tests/test_owned_memory_text_fixture.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_owned_memory_text_fixture.py)
- [tests/test_native_cloud_probe.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_native_cloud_probe.py)
- [tests/test_performance_host_a13.py](https://github.com/Creammmmm/InkEcho/blob/2c562eae0c313a32f7f972572f8bfc77a61709f6/tests/test_performance_host_a13.py)
