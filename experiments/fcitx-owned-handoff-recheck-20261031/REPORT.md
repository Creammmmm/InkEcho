# Fcitx 到 owned IBus 切换后的状态复查

本地使用测试替身验证自动切换：Fcitx 确认本任务零发送、owned 扩展与双方服务身份已核验后，清理旧 Fcitx 桥可能等待。在该等待中扩展被停用时，旧实现仍会调用 owned 输出。候选在清理后重新检查启用状态，并在此异步等待后重新检查两方服务身份；发现状态或身份改变时清理候选桥且不发送。

```sh
python -m pytest -q tests/test_fcitx_owned_handoff.py tests/test_output_router.py tests/test_explicit_owned.py tests/test_fcitx_preflight_restricted.py
python -m ruff check src/inkecho/platform/ibus_owned_default.py tests/test_fcitx_owned_handoff.py
```

上述相关测试 174 项通过，Ruff 通过。新增测试覆盖旧桥清理时停用扩展、最终状态检查等待期间取消，以及在该等待期间分别更换 Fcitx 和 owned 服务 owner；异常时旧桥和候选桥各清理一次，候选不发送。现有测试覆盖未变化时的正常切换及原有取消、安全停止行为。

这是离线替身测试，不是实际桌面、真实输入法、完整 Session 或应用包验收。多次异步检查与后续发送无法原子化：不同检查之间以及最后检查后仍可能发生外部状态变化；本改动仅缩短已识别的窗口，不证明消除所有竞态，也不扩大兼容性声明。
