# Fcitx 输出清理失败验证（2026-10-31）

在 Linux 本机使用 Python 虚拟环境运行受控回归：

```sh
TMPDIR=/var/tmp .venv/bin/python -m pytest -q tests/test_output_router.py tests/test_fcitx_owned_handoff.py tests/test_fcitx5.py
```

结果：217 项通过。测试使用真实 `Fcitx5Bridge` 清理代码及模拟 D-Bus、模拟
capability 删除失败，覆盖取消、过期、已部分发送、零发送时原文回退、以及
KeyboardInterrupt/SystemExit；也使用桥替身检查诊断和发送计数。清理失败不会
作为普通润色失败进入回退；既有输入错误与停止结果保留，发送计数为尝试数，并非
目标应用收件确认。测试不连接真实桌面或真实 Fcitx 服务，不验证组词与焦点。

输出主体成功后，如果仅在等待清理时 predicate 或 deadline 发生变化，基础作用域
不保留它们，不能承诺此情形的停止优先；已抛出的任务取消异常会保留。对已派发的
请求仍无法撤回，任何未确认输入不能重放。
